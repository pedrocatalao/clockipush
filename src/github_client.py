import os
import requests
import json
import sys


def run_query(query, variables=None):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("PERSONAL_GITHUB_TOKEN")
    if not token:
        print(
            "Error: Neither GITHUB_TOKEN nor PERSONAL_GITHUB_TOKEN environment variable is set.",
            file=sys.stderr,
        )
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}
    request = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
    )
    if request.status_code == 200:
        return request.json()
    elif request.status_code == 401:
        raise Exception(
            f"GitHub Authentication failed (401). Please check if your GITHUB_TOKEN or PERSONAL_GITHUB_TOKEN is valid and has the required scopes (repo, read:project, read:org)."
        )
    else:
        raise Exception(
            f"Query failed to run by returning code of {request.status_code}. {query}"
        )


def get_issues():
    query = """
    query($cursor: String) {
      search(query: "is:issue assignee:@me sort:updated-desc", type: ISSUE, first: 100, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          ... on Issue {
            title
            number
            state
            updatedAt
            repository {
              name
              owner {
                login
              }
            }
            projectItems(first: 10) {
              nodes {
                isArchived
                project {
                  title
                }
                fieldValues(first: 20) {
                  nodes {
                    ... on ProjectV2ItemFieldSingleSelectValue {
                      name
                      field {
                        ... on ProjectV2FieldCommon {
                          name
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    """

    issues = []
    cursor = None

    while True:
        variables = {"cursor": cursor}
        result = run_query(query, variables)

        if "errors" in result:
            print(f"GraphQL errors: {result['errors']}", file=sys.stderr)
            break

        data = result["data"]["search"]

        for node in data["nodes"]:
            if (
                not node
            ):  # Search can sometimes return None nodes or we might have filtered types
                continue
            issue_data = {
                "issue_name": node["title"],
                "number": node["number"],
                "status": node["state"],
                "updated_at": node["updatedAt"],
                "org": node["repository"]["owner"]["login"],
                "repo": node["repository"]["name"],
                "projects": [],
            }

            # Process projects
            if node["projectItems"]["nodes"]:
                for proj_node in node["projectItems"]["nodes"]:
                    project_info = {
                        "project_name": proj_node["project"]["title"],
                        "status": "No Status",
                        "is_archived": proj_node["isArchived"],
                    }

                    # Find status field
                    for field_value in proj_node["fieldValues"]["nodes"]:
                        # We look for the field named "Status"
                        if (
                            hasattr(field_value, "get")
                            and field_value.get("field", {}).get("name") == "Status"
                        ):
                            project_info["status"] = field_value.get("name")
                            break

                    issue_data["projects"].append(project_info)

            issues.append(issue_data)

        if not data["pageInfo"]["hasNextPage"]:
            break

        cursor = data["pageInfo"]["endCursor"]

    return issues

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect GitHub issues with filtering."
    )
    parser.add_argument("--org", help="Filter by organization name (case-insensitive)")
    parser.add_argument("--project", help="Filter by project name (case-insensitive)")
    parser.add_argument("--status", help="Filter by project status (case-insensitive)")
    parser.add_argument(
        "--is-archived",
        help="Filter by archived status (true/false)",
        choices=["true", "false", "True", "False"],
    )
    args = parser.parse_args()

    try:
        all_issues = get_issues()

        filtered_issues = []
        for issue in all_issues:
            # Filter by Org
            if args.org and args.org.lower() != issue["org"].lower():
                continue

            # Filter by Project, Status, and Archived
            # If project, status, or is_archived is specified, we need to check the projects list
            if args.project or args.status or args.is_archived:
                project_match = False
                for proj in issue["projects"]:
                    p_name_match = True
                    p_status_match = True
                    p_archived_match = True

                    if (
                        args.project
                        and args.project.lower() not in proj["project_name"].lower()
                    ):
                        p_name_match = False

                    if (
                        args.status
                        and args.status.lower() not in proj["status"].lower()
                    ):
                        p_status_match = False

                    if args.is_archived:
                        target_archived = args.is_archived.lower() == "true"
                        if proj["is_archived"] != target_archived:
                            p_archived_match = False

                    if p_name_match and p_status_match and p_archived_match:
                        project_match = True
                        break

                if not project_match:
                    continue

            filtered_issues.append(issue)

        print(json.dumps(filtered_issues, indent=2))
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)
