## src/agents/base_agent.py
import re
import json
import datetime
import sys, io
from colorama import Fore, Style
from src.utils.logger import log_message

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
        Also, if the final closing bracket is missing, it appends it before parsing.
        """
        if not isinstance(raw_response, str):
            self.communicate("Raw response is not a string.", level="ERROR")
            return None

        raw_response = raw_response.strip()

        # Remove preamble text (e.g., "Here's a JSON response:")
        raw_response = re.sub(r'^[^{\[]+', '', raw_response).strip()

        # Remove possible Markdown JSON code blocks (e.g., ```json ... ```)
        raw_response = re.sub(r"```json\n(.*?)\n```", r"\1", raw_response, flags=re.DOTALL).strip()

        # Attempt to locate the JSON block manually by finding the first occurrence of '{' or '['
        first_curly = raw_response.find('{')
        first_square = raw_response.find('[')
        if first_curly == -1 and first_square == -1:
            self.communicate("No valid JSON block found in the response.", level="ERROR")
            return None

        # Determine the starting index (whichever comes first)
        if first_curly == -1:
            start = first_square
        elif first_square == -1:
            start = first_curly
        else:
            start = min(first_curly, first_square)

        # Determine the type of JSON block and locate its closing bracket
        if raw_response[start] == '{':
            end = raw_response.rfind('}')
            if end == -1 or end < start:
                # Append missing closing brace
                raw_response += '}'
                end = raw_response.rfind('}')
        elif raw_response[start] == '[':
            end = raw_response.rfind(']')
            if end == -1 or end < start:
                # Append missing closing bracket
                raw_response += ']'
                end = raw_response.rfind(']')
        else:
            self.communicate("No valid JSON block found in the response.", level="ERROR")
            return None

        json_content = raw_response[start:end+1]

        # Attempt to parse the JSON content
        try:
            return json.loads(json_content)
        except json.JSONDecodeError as e:
            self.communicate(f"Initial JSON parsing failed: {e}. Attempting auto-fix.", level="WARNING")
            # Remove newlines and carriage returns
            json_content = json_content.replace("\n", "").replace("\r", "").strip()
            # Remove trailing commas before } and ]
            json_content = re.sub(r',\s*}', '}', json_content)
            json_content = re.sub(r',\s*]', ']', json_content)
            try:
                return json.loads(json_content)
            except json.JSONDecodeError as e2:
                self.communicate(f"JSON repair failed: {e2}", level="ERROR")

        self.communicate("No valid JSON block found in the response.", level="ERROR")
        return None