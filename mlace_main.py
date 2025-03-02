import os
import yfinance as yf
import json
import ollama
import requests
import time
import datetime
import re
import hashlib
import concurrent.futures
from colorama import Fore, Style

# Import the domain agent functions
from domain_agent import Session, reset_context

# Load configuration settings
with open("config.json", "r") as config_file:
    SETTINGS = json.load(config_file)

CONFIDENCE_THRESHOLD = SETTINGS.get("confidence_threshold", 85)
MAX_REFINEMENT_ATTEMPTS = SETTINGS.get("max_refinement_attempts", 4)
MAX_CONFIDENCE_ITERATIONS = SETTINGS.get("max_confidence_iterations", 5)

# Ollama API Wrapper with robust error handling
class OllamaInterface:
#    def __init__(self, model="deepseek-r1", temperature=0.1):
    def __init__(self, model="llama3.2", temperature=0.1):
        self.model = model

    def query(self, prompt):
        try:
            response = ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}])
            raw_content = response.get("message", {}).get("content", "")
            print(f"{Fore.MAGENTA}[LLM Query] {prompt[:200]}...{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}[LLM Response] {raw_content[:200]}...{Style.RESET_ALL}")
            return raw_content
        except Exception as e:
            print(f"{Fore.RED}[ERROR in OllamaInterface] {e}{Style.RESET_ALL}")
            return "ERROR"

# In the base Agent class, add a method to update internal state from feedback
class Agent:
    def __init__(self, name, role, prompt_template):
        self.name = name
        self.role = role
        self.prompt_template = prompt_template
        self.interface = OllamaInterface()
        self.output = None
        self.improvement_history = []  # Track improvements over time

    def execute(self, problem_statement, context=""):
        prompt = self.prompt_template.format(problem=problem_statement, context=context)
        try:
            self.output = self.interface.query(prompt)
        except Exception as e:
            print(f"{Fore.RED}[{self.name} ERROR] {e}{Style.RESET_ALL}")
            self.output = "ERROR"
        return self.output

    def update_from_feedback(self, refined_response, evaluator_feedback):
        """
        Update the agent's prompt_template (or internal state) based on feedback.
        This could involve appending clarifications or adjustments to the prompt.
        """
        # Example: Append a note to the prompt template to guide future responses.
        feedback_note = f"\n\n[Feedback Update]: {evaluator_feedback.strip()}"
        if feedback_note not in self.prompt_template:
            self.prompt_template += feedback_note
            self.improvement_history.append(feedback_note)
            print(f"{Fore.GREEN}[{self.name}] Prompt template updated with feedback.{Style.RESET_ALL}")
        else:
            print(f"{Fore.CYAN}[{self.name}] Feedback already integrated.{Style.RESET_ALL}")

# Base Agent Class
class Agent_old:
    def __init__(self, name, role, prompt_template):
        self.name = name
        self.role = role
        self.prompt_template = prompt_template
        self.interface = OllamaInterface()
        self.output = None

    def execute(self, problem_statement, context=""):
        prompt = self.prompt_template.format(problem=problem_statement, context=context)
        try:
            self.output = self.interface.query(prompt)
        except Exception as e:
            print(f"{Fore.RED}[{self.name} ERROR] {e}{Style.RESET_ALL}")
            self.output = "ERROR"
        return self.output

# PromptRefinerAgent: iteratively refines the problem statement
class PromptRefinerAgent(Agent):
    def refine_problem_statement(self, original_problem, max_attempts=MAX_REFINEMENT_ATTEMPTS):
        refined_problem = original_problem
        confidence_score = 50  # Default to 50% if no score is extracted

        for attempt in range(max_attempts):
            print(f"{Fore.YELLOW}[PromptRefinerAgent] Refinement Attempt {attempt+1}/{max_attempts}{Style.RESET_ALL}")

            # Explicitly ask the LLM to provide a confidence score in its response
            prompt = f"""
            Refine the following problem statement to improve clarity, specificity, and completeness.
            
            **Original Problem Statement:**
            {refined_problem}
            
            After refinement, provide:
            1. The improved problem statement.
            2. A **confidence score (0-100%)** indicating how well the refinement improves clarity, specificity, and completeness.

            **Response Format:**
            ```
            Refined Problem Statement: [Your refined statement here]
            Confidence Score: [X%]
            ```
            """

            llm_response = self.interface.query(prompt)

            # Extract confidence score and refined statement
            refined_problem, extracted_confidence = self.extract_confidence_score(llm_response)

            if extracted_confidence >= CONFIDENCE_THRESHOLD:
                print(f"{Fore.GREEN}[PromptRefinerAgent] Confidence {extracted_confidence}% → Final Refinement Achieved.{Style.RESET_ALL}")
                return refined_problem, extracted_confidence

            if refined_problem.strip() == original_problem.strip():
                print(f"{Fore.CYAN}[PromptRefinerAgent] No significant refinement detected. Stopping early.{Style.RESET_ALL}")
                return refined_problem, extracted_confidence

        print(f"{Fore.RED}[PromptRefinerAgent] Max Refinement Attempts Reached. Using Best Version.{Style.RESET_ALL}")
        return refined_problem, extracted_confidence

    @staticmethod
    def extract_confidence_score(response_text):
        """Extracts confidence score from LLM response."""
        try:
            # Match confidence score in the format: Confidence Score: 85%
            match = re.search(r"Confidence Score:\s*([0-9]+(?:\.[0-9]+)?)%", response_text, re.IGNORECASE)
            if match:
                score = float(match.group(1))
                return response_text.replace(match.group(0), "").strip(), min(max(int(score), 0), 100)  # Normalize to 0-100 range
        except Exception as e:
            print(f"{Fore.RED}[Extract Confidence Error] {e}{Style.RESET_ALL}")

        return response_text.strip(), 50  # Default to 50% if extraction fails



class PromptRefinerAgent_old(Agent):
    def refine_problem_statement(self, original_problem, max_attempts=MAX_REFINEMENT_ATTEMPTS):
        refined_problem = original_problem
        confidence_score = 50
        for attempt in range(max_attempts):
            print(f"{Fore.YELLOW}[PromptRefinerAgent] Refinement Attempt {attempt+1}/{max_attempts}{Style.RESET_ALL}")
            new_refinement = self.interface.query(self.prompt_template.format(problem=refined_problem))
#            print(f"..........{new_refinement}")
            confidence_score = self.extract_confidence_score(new_refinement)
            if confidence_score >= CONFIDENCE_THRESHOLD:
                print(f"{Fore.GREEN}[PromptRefinerAgent] Confidence {confidence_score}% → Final Refinement Achieved.{Style.RESET_ALL}")
                return new_refinement, confidence_score
            if new_refinement.strip() == refined_problem.strip():
                print(f"{Fore.CYAN}[PromptRefinerAgent] No significant refinement detected. Stopping early.{Style.RESET_ALL}")
                return refined_problem, confidence_score
            refined_problem = new_refinement
        print(f"{Fore.RED}[PromptRefinerAgent] Max Refinement Attempts Reached. Using Best Version.{Style.RESET_ALL}")
        return refined_problem, confidence_score
        
    @staticmethod
    def extract_confidence_score(response_text):
        """Extracts confidence score from evaluation text output."""
        patterns = [
            r"\*\*Confidence Score:\*\*\s*([0-9]+(?:\.[0-9]+)?)/10",
            r"Confidence\s*Score\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, response_text)
            if match:
                return min(max(int(float(match.group(1)) * 10), 0), 100)
#        print(f"..............{match} {response_text} ")
        return 50  # Default to 50 if extraction fails
    
    @staticmethod
    def extract_confidence_score_old(response_text):
        try:
            match = re.search(r'Confidence\s*Score\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)', response_text, re.IGNORECASE)
            if match:
                score = float(match.group(1))
                return min(max(int(score), 0), 100)
        except Exception as e:
            print(f"{Fore.RED}[Extract Confidence Error] {e}{Style.RESET_ALL}")
        return 50

# ResearchAgent with enhanced delegation logic and dynamic mapping (#1)
class ResearchAgent(Agent):
    def __init__(self, name, role, prompt_template):
        super().__init__(name, role, prompt_template)
        self.specialized_agents = {}
        
    def decide_specialized_agents(self, problem_statement, context=""):
        mapping_prompt = (
            "You are an expert in agent specialization. Given the following problem statement:\n"
            f"{problem_statement}\n\n"
            "And the following domain context: 'This problem is about clinical operational improvement (e.g., reducing discharge time at a level 1 trauma center)'.\n"
            "From the following agent options: ResearchAgentFinance, MacroeconomicAgent, none, decide which specialized agents are needed for additional real-time data lookup. "
            "Return your answer as a JSON object with keys 'finance' and 'macro' where the value is either 'yes' or 'no'. "
            "Ensure the output is **pure JSON** with no additional formatting, explanations, or backticks. Do NOT enclose the response in triple backticks or markdown."
        )
        mapping_response = self.interface.query(mapping_prompt)
        print(f"{Fore.CYAN}[ResearchAgent] Dynamic mapping response: {mapping_response}{Style.RESET_ALL}")
        try:
            decision = json.loads(mapping_response)
        except Exception as e:
            print(f"{Fore.RED}[Mapping Error] Could not parse mapping response: {e}{Style.RESET_ALL}")
            decision = {"finance": "no", "macro": "no"}
        
        # Always include ResearchAgent itself
        agent_list = ["ResearchAgent"]
        
        if decision.get("finance", "no").lower() == "yes":
            agent_list.append("ResearchAgentFinance")
        if decision.get("macro", "no").lower() == "yes":
            agent_list.append("MacroeconomicAgent")
        
        # Always include core agents needed for overall solution development
        agent_list.extend(["DirectorAgent", "SolutionArchitectAgent", "CommunicatorAgent", "EvaluatorAgent", "ResponseCritiqueAgent"])
        print(f"{Fore.CYAN}[ResearchAgent] Dynamically selected agents: {agent_list}{Style.RESET_ALL}")
        return agent_list
        
    def execute(self, problem_statement, context=""):
        enriched_context = (f"{context}\n\n🔍 Gather insights from at least three credible sources. "
                            "Present key trends and comparisons using bullet points or tables for clarity.")
        generic_response = super().execute(problem_statement, enriched_context)
        selected_agents = self.decide_specialized_agents(problem_statement, context)
        additional_insights = ""
        if "ResearchAgentFinance" in selected_agents:
            if "ResearchAgentFinance" not in self.specialized_agents:
                self.specialized_agents["ResearchAgentFinance"] = ResearchAgentFinance(
                    "ResearchAgentFinance",
                    "Financial Research Analyst",
                    ("You are a financial research analyst. Your task is to research the following problem: {problem}\n\n"
                     "Context: {context}\n\nCompare metrics from at least three credible sources, using bullet points or tables where possible.")
                )
            finance_response = self.specialized_agents["ResearchAgentFinance"].execute(problem_statement, context)
            additional_insights += f"\n\n🔹 **Financial Insights:**\n- {finance_response.replace(chr(10), chr(10)+'- ')}"
        if "MacroeconomicAgent" in selected_agents:
            if "MacroeconomicAgent" not in self.specialized_agents:
                self.specialized_agents["MacroeconomicAgent"] = MacroeconomicAgent(
                    "MacroeconomicAgent",
                    "Macroeconomic Analyst",
                    ("You are a macroeconomic analyst. Your task is to fetch and analyze real-time economic indicators for the following problem: {problem}\n\n"
                     "Context: {context}\n\nEmphasize trends and provide actionable comparisons.")
                )
            macro_response = self.specialized_agents["MacroeconomicAgent"].execute(problem_statement, context)
            additional_insights += f"\n\n🔹 **Macroeconomic Insights:**\n- {macro_response.replace(chr(10), chr(10)+'- ')}"
        final_response = f"{generic_response}\n\n{additional_insights}"
        return final_response

# ResearchAgentFinance uses Yahoo Finance to fetch market data
class ResearchAgentFinance(Agent):
    def execute(self, problem_statement, context=""):
        external_data = self.fetch_market_data()
        enriched_context = f"{context}\n\n🔹 Real-time Market Data:\n{external_data}"
        return super().execute(problem_statement, enriched_context)

    def fetch_market_data(self):
        market_data = {}
        try:
            indices = {
                "S&P 500": "^GSPC",
                "NASDAQ": "^IXIC",
                "Dow Jones": "^DJI",
                "Russell 2000": "^RUT",
                "FTSE 100": "^FTSE",
                "DAX": "^GDAXI"
            }
            for name, ticker in indices.items():
                stock = yf.Ticker(ticker)
                history = stock.history(period="1d")
                market_data[name] = {"Current Price": history["Close"].iloc[-1] if not history.empty else "Unavailable"}
            treasury_yields = {
                "US 10Y Treasury Yield": "^TNX",
                "US 30Y Treasury Yield": "^TYX",
                "US 5Y Treasury Yield": "^FVX"
            }
            for name, ticker in treasury_yields.items():
                bond = yf.Ticker(ticker)
                history = bond.history(period="1d")
                market_data[name] = {"Current Yield (%)": history["Close"].iloc[-1] if not history.empty else "Unavailable"}
        except Exception as e:
            print(f"{Fore.YELLOW}[ResearchAgentFinance] Failed to fetch data: {e}{Style.RESET_ALL}")
            market_data = {"Stock Market": "Unavailable", "Inflation Rate": "Unknown", "Bond Yields": "Unavailable"}
        return market_data

# MacroeconomicAgent fetches and analyzes macroeconomic indicators
class MacroeconomicAgent(Agent):
    def execute(self, problem_statement, context=""):
        macro_data = self.fetch_macro_data()
        enriched_context = f"{context}\n\n🔹 Real-time Macroeconomic Data:\n{macro_data}"
        return super().execute(problem_statement, enriched_context)

    def fetch_macro_data(self):
        indicators = {
            "US Inflation Rate": "^IRX",
            "US GDP Growth": "^DJI",
            "US Interest Rates": "^TNX",
            "Unemployment Rate": "^IXIC"
        }
        macro_info = {}
        try:
            for indicator, symbol in indicators.items():
                macro = yf.Ticker(symbol)
                history = macro.history(period="1d")
                macro_info[indicator] = history["Close"].iloc[-1] if not history.empty else "Unavailable"
            return macro_info
        except Exception as e:
            return f"⚠️ Failed to fetch macroeconomic data: {e}"

class DirectorAgent(Agent):
    def execute(self, problem_statement, context=""):
        print(f"{Fore.BLUE}[{self.name}] Executing DirectorAgent...{Style.RESET_ALL}")
        return super().execute(problem_statement, context)

class SolutionArchitectAgent(Agent):
    def execute(self, problem_statement, context=""):
        print(f"{Fore.BLUE}[{self.name}] Executing SolutionArchitectAgent...{Style.RESET_ALL}")
        return super().execute(problem_statement, context)

class CommunicatorAgent(Agent):
    def execute(self, problem_statement, context=""):
        print(f"{Fore.BLUE}[{self.name}] Executing CommunicatorAgent...{Style.RESET_ALL}")
        return super().execute(problem_statement, context)

# ResponseCritiqueAgent refines responses if needed
class ResponseCritiqueAgent(Agent):
    def execute(self, agent_name, agent_response):
        critique_prompt = f"""
        Evaluate the response from {agent_name} for clarity, completeness, and alignment with the problem statement.
        If necessary, refine it to be more actionable and specific.

        **Original Response:**
        {agent_response}

        **Refined Response:** (Ensure this is the final improved version)
        """
        refined_response = self.interface.query(critique_prompt)
        if str(refined_response).strip() != str(agent_response).strip():
#    if refined_response.strip() != agent_response.strip():
            print(f"{Fore.GREEN}✅ {agent_name} Response Optimized!{Style.RESET_ALL}")
            return refined_response
        return agent_response  # If no improvement, return original

class ResponseCritiqueAgent_old(Agent):
    def execute(self, agent_name, agent_response):
        critique_prompt = f"""
        Evaluate the response from {agent_name} for clarity, completeness, and alignment with the problem statement.
        If necessary, refine it to be more actionable and specific.

        Original Response:
        {agent_response}

        Refined Response:
        """
        refined_response = self.interface.query(critique_prompt)
        if str(refined_response).strip() != str(agent_response).strip():
#        if refined_response.strip() == agent_response.strip():
            print(f"{Fore.CYAN}ℹ️ No meaningful refinement needed for {agent_name}.{Style.RESET_ALL}")
            return agent_response
        return refined_response

# EvaluatorAgent assesses responses and returns a confidence score
class EvaluatorAgent(Agent):
    def execute(self, agent_name, agent_response, problem_statement):
        evaluation_prompt = f"""
        You are an evaluation expert. Your task is to assess the response provided by {agent_name}
        in relation to the original problem statement.

        **Problem Statement:** {problem_statement}
        **Agent Response:** {agent_response}

        Provide the evaluation in the following structured format:

        **Evaluation**

        *   **Accuracy:** X/10
            Explanation of accuracy assessment.
        *   **Completeness:** X/10
            Explanation of completeness assessment.
        *   **Improvements:**
            *   Specific improvement 1
            *   Specific improvement 2
            *   Specific improvement 3
        *   **Confidence Score:** X/10

        Ensure that the Confidence Score is always provided in the format **X/10** for accurate parsing.
        """
        evaluation_output = self.interface.query(evaluation_prompt)
        print(f"{Fore.YELLOW}[EvaluatorAgent] Evaluation for {agent_name}:\n{evaluation_output}{Style.RESET_ALL}")
        return evaluation_output
        


def extract_agents(llm_response):
    """Extract agent names reliably from LLM responses by applying filtering rules."""
    valid_agents = {"ResearchAgent", "ResearchAgentFinance", "MacroeconomicAgent",
                    "DirectorAgent", "SolutionArchitectAgent", "CommunicatorAgent",
                    "EvaluatorAgent", "ResponseCritiqueAgent"}

    found_agents = set()
    response_variants = llm_response.lower().split(",")  # Normalize text and split

    for agent in response_variants:
        agent = agent.strip()
        if agent in valid_agents:
            found_agents.add(agent)

    # Apply consistency rule: Always include core agents
    core_agents = {"ResearchAgent", "DirectorAgent"}
    found_agents.update(core_agents)

    print(f"{Fore.CYAN}[Dynamic Mapping] Extracted Agents (Filtered): {sorted(found_agents)}{Style.RESET_ALL}")
    return sorted(found_agents)

        
def extract_agents_old(llm_response):
    # Load the full list of valid agent names from your config
    with open("agents_config.json", "r") as f:
        agent_configs = json.load(f)
    valid_agents = set(agent_configs.keys())
    
    # Initialize an empty set for found agent names
    found_agents = set()
    
    # For each valid agent, check if its name appears in the LLM response (case-insensitive)
    for agent in valid_agents:
        pattern = re.compile(r"\b" + re.escape(agent) + r"\b", re.IGNORECASE)
        if pattern.search(llm_response):
            found_agents.add(agent)
    
    found_list = list(found_agents)
    print(f"{Fore.CYAN}[Dynamic Mapping] Extracted Agents: {found_list}{Style.RESET_ALL}")
    return found_list

def get_dynamic_agent_mapping(problem_statement, domain="General"):
    domain_exclusions = SETTINGS.get("domain_exclusions", {})
    exclusions = domain_exclusions.get(domain, [])
    
    prompt = (
        "Based on the following problem statement and domain context, list the names of the specialized agents that should be engaged. "
        "Available agent types include: ResearchAgent, ResearchAgentFinance, MacroeconomicAgent, DirectorAgent, SolutionArchitectAgent, CommunicatorAgent, EvaluatorAgent, and ResponseCritiqueAgent. "
        "Exclude agents not relevant to the domain. "
        f"Domain: {domain}\n"
        f"Problem Statement: {problem_statement}\n"
        "**Response Format:**"
        "Return ONLY a comma-separated list of agent names, with NO additional text or explanations."
        "Example:"
        "ResearchAgent, ResearchAgentFinance, MacroeconomicAgent"
        "Your response:"
    )
    
    interface = OllamaInterface()
    response = interface.query(prompt)
    agent_list = [name.strip() for name in response.split(",") if name.strip()]
    filtered_agent_list = [agent for agent in agent_list if agent not in exclusions]
    print(f"{Fore.CYAN}[Dynamic Mapping] Agents recommended by LLM after filtering: {filtered_agent_list}{Style.RESET_ALL}")
    return filtered_agent_list

# MultiAgentSystem Controller orchestrates agent execution
class MultiAgentSystem:
    def __init__(self, config_file="agents_config.json"):
        self.agents = {}
        self.domain_agent_mapping = {}
        self.load_agents(config_file)
        self.agent_cache = {}  # Cache agent selection for problem statements
       # Create an initial session with a dynamic domain.
        from domain_agent import Session, reset_context
        self.session = Session(session_id="session_001", domain="Dynamic")
        reset_context(self.session)

    def hash_problem_statement(self, problem_statement):
        """Generate a unique hash for a given problem statement."""
        return hashlib.sha256(problem_statement.encode()).hexdigest()

    def get_dynamic_agent_mapping(self, problem_statement, domain="General"):
        """Retrieve agents based on problem statement; use cache if available."""
        problem_hash = self.hash_problem_statement(problem_statement)

        if problem_hash in self.agent_cache:
            return self.agent_cache[problem_hash]

        prompt = (
            "Based on the following problem statement and domain context, list the names of the specialized agents that should be engaged. "
            "Available agent types include: ResearchAgent, ResearchAgentFinance, MacroeconomicAgent, DirectorAgent, SolutionArchitectAgent, CommunicatorAgent, EvaluatorAgent, and ResponseCritiqueAgent. "
            "Return ONLY a comma-separated list of agent names, with NO additional text."
            f"Problem Statement: {problem_statement}\n"
        )
        
        interface = OllamaInterface()
        response = interface.query(prompt)
        agent_list = [name.strip() for name in response.split(",") if name.strip()]
        
        # Store selection in cache
        self.agent_cache[problem_hash] = agent_list
        return agent_list

    def load_agents(self, config_file):
        with open(config_file, "r") as f:
            agent_configs = json.load(f)
        for name, details in agent_configs.items():
            if name in ["MacroeconomicAgent", "ResearchAgentFinance"]:
                continue
            if name == "ResponseCritiqueAgent":
                self.agents[name] = ResponseCritiqueAgent(name, details["role"], details["prompt_template"])
            elif name == "EvaluatorAgent":
                self.agents[name] = EvaluatorAgent(name, details["role"], details["prompt_template"])
            elif name == "PromptRefinerAgent":
                self.agents[name] = PromptRefinerAgent(name, details["role"], details["prompt_template"])
            elif name == "ResearchAgent":
                self.agents[name] = ResearchAgent(name, details["role"], details["prompt_template"])
            elif name == "DirectorAgent":
                self.agents[name] = DirectorAgent(name, details["role"], details["prompt_template"])
            elif name == "SolutionArchitectAgent":
                self.agents[name] = SolutionArchitectAgent(name, details["role"], details["prompt_template"])
            elif name == "CommunicatorAgent":
                self.agents[name] = CommunicatorAgent(name, details["role"], details["prompt_template"])
            else:
                self.agents[name] = Agent(name, details["role"], details["prompt_template"])

    # (#2) Clear previous console output.
    def clear_console(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def adjust_agent_prompts(self, refined_problem):
        for agent_name, agent in self.agents.items():
            if agent_name != "PromptRefinerAgent":
                print(f"{Fore.YELLOW}🔄 Updating prompt template for {agent_name}...{Style.RESET_ALL}")
                new_prompt_template = f"{agent.prompt_template}\n\nRefined Problem Statement:\n{refined_problem}"
                agent.prompt_template = new_prompt_template
                print(f"{Fore.GREEN}✅ {agent_name} prompt adjusted.{Style.RESET_ALL}")
                
    def refine_agent_response(self, agent_name, agent_response, problem_statement):
        """Refine agent response using LLM feedback before re-execution."""
        critique_prompt = f"""
        The response from {agent_name} has been evaluated and requires improvement.

        **Problem Statement:** {problem_statement}
        **Current Response:** {agent_response}
        
        **Evaluator Feedback:**
        - Improve clarity on key assumptions.
        - Specify investment vehicles for each sector or region.
        - Quantify inflation impact and tax implications.

        **Refined Response:**
        Provide a revised version of the response incorporating the above feedback.
        """
        refined_response = self.agents["ResponseCritiqueAgent"].interface.query(critique_prompt)
        
        if refined_response.strip() != agent_response.strip():
            print(f"{Fore.GREEN}✅ {agent_name} Response Optimized!{Style.RESET_ALL}")
            return refined_response
        return agent_response  # Return the same response if no refinement is needed.
        
    @staticmethod
    def extract_confidence_score(response_text):
        try:
            print(f"Raw evaluation output:\n{response_text}")  # Debugging output

            # Updated regex to capture both whole numbers and decimals (e.g., 8/10, 8.5/10)
            match = re.search(r'\*\*Confidence Score:\*\*\s*([0-9]+(?:\.[0-9]+)?)/10', response_text)

            if match:
                score = float(match.group(1)) * 10  # Convert 8.5/10 to 85
                print(f"✅ Extracted confidence score: {score}")  # Debugging output
                return score
            else:
                print(f"⚠️ Failed to extract confidence score. Defaulting to 50%.")  # Debugging alert

        except Exception as e:
            print(f"❌ Error extracting confidence score: {e}")

        return 50  # Default fallback value

    def run_agents_sequentially(self, refined_problem):
        self.adjust_agent_prompts(refined_problem)
        dependency_outputs = {}

        ordered_execution = [
            "PromptRefinerAgent",
            "ResearchAgent",
            "ResearchAgentFinance",
            "MacroeconomicAgent",
            "SolutionArchitectAgent",
            "CommunicatorAgent",
            "EvaluatorAgent",
            "ResponseCritiqueAgent",
            "DirectorAgent"
        ]

        dynamic_agents = self.get_dynamic_agent_mapping(refined_problem, self.session.domain)
        self.session.active_agents = dynamic_agents
        filtered_execution = [agent for agent in ordered_execution if agent in dynamic_agents]

        for agent_name in filtered_execution:
            if agent_name in self.agents:
                print(f"{Fore.BLUE}[{datetime.datetime.now()}] 🔄 Running {agent_name}...{Style.RESET_ALL}")
                start_time = time.time()
                if agent_name == "EvaluatorAgent":
                    # For the EvaluatorAgent, run evaluation and then trigger a refinement loop
                    agent_response = self.agents[agent_name].execute(
                        agent_name,
                        dependency_outputs.get(agent_name, ""),
                        refined_problem
                    )
                    confidence_score = self.extract_confidence_score(agent_response)
                    iteration = 0
                    while confidence_score < 70 and iteration < 3:
                        print(f"{Fore.YELLOW}[{datetime.datetime.now()}] 🔄 Refining response due to low confidence ({confidence_score}%)...{Style.RESET_ALL}")
                        # Get a refined response from the critique agent
                        refined_response = self.agents["ResponseCritiqueAgent"].execute(agent_name, agent_response)
                        # Update the originating agent with feedback for future runs
                        if agent_name in self.agents:
                            self.agents[agent_name].update_from_feedback(refined_response, agent_response)
                        # Re-run evaluation after refinement
                        evaluation_output = self.agents["EvaluatorAgent"].execute(agent_name, refined_response, refined_problem)
                        confidence_score = self.extract_confidence_score(evaluation_output)
                        agent_response = refined_response  # Use refined response for next iteration
                        iteration += 1

                    print(f"{Fore.GREEN}[{datetime.datetime.now()}] ✅ Final Confidence Score: {confidence_score}%{Style.RESET_ALL}")
                else:
                    # Regular agent execution
                    agent_response = self.agents[agent_name].execute(refined_problem, dependency_outputs)
                execution_time = time.time() - start_time
                print(f"{Fore.GREEN}[{datetime.datetime.now()}] ✅ {agent_name} Completed in {execution_time:.2f}s!{Style.RESET_ALL}")
                dependency_outputs[agent_name] = agent_response

        return dependency_outputs
        
    def run_agents_sequentially_old(self, refined_problem):
        """Execute agents in a strict predefined order."""
        self.adjust_agent_prompts(refined_problem)
        dependency_outputs = {}

        # Define strict agent execution order
        ordered_execution = [
            "PromptRefinerAgent",
            "ResearchAgent",
            "ResearchAgentFinance",
            "MacroeconomicAgent",
            "SolutionArchitectAgent",
            "CommunicatorAgent",
            "EvaluatorAgent",
            "ResponseCritiqueAgent",
            "DirectorAgent"
        ]

        # Ensure only selected agents are executed
        dynamic_agents = self.get_dynamic_agent_mapping(refined_problem, self.session.domain)
        self.session.active_agents = dynamic_agents
        filtered_execution = [agent for agent in ordered_execution if agent in dynamic_agents]

        for agent_name in filtered_execution:
            if agent_name in self.agents:
                print(f"{Fore.BLUE}[{datetime.datetime.now()}] 🔄 Running {agent_name}...{Style.RESET_ALL}")
                start_time = time.time()
                if agent_name == "EvaluatorAgent":
                    agent_response = self.agents[agent_name].execute(
                        agent_name,  # Name of the agent being evaluated
                        dependency_outputs.get(agent_name, ""),  # The agent's response to be evaluated
                        refined_problem  # The problem statement for evaluation context
                    )
                    #####################################################################
                    confidence_score = self.extract_confidence_score(agent_response)

                    # 🔄 If confidence score is below 7/10 (70%), request refinements
                    iteration = 0
                    while confidence_score < 70 and iteration < 3:  # Limit to 3 refinements max
                        print(f"{Fore.YELLOW}[{datetime.datetime.now()}] 🔄 Refining response due to low confidence ({confidence_score}%)...{Style.RESET_ALL}")
                        agent_response = self.agents["ResponseCritiqueAgent"].execute(agent_name, agent_response)
                        
                        # Re-evaluate
                        evaluation_output = self.agents["EvaluatorAgent"].execute(agent_name, agent_response, refined_problem)
                        confidence_score = self.extract_confidence_score(evaluation_output)
                        iteration += 1

                    print(f"{Fore.GREEN}[{datetime.datetime.now()}] ✅ Final Confidence Score: {confidence_score}%{Style.RESET_ALL}")
                    #####################################################################
                else:
                    agent_response = self.agents[agent_name].execute(refined_problem, dependency_outputs)
#                agent_response = self.agents[agent_name].execute(refined_problem, dependency_outputs)
                execution_time = time.time() - start_time
                print(f"{Fore.GREEN}[{datetime.datetime.now()}] ✅ {agent_name} Completed in {execution_time:.2f}s!{Style.RESET_ALL}")

                dependency_outputs[agent_name] = agent_response

        return dependency_outputs
        
    def run(self, problem_statement, domain="General"):
        self.clear_console()  # (#2) Clear console before starting
        print("\n==== Multi-Agent System Started ====\n")
        self.session = Session(session_id=f"session_{int(time.time())}", domain=domain)
        reset_context(self.session)
        dynamic_agents = get_dynamic_agent_mapping(problem_statement, domain)
        print(f"{Fore.CYAN}[Dynamic Mapping] Agents recommended: {dynamic_agents}{Style.RESET_ALL}")
        self.session.active_agents = dynamic_agents
        if "PromptRefinerAgent" in self.agents:
            print(f"{Fore.BLUE}🔄 Running PromptRefinerAgent...{Style.RESET_ALL}")
            refined_problem, confidence = self.agents["PromptRefinerAgent"].refine_problem_statement(problem_statement)
            print(f"{Fore.CYAN}Refined Problem Statement (Confidence {confidence}%):\n{refined_problem}{Style.RESET_ALL}")
        else:
            refined_problem = problem_statement
        agent_outputs = self.run_agents_sequentially(refined_problem)
        print("\n==== Multi-Agent System Completed ====\n")
        final_output = "\n".join([f"**{name} Output:**\n{result}" for name, result in agent_outputs.items()])
        return final_output

if __name__ == "__main__":
    problem = (
    "Develop an portfolio investment strategy yielding 8-10% annual return with minimal risk exposure."
    "* Current age: 68"
    "* Annual income: $65,000"
    "* Net worth: $0.4M"
    "* Investment goals:"
    "    + Long-term growth and wealth accumulation"
    "    + Regular income generation through dividends"
    "* Risk tolerance:"
    "    + Conservative (avoiding high-risk investments)"
    "    + Willing to accept some market volatility in pursuit of long-term returns"
    )
    domain = "Wealth Management"
    agent_system = MultiAgentSystem()
    final_solution = agent_system.run(problem, domain)
    print("\n===== Final Solution =====\n")
    print(final_solution)

