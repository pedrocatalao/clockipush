import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from dotenv import load_dotenv
from src.ai_matcher import AIMatcher

# Load environment variables
load_dotenv()

# ANSI Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
RESET = "\033[0m"

api_key = os.getenv("OPENAI_API_KEY")
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
            {"id": "task_1d", "name": "Research"},
            {"id": "task_1e", "name": "Consultancy & Support"},
        ],
    }
]

test_events = [
    "Pedro / Erik (in the car) memory explainer",
    "#650 [report-service] cpu % shall be replaced by absolute cpu nanoseconds",
    "Update server from 4.17.8 to 4.17.9",
    "#654 [report-service] Number format exception (instance report)",
    "JIRA ticket - tracing issue",
    "Deploy new version to prod",
    "Retrospective & backlog refinement",
    "#655 [report-service] Code coverage from 22% to 51%",
    "#554 [Epic] Memory limitations Docker containers",
    "Discussion memory settings customer",
    "Fluxygen daily standup",
]

matcher = AIMatcher(api_key=api_key)

print("Running AI Matcher Tests (Batch)...")

# Prepare items for batch matching
items_to_match = []
for i, event in enumerate(test_events):
    items_to_match.append({"id": f"item_{i}", "description": event})

print(f"Batch matching {len(items_to_match)} items...")
matches = matcher.batch_match_tasks(items_to_match, projects_with_tasks)

print("\nResults:")
for item in items_to_match:
    item_id = item["id"]
    description = item["description"]
    match = matches.get(item_id)

    print(f"\nEvent: {CYAN}{description}{RESET}")

    if match and match["project_id"]:
        p_id = match["project_id"]
        t_id = match["task_id"]
        reasoning = match.get("reasoning", "No reasoning")

        # Find names for display
        p_name = "Unknown"
        t_name = "Unknown"
        for p in projects_with_tasks:
            if p["id"] == p_id:
                p_name = p["name"]
                for t in p["tasks"]:
                    if t["id"] == t_id:
                        t_name = t["name"]
                        break
                break

        print(
            f"  -> Matched: Project='{p_name}' ({p_id}), Task='{GREEN}{t_name}{RESET}' ({t_id})"
        )
        print(f"  -> Reasoning: {reasoning}")
    else:
        print("  -> No match found.")
