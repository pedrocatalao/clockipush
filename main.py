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
load_dotenv(override=True)

# ANSI Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

def resolve_names(projects, project_id, task_id):
    p_name = "Unknown"
    t_name = "Unknown"
    for p in projects:
        if p['id'] == project_id:
            p_name = p['name']
            for t in p['tasks']:
                if t['id'] == task_id:
                    t_name = t['name']
                    break
            break
    return p_name, t_name

def main():
    arg_parser = argparse.ArgumentParser(description='Sync Google Calendar events to Clockify.')
    arg_parser.add_argument('--dry-run', action='store_true', help='Run without making changes to Clockify')
    arg_parser.add_argument('--days', type=int, default=1, help='Number of past days to sync (default: 1)')
    arg_parser.add_argument('--today', action='store_true', help='Sync only today (since 00:00 UTC)')
    args = arg_parser.parse_args()

    # Configuration
    CLOCKIFY_API_KEY = os.getenv('CLOCKIFY_API_KEY')
    CLOCKIFY_WORKSPACE_ID = os.getenv('CLOCKIFY_WORKSPACE_ID')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'service_account.json')
    CALENDAR_ID = os.getenv('GOOGLE_CALENDAR_ID', 'primary')
    TARGET_PROJECT_NAME = os.getenv('CLOCKIFY_PROJECT_NAME')

    if not all([CLOCKIFY_API_KEY, CLOCKIFY_WORKSPACE_ID, GEMINI_API_KEY]):
        print("Error: Missing environment variables. Please check .env file.")
        return

    # Initialize Clients
    print("Initializing clients...")
    calendar_client = CalendarClient(service_account_file=SERVICE_ACCOUNT_FILE)
    clockify_client = ClockifyClient(api_key=CLOCKIFY_API_KEY, workspace_id=CLOCKIFY_WORKSPACE_ID)
    ai_matcher = AIMatcher(api_key=GEMINI_API_KEY)

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

    if args.today:
        # Start of today (00:00:00 UTC)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        time_min = start_of_day.isoformat().replace('+00:00', 'Z')
        # Buffer min is 1 day before start of day
        buffer_min_dt = start_of_day - datetime.timedelta(days=1)
    else:
        time_min = (now - datetime.timedelta(days=args.days)).isoformat().replace('+00:00', 'Z')
        buffer_min_dt = now - datetime.timedelta(days=args.days + 1)

    # Fetch existing time entries to prevent duplicates
    print("Fetching existing time entries...")
    try:
        # Buffer by 1 extra day to catch events that started before time_min but overlap
        buffer_min = buffer_min_dt.isoformat().replace('+00:00', 'Z')
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

    # Track total duration of calendar events
    total_calendar_seconds = 0

    if not events:
        print("No events found.")
    else:
        for event in events:
            summary = event.get('summary', 'No Title')
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            # Skip all-day events for now if they don't have specific times
            if 'T' not in start:
                print(f"Skipping all-day event: {summary}")
                continue

            print(f"Processing event: {CYAN}{summary}{RESET} ({start} - {end})")

            # Pre-check for duplicates
            # Convert event start to UTC ISO for comparison
            try:
                start_dt = parser.parse(start).astimezone(datetime.timezone.utc)
                end_dt = parser.parse(end).astimezone(datetime.timezone.utc)
                start_iso = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                
                # Add to total duration
                duration = (end_dt - start_dt).total_seconds()
                total_calendar_seconds += duration

                if (start_iso, summary) in existing_signatures:
                    print(f"  -> Skipping duplicate: Entry already exists for {start_iso}")
                    continue
            except Exception as e:
                print(f"  -> Error checking duplicate: {e}")

            # Match to Clockify Task
            project_id, task_id = ai_matcher.match_event_to_task(summary, projects_with_tasks)

            if project_id:
                p_name, t_name = resolve_names(projects_with_tasks, project_id, task_id)
                print(f"  -> Matched: Project='{p_name}' ({project_id}), Task='{GREEN}{t_name}{RESET}' ({task_id})")
                
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

    eligible_issues = []

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

        eligible_issues.append({
            "summary": summary,
            "status": status,
            "target_dt": target_dt
        })

    # --- Calculate and Distribute Time ---
    WORK_DAY_SECONDS = 8 * 3600
    remaining_seconds = max(0, WORK_DAY_SECONDS - total_calendar_seconds)

    print(f"\nTime Calculation:")
    print(f"  Total Calendar Time: {total_calendar_seconds / 3600:.2f} hours")
    print(f"  Target Work Day: 8.00 hours")
    print(f"  Remaining Time: {remaining_seconds / 3600:.2f} hours")
    print(f"  Eligible GitHub Issues: {len(eligible_issues)}")

    if eligible_issues and remaining_seconds > 0:
        seconds_per_issue = remaining_seconds / len(eligible_issues)
        print(f"  -> Allocating {seconds_per_issue / 3600:.2f} hours per issue")

        # Start allocating from 09:00 UTC of the target day (using the first issue's date as reference or 'now')
        # Since we might have mixed dates (Done vs In Progress), this is tricky.
        # But typically we are running for "Today".
        # Let's use the target_dt from the issue itself to set the day, but fix the hour.

        # Group by date to be safe?
        # For simplicity, we assume the sync is for a single day context.
        # We will use the target_dt from the issue to determine the DAY, but set the time sequentially.
        # To avoid overlaps on the same day, we need to track the 'next_start_time' PER DAY.

        next_start_times = {} # Key: Date string (YYYY-MM-DD), Value: datetime

        for issue in eligible_issues:
            summary = issue['summary']
            target_dt = issue['target_dt']
            date_key = target_dt.strftime('%Y-%m-%d')

            # Initialize start time for this day if not set (e.g., 09:00 UTC)
            if date_key not in next_start_times:
                next_start_times[date_key] = target_dt.replace(hour=9, minute=0, second=0, microsecond=0)

            start_dt = next_start_times[date_key]
            end_dt = start_dt + datetime.timedelta(seconds=seconds_per_issue)

            # Update next start time for this day
            next_start_times[date_key] = end_dt

            start_iso = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            end_iso = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

            print(f"Processing GitHub Issue ({issue['status']}): {CYAN}{summary}{RESET}")
            print(f"  -> Allocated: {start_iso} - {end_iso}")

            # Duplicate Check
            if (start_iso, summary) in existing_signatures:
                print(f"  -> Skipping duplicate: Entry already exists for {start_iso}")
                continue

            # Match to Clockify Task
            project_id, task_id = ai_matcher.match_event_to_task(summary, projects_with_tasks)

            if project_id:
                p_name, t_name = resolve_names(projects_with_tasks, project_id, task_id)
                print(f"  -> Matched: Project='{p_name}' ({project_id}), Task='{GREEN}{t_name}{RESET}' ({task_id})")

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
                    print(f"  -> Dry run: Skipping write.")
            else:
                print("  -> No suitable match found.")
    elif not eligible_issues:
        print("  -> No eligible GitHub issues found to distribute time.")
    else:
        print("  -> No remaining time to distribute (Calendar events >= 8 hours).")

if __name__ == '__main__':
    main()
