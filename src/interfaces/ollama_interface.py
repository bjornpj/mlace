## src/interfaces/ollama_interface.py
import ollama
from src.interfaces.llm_interface import LLMInterface
from colorama import Fore, Style

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