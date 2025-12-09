import openai
import json
import os


class AIMatcher:
    def __init__(self, api_key, model="gpt-4o"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def batch_match_tasks(self, items, projects_with_tasks):
        """
        Matches a list of items to relevant Clockify tasks.

        :param items: List of dicts [{'id': 'unique_id', 'description': 'text'}]
        :param projects_with_tasks: A list or dict structure containing projects and their tasks.
        :return: Dict { 'unique_id': {'project_id': '...', 'task_id': '...', 'reasoning': '...'} }
        """
        if not items:
            return {}

        # Prepare the context for the LLM
        candidates = []
        for project in projects_with_tasks:
            p_name = project["name"]
            p_id = project["id"]
            candidates.append(f"Project: {p_name} (ID: {p_id})")
            for task in project.get("tasks", []):
                t_name = task["name"]
                t_id = task["id"]
                candidates.append(f"  - Task: {t_name} (ID: {t_id})")
            candidates.append("")  # Empty line between projects

        candidates_str = "\n".join(candidates)

        items_str = ""
        for item in items:
            items_str += (
                f"- ID: {item['id']} | Description: \"{item['description']}\"\n"
            )

        prompt = f"""
        You are an intelligent assistant that maps calendar events and github issues to time tracking tasks.

        Available Projects and Tasks:
        {candidates_str}

        Items to Match:
        {items_str}

        Goal: Select the most appropriate Project and Task for each item.

        Guidelines:
        1. Analyze the description to understand the work context, look for keywords in the event that match task names.
        2. "Standup", "Sync", "Discussion", "Call", "Retro", "Retrospective", "Refinement", "Sprint" usually map to "Meetings - internal" task.
        3. "Update", "Upgrade", "Deploy" usually map to "Deployments" task.
        4. If it's a JIRA ticket, map to "Consultancy", "Support" tasks.
        5. If the event refers to "Research", "Analyse", "Investigate", falls into the "Research" task.
        6. GitHub issues usually map to "Backlog" unless they fall into the previous tasks.
        7. Calendar events maps to "Meetings" unless they fall into the previous tasks.

        Output Format:
        Return a JSON object where keys are the Item IDs and values are objects with:
        - "reasoning": A brief explanation.
        - "projectId": The exact alphanumeric ID of the selected project.
        - "taskId": The exact alphanumeric ID of the selected task.
        
        Example Output:
        {{
            "item_1": {{ "reasoning": "...", "projectId": "...", "taskId": "..." }},
            "item_2": {{ "reasoning": "...", "projectId": "...", "taskId": "..." }}
        }}

        If no task fits well, return null for projectId and taskId.
        """

        # Build a lookup map for validation: task_id -> project_id
        task_to_project_map = {}
        for project in projects_with_tasks:
            p_id = project["id"]
            for task in project.get("tasks", []):
                task_to_project_map[task["id"]] = p_id

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that outputs JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            results = json.loads(content)

            final_matches = {}

            for item in items:
                item_id = item["id"]
                match = results.get(item_id)

                if not match:
                    print(f"DEBUG: No match returned for item {item_id}")
                    final_matches[item_id] = {
                        "project_id": None,
                        "task_id": None,
                        "reasoning": "No match found by AI.",
                    }
                    continue

                reasoning = match.get("reasoning", "No reasoning provided")
                project_id = match.get("projectId")
                task_id = match.get("taskId")

                # Validation and Correction
                if task_id:
                    if task_id in task_to_project_map:
                        # If task exists, enforce the correct project ID
                        correct_project_id = task_to_project_map[task_id]
                        if project_id != correct_project_id:
                            # print(f"  -> AI Mismatch corrected for {item_id}: Task {task_id} belongs to Project {correct_project_id}, not {project_id}")
                            project_id = correct_project_id
                    else:
                        # If task ID is not found in our list, it's invalid.
                        print(
                            f"  -> Invalid Task ID returned by AI for {item_id}: {task_id}. Ignoring task."
                        )
                        task_id = None

                final_matches[item_id] = {
                    "project_id": project_id,
                    "task_id": task_id,
                    "reasoning": reasoning,
                }

            return final_matches

        except Exception as e:
            print(f"Error during AI matching: {e}")
            return {}
