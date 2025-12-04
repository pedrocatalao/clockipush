import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from src.clockify_client import ClockifyClient
from src.calendar_client import CalendarClient
from src.ai_matcher import AIMatcher

load_dotenv()


def test_connections():
    print("Testing connections...")

    # 1. Clockify
    print("\n--- Clockify ---")
    api_key = os.getenv("CLOCKIFY_API_KEY")
    workspace_id = os.getenv("CLOCKIFY_WORKSPACE_ID")
    if api_key and workspace_id:
        try:
            client = ClockifyClient(api_key, workspace_id)
            projects = client.get_projects()
            print(f"Success! Found {len(projects)} projects.")
        except Exception as e:
            print(f"Failed: {e}")
    else:
        print("Skipping: Missing CLOCKIFY_API_KEY or CLOCKIFY_WORKSPACE_ID")

    # 2. OpenAI
    print("\n--- OpenAI ---")
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            matcher = AIMatcher(openai_key)
            # Simple test call
            # We won't actually call the API to save cost/time unless needed,
            # but instantiating checks the client.
            # To really test, we'd need a dummy prompt.
            print("Client initialized.")
        except Exception as e:
            print(f"Failed: {e}")
    else:
        print("Skipping: Missing OPENAI_API_KEY")

    # 3. Google Calendar
    print("\n--- Google Calendar ---")
    sa_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    if (
        os.path.exists(sa_file)
        or os.path.exists("token.json")
        or os.path.exists("credentials.json")
    ):
        try:
            client = CalendarClient(service_account_file=sa_file)
            client.authenticate()
            print("Authentication successful (service object created).")
        except Exception as e:
            print(f"Failed: {e}")
    else:
        print(
            "Skipping: No credentials file found (service_account.json, token.json, or credentials.json)"
        )

    # 4. GitHub
    print("\n--- GitHub ---")
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        try:
            import requests
            headers = {"Authorization": f"Bearer {github_token}"}
            query = """
                query($cursor: String) {
                  search(query: "is:issue assignee:@me sort:updated-desc", type: ISSUE, first: 1, after: $cursor) {
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                    nodes {
                      ... on Issue {
                        title
                        number
                      }
                    }
                  }
                }
            """
            response = requests.post(
                "https://api.github.com/graphql",
                json={"query": query, "variables": {"cursor": None}},
                headers=headers,
            )
            if response.status_code == 200:
                print(f"Success! Status Code: {response.status_code}")
                # print(f"Response: {response.text[:100]}...") # Optional: print snippet
            else:
                print(f"Failed: Status Code {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"Failed: {e}")
    else:
        print("Skipping: Missing GITHUB_TOKEN")


if __name__ == "__main__":
    test_connections()
