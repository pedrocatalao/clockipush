import openai
import json
import re

class AIMatcher:
    def __init__(self, api_key, model="gpt-4o"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def match_event_to_task(self, event_description, projects_with_tasks):
        """
        Matches an event description to the most relevant Clockify task.
        
        :param event_description: The title/description of the calendar event.
        :param projects_with_tasks: A list or dict structure containing projects and their tasks.
        :return: A tuple (project_id, task_id) or None if no match found.
        """
        
        # Prepare the context for the LLM
        candidates = []
        for project in projects_with_tasks:
            p_name = project['name']
            p_id = project['id']
            candidates.append(f"Project: {p_name} (ID: {p_id})")
            for task in project.get('tasks', []):
                t_name = task['name']
                t_id = task['id']
                candidates.append(f"  - Task: {t_name} (ID: {t_id})")
            candidates.append("") # Empty line between projects

        candidates_str = "\n".join(candidates)

        prompt = f"""
        You are an intelligent assistant that maps calendar events and github issues to time tracking tasks.

        Event Description: "{event_description}"

        Available Projects and Tasks:
        {candidates_str}

        Goal: Select the most appropriate Project and Task for this event.

        Guidelines:
        1. Analyze the event description to understand the work context.
        2. "Standup", "Sync", "Discussion", "Call", "Retro", "Retrospective", "Refinement", "Sprint" usually map to "Meetings" task - do not use "Meetings - external".
        3. "Update", "Upgrade", "Deploy" usually map to "Deployments" task.
        4. If it's a JIRA ticket, it shall match "Consultancy", "Support".
        5. If the event refers to "Research", "Analyse", "Investigate", falls into the "Research" task.
        6. GitHub issues usually map to "Backlog" unless they fall into the previous categories.
        7. Look for keywords in the event that match task names.

        Output Format:
        Return a JSON object with the following fields:
        - "reasoning": A brief explanation of why you chose this match.
        - "projectId": The exact alphanumeric ID of the selected project.
        - "taskId": The exact alphanumeric ID of the selected task.

        If no task fits well, return null for projectId and taskId.
        """

        # Build a lookup map for validation: task_id -> project_id
        task_to_project_map = {}
        for project in projects_with_tasks:
            p_id = project['id']
            for task in project.get('tasks', []):
                task_to_project_map[task['id']] = p_id

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)

            reasoning = result.get('reasoning', 'No reasoning provided')
            project_id = result.get('projectId')
            task_id = result.get('taskId')
            
            print(f"DEBUG: Event='{event_description}' | Reasoning: {reasoning}")

            # Validation and Correction
            if task_id:
                if task_id in task_to_project_map:
                    # If task exists, enforce the correct project ID
                    correct_project_id = task_to_project_map[task_id]
                    if project_id != correct_project_id:
                        # print(f"  -> AI Mismatch corrected: Task {task_id} belongs to Project {correct_project_id}, not {project_id}")
                        project_id = correct_project_id
                else:
                    # If task ID is not found in our list, it's invalid.
                    print(f"  -> Invalid Task ID returned by AI: {task_id}. Ignoring task.")
                    task_id = None

            return project_id, task_id

        except Exception as e:
            print(f"Error during AI matching: {e}")
            return None, None
