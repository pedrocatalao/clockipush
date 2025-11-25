import openai
import json

class AIMatcher:
    def __init__(self, api_key, model="gpt-3.5-turbo"):
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
        # We'll format the projects and tasks into a readable string
        candidates = []
        for project in projects_with_tasks:
            p_name = project['name']
            p_id = project['id']
            for task in project.get('tasks', []):
                t_name = task['name']
                t_id = task['id']
                candidates.append(f"Project: {p_name} (ID: {p_id}) | Task: {t_name} (ID: {t_id})")
            # Also consider project without task if allowed, but usually tasks are preferred
            # candidates.append(f"Project: {p_name} (ID: {p_id}) | Task: None")

        candidates_str = "\n".join(candidates)

        prompt = f"""
        You are an intelligent assistant that maps calendar events to time tracking tasks.
        
        Event Description: "{event_description}"
        
        Available Tasks:
        {candidates_str}
        
        Select the most appropriate Project and Task for this event.
        
        Guidelines:
        1. Look at the calendar event or Github issue title in context, figure out what it is about, and then put it in the correct task.
        2. "Standup", "Sync", "Discussion", "Call", "Retro", "Retrospective", "Refinement", "Sprint" usually map to task "Meetings".
        3. "Update", "Upgrade" usually map to task "Deployments".
        4. If the event is clearly a meeting (e.g. "This is a meeting"), prioritize tasks labeled "Meeting", "Communication", or "Management".
        
        Return ONLY a JSON object with "projectId" and "taskId". 
        IMPORTANT: "projectId" and "taskId" MUST be the alphanumeric IDs provided in the list (e.g., "6584..."), NOT the names.
        If no task fits well, return "projectId": null, "taskId": null.
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
                temperature=0
            )
            
            content = response.choices[0].message.content
            # Clean up potential markdown code blocks
            if content.startswith("```json"):
                content = content[7:-3]
            elif content.startswith("```"):
                content = content[3:-3]
                
            result = json.loads(content)
            project_id = result.get('projectId')
            task_id = result.get('taskId')

            # Post-processing: Extract ID if the LLM included extra text
            import re
            id_pattern = r'[a-f0-9]{24}'

            if project_id and len(project_id) > 24:
                match = re.search(id_pattern, project_id)
                if match:
                    project_id = match.group(0)
            
            if task_id and len(task_id) > 24:
                match = re.search(id_pattern, task_id)
                if match:
                    task_id = match.group(0)

            # Validation and Correction
            if task_id:
                if task_id in task_to_project_map:
                    # If task exists, enforce the correct project ID
                    correct_project_id = task_to_project_map[task_id]
                    if project_id != correct_project_id:
                        print(f"  -> AI Mismatch corrected: Task {task_id} belongs to Project {correct_project_id}, not {project_id}")
                        project_id = correct_project_id
                else:
                    # If task ID is not found in our list, it's invalid.
                    print(f"  -> Invalid Task ID returned by AI: {task_id}. Ignoring task.")
                    task_id = None

            return project_id, task_id

        except Exception as e:
            print(f"Error during AI matching: {e}")
            return None, None
