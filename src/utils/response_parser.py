## src/utils/response_parser.py
import json
import re

def extract_json(agent, raw_response):
    if not isinstance(raw_response, str):
        agent.communicate("Response is not a string.", level="ERROR")
        return None

    json_match = re.search(r'({.*?}|\[.*?\])', raw_response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            agent.communicate(f"JSON parsing failed: {e}", level="ERROR")
    return None
