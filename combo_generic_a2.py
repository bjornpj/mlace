import ollama
import json
import random
import re
import datetime
from colorama import Fore, Style

import subprocess

def log_message(agent_name, message, color, level="INFO"):
    """Utility function to log messages with a timestamp and hierarchical structure."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{color}[{timestamp}] [{agent_name}] [{level}] {message}")
    
# Base Agent class
class Agent:
    def __init__(self, name):
        self.name = name

    def communicate(self, message, level="INFO"):
        """
        Log a message with a specified level.
        Color-code the output: INFO=Blue, WARNING=Orange, DEBUG=Purple.
        """
        level_colors = {
 #           "INFO": Fore.GREEN,
            "SUMMARY": Fore.GREEN,  # Use yellow to simulate orange
            "WARNING": Fore.YELLOW,  # Use yellow to simulate orange
 #           "DEBUG": Fore.WHITE,
            "ERROR": Fore.RED,
        }
        color = level_colors.get(level.upper(), Fore.WHITE)  # Default to white
        reset = Style.RESET_ALL

        # Format the message
        log_message(self.name, f"[{self.name}] [{level.upper()}] {message}", color, level)
        
    def sanitize_response(self, raw_response):
        """
        Extracts and validates the first valid JSON block from the raw LLM response.
        Handles multi-line and nested JSON responses, fixes minor errors, and removes non-JSON text.
        """
        if not isinstance(raw_response, str):
            self.communicate("Raw response is not a string.", level="ERROR")
            return None

        raw_response = raw_response.strip()

        # Remove preamble text (e.g., "Here's a JSON response:")
        raw_response = re.sub(r'^[^{\[]+', '', raw_response).strip()

        # Remove possible Markdown JSON code blocks (e.g., ```json ... ```)
        raw_response = re.sub(r"```json\n(.*?)\n```", r"\1", raw_response, flags=re.DOTALL).strip()

        # Extract JSON block
        json_match = re.search(r'({.*?}|\[.*?\])', raw_response, re.DOTALL)
        if json_match:
            json_content = json_match.group(0)

            try:
                return json.loads(json_content)  # Attempt parsing
            except json.JSONDecodeError as e:
                self.communicate(f"Initial JSON parsing failed: {e}. Attempting auto-fix.", level="WARNING")

                # Try to fix common JSON formatting errors
                json_content = json_content.replace("\n", "").replace("\r", "").strip()  # Remove newlines
                json_content = re.sub(r',\s*}', '}', json_content)  # Remove trailing commas before }
                json_content = re.sub(r',\s*]', ']', json_content)  # Remove trailing commas before ]

                try:
                    return json.loads(json_content)  # Reattempt parsing
                except json.JSONDecodeError as e2:
                    self.communicate(f"JSON repair failed: {e2}", level="ERROR")
        
        self.communicate("No valid JSON block found in the response.", level="ERROR")
        return None
 
class LLMInterface:
    def __init__(self, model_name):
        self.model_name = model_name

    def query(self, prompt):
        """Method to query an LLM. Replace with specific LLM API call."""
        raise NotImplementedError("Subclasses must implement this method.")


class OllamaInterface(LLMInterface):
    def query(self, prompt):
        try:
            response = ollama.chat(model=self.model_name, messages=[{"role": "user", "content": prompt}])
            raw_content = response.get("message", {}).get("content", "")
            print(f"{Fore.MAGENTA}[LLMInterface] [DEBUG] Prompt: {prompt}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}[LLMInterface] [DEBUG] Raw response: {raw_content}{Style.RESET_ALL}")
            return response
        except Exception as e:
            print(f"{Fore.RED}[LLMInterface] [ERROR] Failed to query LLM: {e}{Style.RESET_ALL}")
            raise
 
 
# Individual Agent class
class IndividualAgent(Agent):
    def __init__(self, name, llm_interface):
        super().__init__(name)
        self.llm_interface = llm_interface
        
    def perform_task(self, task):
        task_description = task if isinstance(task, str) else task.get("description", "No description provided")
        self.communicate(f"Received task: {task_description}", level="INFO")

        prompt = f"""
        You are an Individual Agent responsible for completing the following task:

        Task: {task_description}

        Respond in JSON format:
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
            
class OSAgent(IndividualAgent):
    def __init__(self, name, llm_interface):
        super().__init__(name, llm_interface)
        
    def perform_task(self, task):
        """
        Handles tasks requiring OS-level operations. Executes commands generated by the LLM.
        """
        task_description = task if isinstance(task, str) else task.get("description", "No description provided")
        self.communicate(f"Received task: {task_description}", level="INFO")

        prompt = f"""
        You are an OS Agent capable of solving tasks using Python, Shell or Cmd on Win11 OS.
        Analyze the following task and generate the appropriate command or script to execute it programmatically.

        Task: {task_description}

        Respond strictly in JSON format:
        {{
            "command_type": "python|shell|cmd",
            "command": "The command or script to execute the task",
            "remarks": "Explanation of the command if needed"
        }}
        """
        try:
            response = self.llm_interface.query(prompt)
            raw_response = response["message"]["content"].strip()
            self.communicate(f"Raw response from LLM: {raw_response}", level="DEBUG")

            # Sanitize and parse the response
            sanitized_response = self.sanitize_response(raw_response)
            if not sanitized_response or not isinstance(sanitized_response, dict):
                raise ValueError("Sanitized response is empty or invalid.")

            # Extract command details
            command_type = sanitized_response.get("command_type")
            command = sanitized_response.get("command")
            remarks = sanitized_response.get("remarks", "No remarks provided.")

            # Fix incorrect command types
            if command_type == "python" and not self.is_valid_python(command):
                self.communicate(f"Invalid Python command detected. Switching to default Python command.", level="WARNING")
                command = "import datetime; print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))"

            if command_type == "shell" or command_type == "cmd":
                command = self.fix_escape_sequences(command)

            self.communicate(f"Generated command: {command} ({command_type})", level="INFO")

            # Execute the command
            if command_type == "python":
                old_stdout = sys.stdout  # Define `old_stdout` before the try block
                sys.stdout = io.StringIO()  # Redirect stdout to capture execution output

                try:
                    exec(command, globals())  # Execute the command

                    # Retrieve the execution result
                    output = sys.stdout.getvalue().strip()
                except Exception as e:
                    output = f"Error: {e}"
                    self.communicate(f"Python command execution failed: {e}", level="ERROR")
                finally:
                    sys.stdout = old_stdout  # Restore stdout no matter what

                self.communicate(f"Python command executed successfully. Output: {output}", level="INFO")
                return {
                    "task": task_description,
                    "status": "completed" if "Error" not in output else "failed",
                    "quality": 100 if "Error" not in output else 0,
                    "result": output if output else "Python command executed with no output.",
                    "remarks": remarks
                }            
            elif command_type in ["shell", "cmd"]:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                output = result.stdout.strip()
                error = result.stderr.strip()
                if result.returncode == 0:
                    self.communicate(f"Command executed successfully. Output: {output}", level="INFO")
                    return {
                        "task": task_description,
                        "status": "completed",
                        "quality": 100,
                        "result": output,
                        "remarks": remarks
                    }
                else:
                    self.communicate(f"Command failed. Error: {error}", level="ERROR")
                    return {
                        "task": task_description,
                        "status": "failed",
                        "quality": 0,
                        "result": None,
                        "remarks": error
                    }
            else:
                self.communicate("Unsupported command type.", level="ERROR")
                return {
                    "task": task_description,
                    "status": "failed",
                    "quality": 0,
                    "result": None,
                    "remarks": "Unsupported command type."
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

    def is_valid_python(self, command):
        """
        Checks if the provided command is valid Python code.
        """
        try:
            compile(command, "<string>", "exec")
            return True
        except SyntaxError:
            return False

    def fix_escape_sequences(self, command):
        """
        Fixes incorrect escape sequences in shell and cmd commands.
        """
        # Replace incorrect "\%" with "%"
        command = re.sub(r'\\%', '%', command)
        
        # Ensure proper formatting for Windows CMD (double up %% for batch)
        if "cmd" in command:
            command = command.replace("%", "%%")
        
        return command
            
           
# Manager Agent class
class ManagerAgent(Agent):
    def __init__(self, name, individual_agents, os_agent, llm_interface):
        super().__init__(name)
        self.individual_agents = individual_agents
        self.os_agent = os_agent  # Add this line to store the OSAgent reference
        self.llm_interface = llm_interface

    def translate_task_to_subtasks(self, task):
        self.communicate(f"Translating task: {task}", level="INFO")
        prompt = f"""
        You are a Manager Agent responsible for breaking down the following task into actionable subtasks.

        Task: {task}

        Respond strictly as a JSON array of strings. Do not include any additional text, explanations, or comments.

        Example response:
        [
            "Subtask 1 description",
            "Subtask 2 description",
            "Subtask 3 description"
        ]

        If you cannot generate subtasks, return an empty JSON array: []. 
        """
        try:
            self.communicate(f"Prompt sent to LLM: {prompt}", level="DEBUG")
            response = self.llm_interface.query(prompt)
            raw_response = response["message"]["content"].strip()
            self.communicate(f"Raw response from LLM: {raw_response}", level="DEBUG")

            subtasks = self.sanitize_response(raw_response)
            if subtasks:
                self.communicate(f"Extracted subtasks: {subtasks}", level="INFO")
                return subtasks

            self.communicate("Error: Failed to extract valid subtasks. Retrying...", level="WARNING")
        except Exception as e:
            self.communicate(f"Exception during task translation: {e}", level="ERROR")

        # Retry with simplified prompt
        simplified_prompt = f"Break down the task: {task} into 3 actionable subtasks in JSON array format."
        try:
            self.communicate("Retrying with simplified prompt...", level="WARNING")
            response = self.llm_interface.query(simplified_prompt)
            raw_retry_response = response["message"]["content"].strip()
            self.communicate(f"Raw retry response: {raw_retry_response}", level="DEBUG")
            subtasks = self.sanitize_response(raw_retry_response)
            if subtasks:
                self.communicate(f"Extracted subtasks from retry: {subtasks}", level="INFO")
                return subtasks
        except Exception as e:
            self.communicate(f"Retry failed with exception: {e}", level="ERROR")

        # Final fallback
        self.communicate("Falling back to hardcoded subtasks.", level="WARNING")
        return ["Analyze portfolio performance", "Research growth stocks for 2025", "Develop risk mitigation strategies"]
       
    def classify_task(self, task):
        """
        Classify the task as either 'programmatic' or 'general' using the LLM.
        """
        self.communicate(f"Classifying task: {task}", level="INFO")
        prompt = f"""
        You are an intelligent assistant. Analyze the following task description and classify it into one of the following categories:
        - 'programmatic': Tasks requiring execution of code (e.g., Python, Shell, or Cmd scripts).
        - 'general': Conceptual or analytical tasks that do not involve coding or system-level operations.

        Task: {task}

        Respond strictly in JSON format:
        {{
            "task_type": "programmatic|general",
            "reason": "Brief explanation of why the task is classified this way."
        }}
        """
        try:
            response = self.llm_interface.query(prompt)
            raw_response = response["message"]["content"].strip()
            self.communicate(f"Raw classification response: {raw_response}", level="DEBUG")

            # Sanitize and parse response
            classification = self.sanitize_response(raw_response)
            if classification and "task_type" in classification:
                self.communicate(f"Task classified as: {classification['task_type']}", level="INFO")
                return classification["task_type"]
            else:
                self.communicate("Classification failed. Defaulting to 'general'.", level="WARNING")
                return "general"
        except Exception as e:
            self.communicate(f"Error classifying task: {e}", level="ERROR")
            return "general"
            
    def assign_task(self, task):
        """
        Assigns tasks based on their classification ('programmatic' or 'general').
        """
        subtasks = self.translate_task_to_subtasks(task)
        if not subtasks:
            self.communicate(f"No subtasks generated for task '{task}'. Using fallback.", level="WARNING")
            return []

        self.communicate(f"Assigning subtasks: {subtasks}", level="INFO")
        reports = []

        for subtask in subtasks:
            # Classify the subtask
            task_type = self.classify_task(subtask)

            if task_type == "programmatic":
                self.communicate(f"Assigning programmatic subtask '{subtask}' to {self.os_agent.name}", level="INFO")
                report = self.os_agent.perform_task(subtask)
            else:
                individual_agent = random.choice(self.individual_agents)
                self.communicate(f"Assigning general subtask '{subtask}' to {individual_agent.name}", level="INFO")
                report = individual_agent.perform_task(subtask)

            # Collect the report
            reports.append(report)

        return reports
                 
        
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

            
        
# Example usage
if __name__ == "__main__":
    llm = OllamaInterface("llama3.2")
#    llm = OllamaInterface("deepseek-r1:1.5b")
    individual_agents = [IndividualAgent(f"IndividualAgent-{i}", llm) for i in range(6)]
    os_agent = OSAgent("OSAgent", llm)
    manager_agents = [ManagerAgent(f"ManagerAgent-{i}", individual_agents, os_agent, llm) for i in range(3)]
    director = DirectorAgent("DirectorAgent", manager_agents, llm)

    goal = "Develop a investment strategy which yeild in 10%-15% returns at lowest possible risk. For each recommendation provide up to 3 proposed tickers."
#    goal = "Creat an action plan which reduces global warming with more than 2C."
#    goal = "Display current date and time of local machine."
#    goal = "List all txt files in current directory in Python."
    director.delegate_goal(goal)
