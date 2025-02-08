## src/agents/director_agent.py
import re
import json  # Ensure this is imported
from src.agents.base_agent import Agent

# Director Agent class
class DirectorAgent(Agent):
    def __init__(self, name, manager_agents, llm_interface):
        super().__init__(name)
        self.manager_agents = manager_agents
        self.llm_interface = llm_interface

    def translate_goal_to_tasks(self, goal):
        self.communicate(f"Translating goal into tasks using LLM: {goal}", level="INFO")
        prompt = f"""
    You are a Director Agent responsible for breaking down the following high-level goal into actionable tasks for Manager Agents.

    Goal: {goal}

    ### Instructions:
    1. Analyze the task description.
    2. If it is possible to break down the task into subtasks, respond strictly as a **JSON array of strings** where each string describes a subtask.
    3. If no subtasks can be generated (e.g., the task is too vague, incomplete, or non-actionable), respond with an **empty JSON array**: [].
    4. Do not include any additional text, explanations, comments, or formatting outside the JSON array.

    Example response:
    [
        "Task 1 description",
        "Task 2 description",
        "Task 3 description"
    ]

    If you cannot generate tasks, return an empty JSON array: [].
    """
        try:
            # Call the LLM with the prompt
            response = self.llm_interface.query(prompt)
            raw_content = response["message"]["content"].strip()
            self.communicate(f"Raw response from LLM: {raw_content}", level="DEBUG")

            # Validate and parse response
            try:
                tasks = json.loads(raw_content)
                if isinstance(tasks, list) and all(isinstance(task, str) for task in tasks):
                    return tasks
                else:
                    self.communicate("Error: Invalid response format. Falling back to default tasks.", level="ERROR")
                    return []
            except json.JSONDecodeError:
                self.communicate("Error: JSON decoding failed. Falling back to default tasks.", level="ERROR")
                return []
        except Exception as e:
            self.communicate(f"Error: Failed to translate goal. {e}", level="ERROR")
            return []
            
    def generate_conclusions(self, goal, key_findings):
        """
        Generates actionable conclusions using an LLM based on task and results from summary findings.
        """
        if not key_findings:
            return "Insufficient data to generate actionable conclusions for the given goal."

        # Prepare a summary of findings for the LLM
        summary = "\n".join(
            f"- Task: {finding.get('task', 'No task description provided.')}\n"
            f"  Result: {finding.get('result', 'No specific outcome provided.')}\n"
            f"  Remarks: {finding.get('remarks', 'No remarks provided.')}\n"
            if isinstance(finding, dict) else f"- Finding: {finding}\n"
            for finding in key_findings
        )

        # Construct the LLM prompt
        prompt = f"""
        You are an expert assistant tasked with analyzing project findings and generating actionable conclusions.
        Based on the following summary of findings, generate actionable conclusions that align with the goal.

        Goal: {goal}

        Summary of Key Findings:
        {summary}

        Respond in a concise and structured format:
        - Conclusion 1: [Your first conclusion]
        - Conclusion 2: [Your second conclusion]
        - Conclusion 3: [Your third conclusion, if applicable]
        """

        # Query the LLM for conclusions
        try:
            response = self.llm_interface.query(prompt)
            raw_response = response["message"]["content"].strip()
            self.communicate(f"Raw response from LLM: {raw_response}", level="DEBUG")
           # Replace escaped newline characters and double newlines
            formatted_response = raw_response
            formatted_response = json.dumps({"recommendations": formatted_response})

            # Log the formatted response for verification
            self.communicate(f"Formatted response: {formatted_response}", level="DEBUG")

            # Return the conclusions as provided by the LLM
            return f"### Recommendations Based on Findings:\n{formatted_response}"

        except Exception as e:
            self.communicate(f"Error generating conclusions: {e}", level="ERROR")
            return "An error occurred while generating conclusions. Please check the findings and try again."

    def generate_final_report(self, synthesized_answer):
        """
        Generates a structured, well-formatted final report based on synthesized key findings and recommendations.
        """
        if not synthesized_answer or not isinstance(synthesized_answer, dict):
            self.communicate("Invalid synthesized answer provided.", level="ERROR")
            return "Error: Invalid synthesized answer."

        key_findings = synthesized_answer.get("key_findings", [])
        recommendations = synthesized_answer.get("recommendations", "")

        # Process Key Findings with Sub-Bullets
        formatted_findings = []
        for finding in key_findings:
            # Detect and format sub-bullets (using regex for indentation)
            formatted_finding = re.sub(r'\s*\*\s*', '\n        - ', finding)  # Convert `*` to bullets
            formatted_finding = re.sub(r'\s*\+\s*', '\n            * ', formatted_finding)  # Convert `+` to sub-bullets
            formatted_findings.append(f"    - {formatted_finding.strip()}")

        formatted_findings_text = "\n".join(formatted_findings)

        # Extract and format Recommendations properly
        try:
            recommendations_cleaned = re.sub(r"### Recommendations Based on Findings:\n", "", recommendations).strip()
            recommendations_json = json.loads(recommendations_cleaned)
            
            if isinstance(recommendations_json, dict) and "recommendations" in recommendations_json:
                formatted_recommendations = recommendations_json["recommendations"]
            else:
                formatted_recommendations = recommendations_cleaned  # Fallback
        except json.JSONDecodeError:
            self.communicate("Error parsing recommendations JSON. Returning raw text.", level="WARNING")
            formatted_recommendations = recommendations_cleaned  # Fallback to raw text

        # Process Recommendations with proper indentation
        formatted_recommendations = re.sub(r'\n(\d+)\.\s*', r'\n    \1. ', formatted_recommendations)  # Numbered lists
        formatted_recommendations = re.sub(r'\n\*\s*', r'\n        - ', formatted_recommendations)  # Bullet points
        formatted_recommendations = re.sub(r'\n\\t\*\s*', r'\n            * ', formatted_recommendations)  # Indent sub-bullets

        # Construct the Final Report with consistent indentation
        final_report = f"""
        ==========================================
                     FINAL INVESTMENT REPORT
        ==========================================

        **Key Findings:**
        {formatted_findings_text}

        **Recommendations:**
        {formatted_recommendations}
        """

        print(f'{final_report}')

        self.communicate("Final investment report generated successfully.", level="INFO")
        return final_report
    
    def delegate_goal(self, goal):
        self.communicate(f"Delegating goal: {goal}", level="INFO")
        all_reports = {}
        total_subtasks = 0
        completed_subtasks = 0
        total_quality = 0
        synthesized_answer = {"key_findings": [], "recommendations": ""}

        for manager in self.manager_agents:
            self.communicate(f"Delegating goal to {manager.name}", level="INFO")
            manager_tasks = [{"description": goal}]
            reports = manager.assign_task(manager_tasks[0])
            all_reports[manager.name] = reports

            for report in reports:
                total_subtasks += 1
                if report.get("status") == "completed":
                    completed_subtasks += 1
                    if "result" in report and report["result"]:
                        synthesized_answer["key_findings"].append(report["result"])
                total_quality += report.get("quality", 0)

        avg_quality = total_quality / total_subtasks if total_subtasks else 0
        overall_status = "completed" if completed_subtasks == total_subtasks else "partially completed"

        # Generate actionable conclusions
        synthesized_answer["recommendations"] = self.generate_conclusions(goal, synthesized_answer["key_findings"])

        # Final summary
        summary = {
            "goal": goal,
            "overall_status": overall_status,
            "total_subtasks": total_subtasks,
            "completed_subtasks": completed_subtasks,
            "average_quality": avg_quality,
            "reports_by_manager": all_reports,
            "synthesized_answer": synthesized_answer
        }
        self.communicate(f"Final summary of reports: {json.dumps(summary, indent=4)}", level="INFO")
        
        # Create a properly formatted Final Report
        self.generate_final_report(synthesized_answer)
        return summary
