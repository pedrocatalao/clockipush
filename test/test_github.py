import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from src.github_client import get_issues
import json

load_dotenv()


def test_github():
    print("Testing GitHub Client...")
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN not found in .env")
        return

    try:
        print("Fetching issues...")
        issues = get_issues()
        print(f"Successfully fetched {len(issues)} issues.")
        if issues:
            print("Sample issue:")
            print(json.dumps(issues[0], indent=2))
    except Exception as e:
        print(f"Failed to fetch issues: {e}")


if __name__ == "__main__":
    test_github()
