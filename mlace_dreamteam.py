#!/usr/bin/env python3
import os
import json
import time
import datetime
import re
import hashlib
import requests
from colorama import Fore, Style

# --- Helper Functions for JSON Extraction ---

def extract_json_between_delimiters(text, start_delim="<<<JSON>>>", end_delim="<<<END>>>"):
    """
    Extracts and parses JSON content between specified delimiters with error correction.
    If delimiters are missing but JSON is present, attempts fallback parsing.
    """
    start = text.find(start_delim)
    end = text.find(end_delim, start + len(start_delim))

    if start != -1 and end != -1:
        json_text = text[start+len(start_delim):end].strip()
    else:
        # Fallback: Try to find first valid JSON block in the raw response
        print(f"{Fore.YELLOW}⚠️ Delimiters not found — attempting raw JSON fallback.{Style.RESET_ALL}")
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            json_text = match.group(0).strip()
        else:
            return None

    try:
        json_text = re.sub(r'(?<!\\)\\n', '', json_text)
        json_text = json_text.replace('\n', ' ').replace('\r', ' ')
        json_text = re.sub(r'\s+', ' ', json_text)
        return json.loads(json_text)
    except Exception as e:
        print(f"{Fore.RED}Error parsing JSON between delimiters or fallback: {e}{Style.RESET_ALL}")
        return None

def extract_json_between_delimiters_orig(text, start_delim="<<<JSON>>>", end_delim="<<<END>>>"):
    """
    Extracts and parses JSON content between specified delimiters with error correction.
    """
    start = text.find(start_delim)
    end = text.find(end_delim, start + len(start_delim))
    if start == -1 or end == -1:
        return None
    json_text = text[start+len(start_delim):end].strip()

    try:
        # Flatten broken JSON content (e.g., from LLM newlines inside strings)
        json_text = re.sub(r'(?<!\\)\\n', '', json_text)
        json_text = json_text.replace('\n', ' ').replace('\r', ' ')
        json_text = re.sub(r'\s+', ' ', json_text)
        return json.loads(json_text)
    except Exception as e:
        print(f"{Fore.RED}Error parsing JSON between delimiters: {e}{Style.RESET_ALL}")
        return None
        
def extract_json_between_delimiters_orig(text, start_delim="<<<JSON>>>", end_delim="<<<END>>>"):
    """
    Extracts the JSON object enclosed between the specified delimiters.
    Returns the JSON object as a dict if successful; otherwise, returns None.
    """
    start = text.find(start_delim)
    end = text.find(end_delim, start + len(start_delim))
    if start == -1 or end == -1:
        return None
    json_text = text[start+len(start_delim):end].strip()
    try:
        return json.loads(json_text)
    except Exception as e:
        print(f"{Fore.RED}Error parsing JSON between delimiters: {e}{Style.RESET_ALL}")
        return None

def extract_json(text):
    """
    Fallback extraction of the first balanced JSON object from text.
    First attempts to extract using delimiters; if that fails, falls back to a brace-count method.
    """
    extracted = extract_json_between_delimiters(text)
    if extracted is not None:
        return extracted
    start = text.find('{')
    if start == -1:
        return None
    brace_count = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i
                break
    if end != -1:
        json_text = text[start:end+1]
        try:
            return json.loads(json_text)
        except Exception as e:
            print(f"{Fore.RED}Error loading JSON: {e}{Style.RESET_ALL}")
            return None
    return None

# --- Session and Context Setup ---

class Session:
    def __init__(self, session_id, domain):
        self.session_id = session_id
        self.domain = domain
        self.active_agents = []
        self.refined_objective = None  # <--- added line
        
def reset_context(session):
    print(f"{Fore.YELLOW}[Context reset for session {session.session_id} in domain {session.domain}]{Style.RESET_ALL}")

# --- Ollama Interface (Actual API Calls) ---
import ollama  # make sure you have `ollama` package installed

class OllamaInterface:
    def __init__(self, model="llama3.2", temperature=0.1):
        self.model = model
        self.temperature = temperature  # Not used by ollama.chat yet, but retained for future

    def query(self, prompt):
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            raw_content = response.get("message", {}).get("content", "")
            print(f"{Fore.MAGENTA}[LLM Query] {prompt[:200]}...{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}[LLM Response] {raw_content[:200]}...{Style.RESET_ALL}")
            return raw_content
        except Exception as e:
            print(f"{Fore.RED}[ERROR in OllamaInterface] {e}{Style.RESET_ALL}")
            return "ERROR"

# --- Base Agent Class ---

class Agent:
    def __init__(self, name, role, prompt_template):
        self.name = name
        self.role = role
        self.prompt_template = prompt_template
        self.interface = OllamaInterface()
        self.output = None
        self.improvement_history = []
    
    def execute(self, problem_statement, context=""):
        prompt = self.prompt_template.format(problem=problem_statement, context=context)
        try:
            self.output = self.interface.query(prompt)
        except Exception as e:
            print(f"{Fore.RED}[{self.name} ERROR] {e}{Style.RESET_ALL}")
            self.output = "ERROR"
        return self.output
    
    def update_from_feedback(self, refined_response, evaluator_feedback):
        feedback_note = f"\n\n[Feedback Update]: {evaluator_feedback.strip()}"
        if feedback_note not in self.prompt_template:
            self.prompt_template += feedback_note
            self.improvement_history.append(feedback_note)
            print(f"{Fore.GREEN}[{self.name}] Prompt template updated with feedback.{Style.RESET_ALL}")
        else:
            print(f"{Fore.CYAN}[{self.name}] Feedback already integrated.{Style.RESET_ALL}")

# --- Supporting Agents ---

class PromptRefinerAgent(Agent):
    def refine_problem_statement(self, original_problem, max_attempts=4):
        refined_problem = original_problem
        confidence_score = 50  # Default value if extraction fails.
        for attempt in range(max_attempts):
            print(f"{Fore.YELLOW}[PromptRefinerAgent] Refinement Attempt {attempt+1}/{max_attempts}{Style.RESET_ALL}")
            prompt = f"""
You are a domain expert and writing coach. Your task is to refine the following problem statement to improve clarity, specificity, and completeness.

**Original Problem Statement:**
{refined_problem}

Refine it so that it:
- Uses measurable and specific language (e.g., targets, deadlines, constraints)
- Is actionable and time-bound
- Includes key context or scope where relevant

**Response Format — strictly follow this format:**

Return ONLY a valid JSON object enclosed exactly between these delimiters: <<<JSON>>> and <<<END>>>.
Do NOT include any markdown, backticks, explanations, or introductory text.

<<<JSON>>>
{{
  "Refined Objective": "[your improved version here]",
  "Confidence Score": "[XX%]"
}}
<<<END>>>
"""

            llm_response = self.interface.query(prompt)
            data = extract_json_between_delimiters(llm_response)
            if data is not None:
                refined_objective = data.get("Refined Objective", "").strip()
                confidence_str = data.get("Confidence Score", "50%").strip().replace("%", "")
                try:
                    extracted_confidence = int(float(confidence_str))
                except:
                    extracted_confidence = 50
                if refined_objective and extracted_confidence >= 85:
                    print(f"{Fore.GREEN}[PromptRefinerAgent] Confidence {extracted_confidence}% → Final Refinement Achieved.{Style.RESET_ALL}")
                    return refined_objective, extracted_confidence
                else:
                    refined_problem = refined_objective if refined_objective else refined_problem
                    confidence_score = extracted_confidence
            else:
                print(f"{Fore.YELLOW}[PromptRefinerAgent] Failed to extract JSON on attempt {attempt+1}.{Style.RESET_ALL}")
        print(f"{Fore.RED}[PromptRefinerAgent] Max Refinement Attempts Reached. Using Best Version.{Style.RESET_ALL}")
        return refined_problem, confidence_score

class EvaluatorAgent(Agent):
    def execute(self, agent_name, agent_response, problem_statement):
        evaluation_prompt = f"""
You are an evaluation expert. Your task is to assess the response provided by {agent_name} in relation to the original objective.

Please keep your feedback **concise and to the point**:
- Limit each explanation to 1 sentence.
- Do not exceed 3 improvement suggestions.
- Keep the full JSON under 1000 characters.

**Objective:** {problem_statement}
**Agent Response:** {agent_response}

Return ONLY a valid JSON object enclosed exactly between these delimiters: <<<JSON>>> and <<<END>>>.
Do NOT include any markdown, backticks, explanations, or introductory text.

<<<JSON>>>
{{
  "Accuracy": "X/10 - [1 short sentence]",
  "Completeness": "X/10 - [1 short sentence]",
  "Improvements": [
      "Short suggestion 1",
      "Short suggestion 2",
      "Short suggestion 3"
  ],
  "Confidence Score": "X/10"
}}
<<<END>>>
"""

        evaluation_output = self.interface.query(evaluation_prompt)
        print(f"{Fore.YELLOW}[EvaluatorAgent] Evaluation for {agent_name}:\n{evaluation_output}{Style.RESET_ALL}")
        return evaluation_output

class ResponseCritiqueAgent(Agent):
    def execute(self, agent_name, agent_response):
        critique_prompt = f"""
Evaluate the response from {agent_name} for clarity, completeness, and alignment with the objective.
If necessary, refine it to be more actionable and specific.

**Original Response:**
{agent_response}

Return your refined response as plain text only.
"""
        refined_response = self.interface.query(critique_prompt)
        if str(refined_response).strip() != str(agent_response).strip():
            print(f"{Fore.GREEN}✅ {agent_name} Response Optimized!{Style.RESET_ALL}")
            return refined_response
        return agent_response

class CommunicatorAgent(Agent):
    def execute(self, problem_statement, context=""):
        print(f"{Fore.BLUE}[{self.name}] Executing CommunicatorAgent...{Style.RESET_ALL}")
        return super().execute(problem_statement, context)

# --- Dynamic/DreamTeam Agent with Multi-Instance Approach ---
class DynamicAgent(Agent):
    def generate_dynamic_expert_definitions(self, problem_statement):
        prompt = f"""
Based on the following objective, list potential expert roles that could contribute to solving the problem.
For each role, provide a title and a brief definition (explaining its expertise, responsibilities, and contribution).
Return ONLY a valid JSON object enclosed exactly between these delimiters: <<<JSON>>> and <<<END>>>.
Do NOT include any markdown, backticks, explanations, or introductory text.

<<<JSON>>>
{{
    "Financial Analyst": "Analyzes market trends and financial data.",
    "Risk Assessor": "Evaluates potential risks and suggests mitigations."
}}
<<<END>>>

Objective: {problem_statement}
"""
        response = self.interface.query(prompt)
        definitions = extract_json_between_delimiters(response)
        if definitions is None:
            print(f"{Fore.RED}Error parsing dynamic expert definitions. Using default definitions.{Style.RESET_ALL}")
            definitions = {
                "Financial Analyst": "Analyzes market trends and financial data.",
                "Risk Assessor": "Evaluates potential risks and suggests mitigations.",
                "Market Researcher": "Gathers market data and identifies trends.",
                "Strategic Planner": "Develops long-term strategies and action plans."
            }
        return definitions

    def extract_required_roles(self, problem_statement):
        expert_definitions = self.generate_dynamic_expert_definitions(problem_statement)
        expert_definitions_str = "\n".join([f"{role}: {desc}" for role, desc in expert_definitions.items()])
        role_prompt = f"""
Using the expert definitions provided below, determine which of these roles are essential to solving the following objective.
Return ONLY a comma-separated list (with no extra text).

Expert Definitions:
{expert_definitions_str}

Objective: {problem_statement}
"""
        role_response = self.interface.query(role_prompt)
        roles = [role.strip() for role in role_response.split(",") if role.strip()]
        if not roles:
            roles = list(expert_definitions.keys())
        return roles, expert_definitions

    def instantiate_dynamic_agents(self, required_roles, expert_definitions):
        dynamic_agent_pool = {}
        for role in required_roles:
            role_definition = expert_definitions.get(role, "General expert responsibilities.")
            prompt_template = (
                f"You are an expert in '{role}'. Your expertise: {role_definition}.\n"
                "Using your specialized knowledge, contribute to solving the following objective.\n"
                "Objective: {problem}\n"
                "Context: {context}\n"
                "Provide your analysis and recommendations specific to the given objective."
            )
            dynamic_agent_pool[role] = Agent(role, role, prompt_template)
        return dynamic_agent_pool

    def execute(self, problem_statement, context=""):
        required_roles, expert_definitions = self.extract_required_roles(problem_statement)
        dynamic_agent_pool = self.instantiate_dynamic_agents(required_roles, expert_definitions)

        team_outputs = {}
        for role, agent in dynamic_agent_pool.items():
            print(f"{Fore.BLUE}[DynamicAgent] Running agent for role: {role}{Style.RESET_ALL}")
            try:
                formatted_prompt = agent.prompt_template.format(problem=problem_statement, context=context)
#               print(f"{Fore.LIGHTBLACK_EX}Prompt for {role}:\n{formatted_prompt[:300]}...{Style.RESET_ALL}")
                agent_output = agent.interface.query(formatted_prompt)
                agent.output = agent_output
                team_outputs[role] = agent_output
            except Exception as e:
                print(f"{Fore.RED}[{role} ERROR] {e}{Style.RESET_ALL}")
                team_outputs[role] = "ERROR"

        aggregated_output = "Aggregated Team Contributions:\n"
        for role, output in team_outputs.items():
            aggregated_output += f"\n--- Role: {role} ---\n{output}\n"
        aggregated_output += "\nEnd of team contributions."
        return aggregated_output

    def execute_orig(self, problem_statement, context=""):
        required_roles, expert_definitions = self.extract_required_roles(problem_statement)
        dynamic_agent_pool = self.instantiate_dynamic_agents(required_roles, expert_definitions)

        team_outputs = {}
        for role, agent in dynamic_agent_pool.items():
            print(f"{Fore.BLUE}[DynamicAgent] Running agent for role: {role}{Style.RESET_ALL}")
            formatted_prompt = agent.prompt_template.format(problem=problem_statement, context=context)
            try:
#                agent_output = agent.execute(problem_statement, context)
                agent_output = agent.interface.query(formatted_prompt)
                agent.output = agent_output
                team_outputs[role] = agent_output
            except Exception as e:
                print(f"{Fore.RED}[{role} ERROR] {e}{Style.RESET_ALL}")
                team_outputs[role] = "ERROR"

        aggregated_output = "Aggregated Team Contributions:\n"
        for role, output in team_outputs.items():
            aggregated_output += f"\n--- Role: {role} ---\n{output}\n"
        aggregated_output += "\nEnd of team contributions."
        return aggregated_output

    def execute_with_peer_review(self, problem_statement, context=""):
        required_roles, expert_definitions = self.extract_required_roles(problem_statement)
        dynamic_agent_pool = self.instantiate_dynamic_agents(required_roles, expert_definitions)

        # Step 1: Initial execution by each agent
        print(f"{Fore.CYAN}\n[DynamicAgent] Step 1: Initial Agent Outputs{Style.RESET_ALL}")
        first_pass_outputs = {}
        for role, agent in dynamic_agent_pool.items():
            formatted_prompt = agent.prompt_template.format(problem=problem_statement, context=context)
            output = agent.interface.query(formatted_prompt)
            agent.output = output
            first_pass_outputs[role] = output
            print(f"{Fore.LIGHTBLACK_EX}Initial output by {role}:\n{output[:200]}...{Style.RESET_ALL}")

        # Step 2: Peer review loop
        print(f"{Fore.CYAN}\n[DynamicAgent] Step 2: Peer Feedback Rounds{Style.RESET_ALL}")
        refined_outputs = {}
        for target_role, target_output in first_pass_outputs.items():
            feedbacks = []
            for reviewer_role, reviewer_agent in dynamic_agent_pool.items():
                if reviewer_role == target_role:
                    continue

                feedback_prompt = f"""
    You are acting as a peer expert '{reviewer_role}' reviewing a fellow expert '{target_role}'.

    Review their output below and suggest up to 2 improvements or corrections. Focus on alignment with the goal, missing data, clarity, and consistency.

    **Output from {target_role}:**
    {target_output}

    Return your feedback in 1–2 bullet points. Use plain text only.
    """
                feedback = reviewer_agent.interface.query(feedback_prompt)
                feedbacks.append(f"- {reviewer_role}: {feedback.strip()}")

            # Step 3: Let the original agent revise their response
            combined_feedback = "\n".join(feedbacks)
            revision_prompt = f"""
    You are the expert '{target_role}'. Based on the original objective and the feedback from your peers, revise your response to make it more clear, accurate, and actionable.

    **Original Objective:**
    {problem_statement}

    **Original Output:**
    {target_output}

    **Peer Feedback:**
    {combined_feedback}

    Return only your revised and improved response as plain text.
    """
            revised_response = dynamic_agent_pool[target_role].interface.query(revision_prompt)
            refined_outputs[target_role] = revised_response
            print(f"{Fore.GREEN}\n✅ {target_role} Revised Output:\n{revised_response[:300]}...{Style.RESET_ALL}")

        # Step 4: Aggregate the final outputs
        print(f"{Fore.CYAN}\n[DynamicAgent] Step 3: Final Aggregated Team Contributions{Style.RESET_ALL}")
        aggregated_output = "Refined Team Contributions:\n"
        for role, output in refined_outputs.items():
            aggregated_output += f"\n--- Role: {role} ---\n{output.strip()}\n"
        aggregated_output += "\nEnd of improved team collaboration."
        return aggregated_output


class SynthesizerAgent(Agent):
    def __init__(self, name="SynthesizerAgent", role="Synthesis Specialist", prompt_template=None):
        if prompt_template is None:
            prompt_template = """
You are a synthesis expert. Your task is to review the outputs from multiple domain experts and combine their contributions into a single, cohesive, and actionable strategy.

Be concise and precise. Capture the unique value of each expert's perspective while avoiding repetition.

**Refined Objective:**
{problem}

**Team Contributions:**
{context}

Return only the unified plan as plain text.
"""
        super().__init__(name, role, prompt_template)

    def synthesize(self, refined_problem, team_contributions):
        prompt = self.prompt_template.format(problem=refined_problem, context=team_contributions)
        return self.interface.query(prompt)


# --- Multi-Agent System Controller ---

class MultiAgentSystem:
    def __init__(self, config_file="agents_config.json"):
        self.agents = {}
        self.agent_cache = {}
        self.load_agents(config_file)
        self.session = Session(session_id="session_001", domain="Dynamic")
        reset_context(self.session)
        
    def hash_problem_statement(self, problem_statement):
        return hashlib.sha256(problem_statement.encode()).hexdigest()
    
    def load_agents(self, config_file):
        agent_configs = {
            "PromptRefinerAgent": {
                "role": "Language Processing Specialist",
                "prompt_template": "Refine the following objective: {problem}\nContext: {context}"
            },
            "EvaluatorAgent": {
                "role": "Evaluation Specialist",
                "prompt_template": "Evaluate the objective: {problem}\nContext: {context}"
            },
            "CommunicatorAgent": {
                "role": "Communication Specialist",
                "prompt_template": """You are a communication expert and executive summary writer.
            Your task is to convert the content below into a well-structured executive summary suitable for senior decision-makers.

            **Instructions:**
            - Start with the exact refined objective below.
            - Structure the summary using bold section headers...
            - Structure the summary using bold section headers (e.g., **Objective**, **Approach**, **Key Metrics**, **Contributors**, **Impact**, **Next Steps**)
            - Highlight any **quantitative targets, constraints, or KPIs** if available
            - Emphasize **why the solution matters** (e.g., efficiency gains, cost savings, risk reduction, compliance, strategic alignment)
            - Summarize key roles or contributors only if relevant (e.g., Engineer, Analyst, Legal Advisor)
            - Avoid jargon, filler language, and marketing tone
            - Use bullet points or short paragraphs for readability
            - Keep the total word count under 350 words

            **Solution Content:**
            {problem}

            **Refined Objective or Context (if available):**
            {context}

            Return only the final executive summary as plain text. Do not include markdown, backticks, or explanations."""
            },
            "DynamicAgent": {
                "role": "Versatile Expert & Dream Team Assembler",
                "prompt_template": "Initial prompt template. Objective: {problem}\nContext: {context}"
            },
            "ResponseCritiqueAgent": {
                "role": "Critique Specialist",
                "prompt_template": """
            Evaluate the response from {problem} for clarity, completeness, and alignment with the objective.
            If necessary, refine it to be more actionable and specific.

            **Original Response:**
            {context}

            Return only the improved response in plain text.
            """
            },
            "SynthesizerAgent": {
                "role": "Synthesis Specialist",
                "prompt_template": None  # uses default
            }
        }

        for name, details in agent_configs.items():
            if name == "PromptRefinerAgent":
                self.agents[name] = PromptRefinerAgent(name, details["role"], details["prompt_template"])
            elif name == "EvaluatorAgent":
                self.agents[name] = EvaluatorAgent(name, details["role"], details["prompt_template"])
            elif name == "ResponseCritiqueAgent":
                self.agents[name] = ResponseCritiqueAgent(name, details["role"], details["prompt_template"])
            elif name == "CommunicatorAgent":
                self.agents[name] = CommunicatorAgent(name, details["role"], details["prompt_template"])
            elif name == "DynamicAgent":
                self.agents[name] = DynamicAgent(name, details["role"], details["prompt_template"])
            elif name == "SynthesizerAgent":
                self.agents[name] = SynthesizerAgent(name, details["role"], details.get("prompt_template"))
            else:
                self.agents[name] = Agent(name, details["role"], details["prompt_template"])
    
    def clear_console(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def execute_with_peer_review(self, problem_statement, context=""):
        required_roles, expert_definitions = self.extract_required_roles(problem_statement)
        dynamic_agent_pool = self.instantiate_dynamic_agents(required_roles, expert_definitions)

        # Step 1: Initial execution by each agent
        print(f"{Fore.CYAN}\n[DynamicAgent] Step 1: Initial Agent Outputs{Style.RESET_ALL}")
        first_pass_outputs = {}
        for role, agent in dynamic_agent_pool.items():
            formatted_prompt = agent.prompt_template.format(problem=problem_statement, context=context)
            output = agent.interface.query(formatted_prompt)
            agent.output = output
            first_pass_outputs[role] = output
            print(f"{Fore.LIGHTBLACK_EX}Initial output by {role}:\n{output[:200]}...{Style.RESET_ALL}")

        # Step 2: Peer review loop
        print(f"{Fore.CYAN}\n[DynamicAgent] Step 2: Peer Feedback Rounds{Style.RESET_ALL}")
        refined_outputs = {}
        for target_role, target_output in first_pass_outputs.items():
            feedbacks = []
            for reviewer_role, reviewer_agent in dynamic_agent_pool.items():
                if reviewer_role == target_role:
                    continue

                feedback_prompt = f"""
    You are acting as a peer expert '{reviewer_role}' reviewing a fellow expert '{target_role}'.

    Review their output below and suggest up to 2 improvements or corrections. Focus on alignment with the goal, missing data, clarity, and consistency.

    **Output from {target_role}:**
    {target_output}

    Return your feedback in 1–2 bullet points. Use plain text only.
    """
                feedback = reviewer_agent.interface.query(feedback_prompt)
                feedbacks.append(f"- {reviewer_role}: {feedback.strip()}")

            # Step 3: Let the original agent revise their response
            combined_feedback = "\n".join(feedbacks)
            revision_prompt = f"""
    You are the expert '{target_role}'. Based on the original objective and the feedback from your peers, revise your response to make it more clear, accurate, and actionable.

    **Original Objective:**
    {problem_statement}

    **Original Output:**
    {target_output}

    **Peer Feedback:**
    {combined_feedback}

    Return only your revised and improved response as plain text.
    """
            revised_response = dynamic_agent_pool[target_role].interface.query(revision_prompt)
            refined_outputs[target_role] = revised_response
            print(f"{Fore.GREEN}\n✅ {target_role} Revised Output:\n{revised_response[:300]}...{Style.RESET_ALL}")

        # Step 4: Aggregate the final outputs
        print(f"{Fore.CYAN}\n[DynamicAgent] Step 3: Final Aggregated Team Contributions{Style.RESET_ALL}")
        aggregated_output = "Refined Team Contributions:\n"
        for role, output in refined_outputs.items():
            aggregated_output += f"\n--- Role: {role} ---\n{output.strip()}\n"
        aggregated_output += "\nEnd of improved team collaboration."
        return aggregated_output

        
    def run(self, problem_statement, domain="General"):
        self.clear_console()
        print("\n==== Multi-Agent System Started ====\n")
        self.session = Session(session_id=f"session_{int(time.time())}", domain=domain)
        reset_context(self.session)

        # Step 1: Refine problem
        if "PromptRefinerAgent" in self.agents:
            print(f"{Fore.BLUE}🔄 Running PromptRefinerAgent...{Style.RESET_ALL}")
            refined_problem, confidence = self.agents["PromptRefinerAgent"].refine_problem_statement(problem_statement)
            self.session.refined_objective = refined_problem  # <--- save into session
            print(f"{Fore.CYAN}Refined Objective (Confidence {confidence}%):\n{refined_problem}{Style.RESET_ALL}")
        else:
            refined_problem = problem_statement

        # Step 2: Run Dream Team
        if "DynamicAgent" in self.agents:
            print(f"{Fore.BLUE}🔄 Running DynamicAgent (Dream Team Assembler)...{Style.RESET_ALL}")
            dynamic_output = self.agents["DynamicAgent"].execute_with_peer_review(refined_problem)
#            dynamic_output = self.agents["DynamicAgent"].execute(refined_problem)
        else:
            dynamic_output = "DynamicAgent not found."

        # Step 3: Synthesize outputs into unified plan
        if "SynthesizerAgent" in self.agents:
            print(f"{Fore.BLUE}🧠 Running SynthesizerAgent...{Style.RESET_ALL}")
            synthesized = self.agents["SynthesizerAgent"].synthesize(refined_problem, dynamic_output)
        else:
            synthesized = dynamic_output

        # Step 3: Evaluate and refine iteratively
        best_output = synthesized
#        best_output = dynamic_output
        best_score = 0

        if "EvaluatorAgent" in self.agents:
            evaluation_output = self.agents["EvaluatorAgent"].execute("DynamicAgent", dynamic_output, refined_problem)
            confidence_score = self.extract_confidence_score(evaluation_output)
            best_score = confidence_score
            iteration = 0

            while confidence_score < 85 and iteration < 3:
                print(f"{Fore.YELLOW}[{datetime.datetime.now()}] 🔄 Refining response due to low confidence ({confidence_score}%)...{Style.RESET_ALL}")
                refined = self.agents["ResponseCritiqueAgent"].execute("DynamicAgent", best_output)
                self.agents["DynamicAgent"].update_from_feedback(refined, evaluation_output)

                evaluation_output = self.agents["EvaluatorAgent"].execute("DynamicAgent", refined, refined_problem)
                confidence_score = self.extract_confidence_score(evaluation_output)

                if confidence_score > best_score:
                    best_output = refined
                    best_score = confidence_score

                iteration += 1

            print(f"{Fore.GREEN}[{datetime.datetime.now()}] ✅ Final Confidence Score: {best_score}%{Style.RESET_ALL}")
        else:
            best_output = dynamic_output

        # Step 4: Final CommunicatorAgent polish
        if "CommunicatorAgent" in self.agents:
            final_output = self.agents["CommunicatorAgent"].execute(best_output, context=refined_problem)
 #           final_output = self.agents["CommunicatorAgent"].execute(best_output)
        else:
            final_output = best_output

        print("\n==== Multi-Agent System Completed ====\n")
        print("\n===== Final Solution (Dream Team Approach) =====\n")
        print(final_output)
        return final_output
    
    @staticmethod
    def extract_confidence_score(response_text):
        try:
            # Try extracting JSON if present
            json_data = extract_json(response_text)
            if json_data:
                for key in json_data:
                    if "confidence" in key.lower():
                        value = json_data[key]
                        if isinstance(value, str) and "/" in value:
                            val = float(value.split("/")[0].strip())
                            return val * 10 if val <= 10 else val
                        elif isinstance(value, (int, float)):
                            return float(value) * 10 if value <= 10 else float(value)

            # Fallback regex match
            match = re.search(r'"Confidence\S*Score"\s*:\s*"?(?P<val>[0-9]+(?:\.[0-9]+)?)\/10"?', response_text, re.IGNORECASE)
            if match:
                return float(match.group("val")) * 10
        except Exception as e:
            print(f"{Fore.RED}❌ Error extracting confidence score: {e}{Style.RESET_ALL}")

        print(f"{Fore.YELLOW}⚠️ Failed to extract confidence score. Defaulting to 50%.{Style.RESET_ALL}")
        return 50    
        
    def extract_confidence_score_orig(response_text):
        try:
            match = re.search(r'"Confidence Score":\s*"?([0-9]+(?:\.[0-9]+)?)\/10"?', response_text)
            if match:
                val = float(match.group(1))
                score = val * 10 if val <= 10 else val  # handle both 7 and 70%
#                score = float(match.group(1)) * 10
                return score
            else:
                print(f"{Fore.YELLOW}⚠️ Failed to extract confidence score. Defaulting to 50%.{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}❌ Error extracting confidence score: {e}{Style.RESET_ALL}")
        return 50

if __name__ == "__main__":
    problem = "Develop a H1 style light bulb which never breaks, consumes close to no power."
    domain = "Industrial Engineering"
    
    agent_system = MultiAgentSystem()
    final_solution = agent_system.run(problem, domain)