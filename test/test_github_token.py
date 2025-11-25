import os
from dotenv import load_dotenv
import requests
import json

load_dotenv()

token = os.getenv('GITHUB_TOKEN')
headers = {"Authorization": f"Bearer {token}"}

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

print("Running GraphQL Query...")
response = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': {"cursor": None}}, headers=headers)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
