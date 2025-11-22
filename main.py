import argparse
import os
import datetime
from dotenv import load_dotenv
from dateutil import parser

from src.calendar_client import CalendarClient
from src.clockify_client import ClockifyClient
from src.ai_matcher import AIMatcher
from src.github_client import get_issues

# Load environment variables
load_dotenv()

def main():
    arg_parser = argparse.ArgumentParser(description='Sync Google Calendar events to Clockify.')
    arg_parser.add_argument('--dry-run', action='store_true', help='Run without making changes to Clockify')
    arg_parser.add_argument('--days', type=int, default=1, help='Number of past days to sync (default: 1)')
    args = arg_parser.parse_args()

    # Configuration
    CLOCKIFY_API_KEY = os.getenv('CLOCKIFY_API_KEY')
    CLOCKIFY_WORKSPACE_ID = os.getenv('CLOCKIFY_WORKSPACE_ID')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'service_account.json')
    CALENDAR_ID = os.getenv('GOOGLE_CALENDAR_ID', 'primary')
    TARGET_PROJECT_NAME = os.getenv('CLOCKIFY_PROJECT_NAME')

    if not all([CLOCKIFY_API_KEY, CLOCKIFY_WORKSPACE_ID, OPENAI_API_KEY]):
        print("Error: Missing environment variables. Please check .env file.")
        return

    # Initialize Clients
    print("Initializing clients...")
    calendar_client = CalendarClient(service_account_file=SERVICE_ACCOUNT_FILE)
    clockify_client = ClockifyClient(api_key=CLOCKIFY_API_KEY, workspace_id=CLOCKIFY_WORKSPACE_ID)
    ai_matcher = AIMatcher(api_key=OPENAI_API_KEY)

    # Fetch Clockify Projects and Tasks
    print("Fetching Clockify projects and tasks...")
    projects = clockify_client.get_projects()
    projects_with_tasks = []
    for project in projects:
        # Filter by project name if specified
        if TARGET_PROJECT_NAME and project['name'] != TARGET_PROJECT_NAME:
            continue
            
        tasks = clockify_client.get_tasks(project['id'])
        project['tasks'] = tasks
        projects_with_tasks.append(project)
    
    if not projects_with_tasks:
        print(f"Error: No projects found matching '{TARGET_PROJECT_NAME}'" if TARGET_PROJECT_NAME else "Error: No projects found.")
        return

    # Calculate time range
    now = datetime.datetime.now(datetime.timezone.utc)
    time_max = now.isoformat().replace('+00:00', 'Z')
    time_min = (now - datetime.timedelta(days=args.days)).isoformat().replace('+00:00', 'Z')

    # Fetch existing time entries to prevent duplicates
    print("Fetching existing time entries...")
    try:
        # Buffer by 1 extra day to catch events that started before time_min but overlap
        buffer_min = (now - datetime.timedelta(days=args.days + 1)).isoformat().replace('+00:00', 'Z')
        existing_entries = clockify_client.get_time_entries(buffer_min, time_max)
        # Create a set of signatures: (start_time, description)
        # Clockify returns times in UTC ISO 8601, e.g. "2023-10-27T10:00:00Z"
        existing_signatures = set()
        for entry in existing_entries:
            # Normalize start time string just in case
            start = entry['timeInterval']['start']
            desc = entry.get('description', '')
            existing_signatures.add((start, desc))
    except Exception as e:
        print(f"Warning: Could not fetch existing entries ({e}). Duplicate prevention might fail.")
        existing_signatures = set()

    # Fetch Calendar Events
    print(f"Fetching calendar events from {time_min} to {time_max}...")
    print(f"Target Calendar ID: {CALENDAR_ID}")
    events = calendar_client.get_events(time_min, time_max, calendar_id=CALENDAR_ID)

    if not events:
        print("No events found.")
        return

    for event in events:
        summary = event.get('summary', 'No Title')
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        # Skip all-day events for now if they don't have specific times
        if 'T' not in start:
            print(f"Skipping all-day event: {summary}")
            continue

        print(f"Processing event: {summary} ({start} - {end})")

        # Pre-check for duplicates
        # Convert event start to UTC ISO for comparison
        try:
            start_dt = parser.parse(start).astimezone(datetime.timezone.utc)
            start_iso = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            if (start_iso, summary) in existing_signatures:
                print(f"  -> Skipping duplicate: Entry already exists for {start_iso}")
                continue
        except Exception as e:
            print(f"  -> Error checking duplicate: {e}")

        # Match to Clockify Task
        project_id, task_id = ai_matcher.match_event_to_task(summary, projects_with_tasks)

        if project_id:
            print(f"  -> Matched to Project ID: {project_id}, Task ID: {task_id}")
            
            # Convert times to UTC ISO 8601 for Clockify
            try:
                start_dt = parser.parse(start).astimezone(datetime.timezone.utc)
                end_dt = parser.parse(end).astimezone(datetime.timezone.utc)
                start_iso = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                end_iso = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            except Exception as e:
                print(f"  -> Error parsing dates: {e}")
                continue

            if not args.dry_run:
                try:
                    clockify_client.add_time_entry(
                        description=summary,
                        start_time=start_iso,
                        end_time=end_iso,
                        project_id=project_id,
                        task_id=task_id
                    )
                    print("  -> Time entry added successfully.")
                except Exception as e:
                    print(f"  -> Failed to add time entry: {e}")
            else:
                print(f"  -> Dry run: Skipping write. (Would send {start_iso} to {end_iso})")
        else:
            print("  -> No suitable match found.")

    # --- GitHub Issue Sync ---
    print("\nFetching GitHub issues...")
    try:
        github_issues = get_issues()
    except Exception as e:
        print(f"Failed to fetch GitHub issues: {e}")
        github_issues = []

    for issue in github_issues:
        # Determine Status ("In Progress" or "Done")
        status = None
        for proj in issue.get('projects', []):
            # Filter by project name if specified
            if TARGET_PROJECT_NAME and proj.get('project_name') != TARGET_PROJECT_NAME:
                continue

            s = proj.get('status', '').lower()
            if "in progress" in s:
                status = "In Progress"
                break
            elif "done" in s:
                status = "Done"
                break
        
        if not status:
            continue

        summary = f"#{issue['number']} {issue['issue_name']}"
        
        # Date Logic
        target_dt = None
        
        if status == "Done":
            # For DONE issues: Use the updated_at date.
            # Only process if it was finished within the sync window.
            updated_at_str = issue.get('updated_at')
            if not updated_at_str:
                continue
            try:
                updated_dt = parser.parse(updated_at_str).astimezone(datetime.timezone.utc)
                time_min_dt = parser.parse(time_min).astimezone(datetime.timezone.utc)
                time_max_dt = parser.parse(time_max).astimezone(datetime.timezone.utc)
                
                if not (time_min_dt <= updated_dt <= time_max_dt):
                    continue
                target_dt = updated_dt
            except Exception as e:
                print(f"Error parsing issue date {updated_at_str}: {e}")
                continue
                
        elif status == "In Progress":
            # For IN PROGRESS issues: Log for TODAY (current run date).
            # This ensures they are logged again if run tomorrow.
            target_dt = datetime.datetime.now(datetime.timezone.utc)

        if not target_dt:
            continue

        print(f"Processing GitHub Issue ({status}): {summary}")

        # 3. Set Time (12:00 PM on the target date)
        start_dt = target_dt.replace(hour=12, minute=0, second=0, microsecond=0)
        end_dt = start_dt + datetime.timedelta(hours=1)
        
        start_iso = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_iso = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        # 4. Duplicate Check
        if (start_iso, summary) in existing_signatures:
            print(f"  -> Skipping duplicate: Entry already exists for {start_iso}")
            continue

        # 5. Match to Clockify Task
        project_id, task_id = ai_matcher.match_event_to_task(summary, projects_with_tasks)

        if project_id:
            print(f"  -> Matched to Project ID: {project_id}, Task ID: {task_id}")
            
            if not args.dry_run:
                try:
                    clockify_client.add_time_entry(
                        description=summary,
                        start_time=start_iso,
                        end_time=end_iso,
                        project_id=project_id,
                        task_id=task_id
                    )
                    print("  -> Time entry added successfully.")
                except Exception as e:
                    print(f"  -> Failed to add time entry: {e}")
            else:
                print(f"  -> Dry run: Skipping write. (Would send {start_iso} to {end_iso})")
        else:
            print("  -> No suitable match found.")

if __name__ == '__main__':
    main()
