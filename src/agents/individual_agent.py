## src/agents/individual_agent.py
import re
import json
from src.agents.base_agent import Agent

# Individual Agent class
class IndividualAgent(Agent):
    def __init__(self, name, llm_interface):
        super().__init__(name)
        self.llm_interface = llm_interface
        
    def perform_task(self, task):
        task_description = task if isinstance(task, str) else task.get("description", "No description provided")
        self.communicate(f"Received task: {task_description}", level="INFO")

        prompt = f"""
        You are an IndividualAgent, a specialized expert responsible for executing the following task with precision and efficiency. Your role is to apply your deep technical expertise to ensure high-quality output while adhering to structured workflows and deadlines.

        Your Responsibilities:
        - Execute assigned tasks with a high level of technical proficiency.
        - Follow structured workflows to ensure consistency and quality.
        - Deliver work within the defined deadlines and project scope.
        - Identify potential issues or inefficiencies and provide justified recommendations for improvement.
        - Do NOT fabricate meetings, discussions, or decision-making events that did not happen.
        
        Your Authorities:
        - Flag issues if a task is infeasible, providing clear reasoning and supporting details.
        - Suggest optimizations to improve efficiency or quality, but cannot modify the project scope.
        - Ensure the work aligns with the required specifications and contributes to overall project success.
        - Now, complete the following task with accuracy and adherence to best practices:

        Task: {task_description}

        Respond in **strict JSON format** without any extra text, markdown formatting, or comments. Use only standard JSON (no inline comments or additional symbols). Your output must be exactly in the following format, with no extra characters (not even whitespace) before or after, and **must include the final closing brace**:
        {{
            "task": "{task_description}",
            "status": "completed or failed",
            "quality": 90,
            "result": "Specific outcome.",
            "remarks": "Brief explanation."
        }}
        """
        try:
            response = self.llm_interface.query(prompt)
            raw_response = response["message"]["content"].strip()
            self.communicate(f"Raw response from LLM: {raw_response}", level="DEBUG")

            # Sanitize the raw response
            sanitized_response = self.sanitize_response(raw_response)
            self.communicate(f"Sanitized response: {sanitized_response}", level="DEBUG")

            # Validate the sanitized response
            if isinstance(sanitized_response, dict):
                report = sanitized_response
            elif isinstance(sanitized_response, str):
                report = json.loads(sanitized_response)
            else:
                raise ValueError("Sanitized response is not valid JSON.")

            self.communicate(f"Task '{task_description}' completed. Report: {report}", level="INFO")
            return report
        except json.JSONDecodeError as e:
            self.communicate(f"JSON parsing failed for task '{task_description}': {e}", level="ERROR")
            return {
                "task": task_description,
                "status": "failed",
                "quality": 0,
                "result": None,
                "remarks": f"JSON decoding error: {e}"
            }
        except Exception as e:
            self.communicate(f"Error processing task '{task_description}': {e}", level="ERROR")
            return {
                "task": task_description,
                "status": "failed",
                "quality": 0,
                "result": None,
                "remarks": f"Exception occurred: {e}"
            }