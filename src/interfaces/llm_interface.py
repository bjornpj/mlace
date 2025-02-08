## src/interfaces/llm_interface.py
class LLMInterface:
    def __init__(self, model_name):
        self.model_name = model_name

    def query(self, prompt):
        """Method to query an LLM. Replace with specific LLM API call."""
        raise NotImplementedError("Subclasses must implement this method.")
