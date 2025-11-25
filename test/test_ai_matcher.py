import os
import json
from dotenv import load_dotenv
from src.ai_matcher import AIMatcher

# Load environment variables
load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    print("Error: OPENAI_API_KEY not found in environment.")
    exit(1)

# Mock Data
projects_with_tasks = [
    {
        "id": "proj_1",
        "name": "DevOps",
        "tasks": [
            {"id": "task_1a", "name": "Deployments"},
            {"id": "task_1b", "name": "Backlog"},
            {"id": "task_1c", "name": "Meetings"},
            {"id": "task_1d", "name": "R&D"}
        ]
    }
]

test_events = [
    "Daily Standup",
    "Fix crash on login screen",
    "Update homepage banner",
    "Client Call - Review Designs",
    "Interview candidate John Doe",
    "Deploy new version to prod",
    "Refinement session",
    "#655 [report-service] Code coverage from 22% to 51%",
    "#554 [Epic] Memory limitations Docker containers",
    "Discussion memory settings customer",
    "Fluxygen daily standup"
]

matcher = AIMatcher(api_key=api_key)

print("Running AI Matcher Tests...")
for event in test_events:
    print(f"\nEvent: {event}")
    p_id, t_id = matcher.match_event_to_task(event, projects_with_tasks)
    
    # Find names for display
    p_name = "Unknown"
    t_name = "Unknown"
    for p in projects_with_tasks:
        if p['id'] == p_id:
            p_name = p['name']
            for t in p['tasks']:
                if t['id'] == t_id:
                    t_name = t['name']
                    break
            break
            
    print(f"  -> Matched: Project='{p_name}' ({p_id}), Task='{t_name}' ({t_id})")
