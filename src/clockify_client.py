import requests
import os

class ClockifyClient:
    def __init__(self, api_key, workspace_id):
        self.base_url = "https://api.clockify.me/api/v1"
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        self.workspace_id = workspace_id

    def get_projects(self):
        """Fetches all projects in the workspace."""
        url = f"{self.base_url}/workspaces/{self.workspace_id}/projects"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_tasks(self, project_id):
        """Fetches tasks for a specific project."""
        url = f"{self.base_url}/workspaces/{self.workspace_id}/projects/{project_id}/tasks"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def add_time_entry(self, description, start_time, end_time, project_id, task_id=None):
        """Adds a time entry."""
        url = f"{self.base_url}/workspaces/{self.workspace_id}/time-entries"
        payload = {
            "description": description,
            "start": start_time,
            "end": end_time,
            "projectId": project_id,
            "taskId": task_id
        }
        response = requests.post(url, headers=self.headers, json=payload)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"Clockify Error: {response.text}")
            raise e
        return response.json()

    def get_time_entries(self, start_time, end_time):
        """Fetches time entries within a specific time range."""
        url = f"{self.base_url}/workspaces/{self.workspace_id}/user/{self.get_current_user_id()}/time-entries"
        params = {
            "start": start_time,
            "end": end_time,
            "page-size": 1000 # Fetch enough to cover the day
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_current_user_id(self):
        """Fetches the current user's ID."""
        url = f"{self.base_url}/user"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()['id']
