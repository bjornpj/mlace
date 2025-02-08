## src/utils/logger.py
import datetime
from colorama import Fore, Style

def log_message(agent_name, message, color, level="INFO"):
    """Utility function to log messages with a timestamp and hierarchical structure."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{color}[{timestamp}] [{agent_name}] [{level}] {message}")
