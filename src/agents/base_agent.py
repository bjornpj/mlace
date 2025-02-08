## src/agents/base_agent.py
import re
import json
import datetime
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