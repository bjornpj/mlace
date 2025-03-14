import os
import re
import json
import time
import hashlib
import datetime
from colorama import Fore, Style
import ollama

# ===============================
# =========== SETTINGS ==========
# ===============================
with open("config.json", "r") as config_file:
    SETTINGS = json.load(config_file)

CONFIDENCE_THRESHOLD = SETTINGS.get("confidence_threshold", 85)
MAX_REFINEMENT_ATTEMPTS = SETTINGS.get("max_refinement_attempts", 4)
MAX_CONFIDENCE_ITERATIONS = SETTINGS.get("max_confidence_iterations", 5)

# ===============================
# ========== OLLAMA API =========
# ===============================
class OllamaInterface:
    def __init__(self, model="llama3.2", temperature=0.1):
        self.model = model
        self.temperature = temperature

    def query(self, prompt):
        """
        Basic wrapper to call ollama.chat().
        Adjust as needed for your environment.
        """
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
#                temperature=self.temperature
            )
            raw_content = response.get("message", {}).get("content", "")
            # Optional debugging prints
            print(f"{Fore.MAGENTA}[LLM Query] {prompt[:200]}...{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}[LLM Response] {raw_content[:200]}...{Style.RESET_ALL}")
            return raw_content
        except Exception as e:
            print(f"{Fore.RED}[ERROR in OllamaInterface] {e}{Style.RESET_ALL}")
            return "ERROR"

# ===============================
# ========== BASE AGENT =========
# ===============================
class Agent:
    def __init__(self, name, role, prompt_template):
        self.name = name
        self.role = role
        self.prompt_template = prompt_template
        self.interface = OllamaInterface()
        self.output = None
        self.improvement_history = []

    def execute(self, problem_statement, context=""):
        """
        Format the prompt template with the problem and context, then query.
        """
        prompt = self.prompt_template.format(problem=problem_statement, context=context)
        try:
            self.output = self.interface.query(prompt)
        except Exception as e:
            print(f"{Fore.RED}[{self.name} ERROR] {e}{Style.RESET_ALL}")
            self.output = "ERROR"
        return self.output

    def update_from_feedback(self, refined_response, evaluator_feedback):
        """
        For example, you can append feedback to the prompt template to iterate improvements.
        """
        feedback_note = f"\n\n[Feedback Update]: {evaluator_feedback.strip()}"
        if feedback_note not in self.prompt_template:
            self.prompt_template += feedback_note
            self.improvement_history.append(feedback_note)
            print(f"{Fore.GREEN}[{self.name}] Prompt template updated with feedback.{Style.RESET_ALL}")
        else:
            print(f"{Fore.CYAN}[{self.name}] Feedback already integrated.{Style.RESET_ALL}")

# ===============================
# ========== ROLE AGENTS ========
# ===============================

class ProductOwnerAgent(Agent):
    """
    Example specialized logic for a Product Owner:
    refine backlog items, user stories, acceptance criteria, etc.
    """
    def refine_backlog_item(self, original_item, max_attempts=MAX_REFINEMENT_ATTEMPTS):
        refined_item = original_item
        confidence_score = 50  # default

        for attempt in range(max_attempts):
            print(f"{Fore.YELLOW}[ProductOwnerAgent] Refinement Attempt {attempt+1}/{max_attempts}{Style.RESET_ALL}")

            # We'll build a specialized prompt
            refine_prompt = f"""
            You are a Product Owner. Refine the following user story/feature to ensure clarity, testability, and alignment with business objectives.
            
            Original Item:
            {refined_item}

            After refinement, provide:
            1. The improved backlog item.
            2. A confidence score (0-100%) regarding clarity and completeness.
            """

            llm_response = self.interface.query(refine_prompt)
            # Attempt to parse out a confidence score
            refined_item, extracted_conf = self.extract_confidence_score(llm_response)

            if extracted_conf >= CONFIDENCE_THRESHOLD:
                print(f"{Fore.GREEN}[ProductOwnerAgent] Confidence {extracted_conf}% → Final Refinement.{Style.RESET_ALL}")
                return refined_item, extracted_conf

        # If max attempts reached, just return the best we have
        return refined_item, extracted_conf

    @staticmethod
    def extract_confidence_score(text):
        """
        For example, parse "Confidence Score: 85%"
        """
        try:
            match = re.search(r"Confidence Score:\s*([0-9]+(?:\.[0-9]+)?)%", text, re.IGNORECASE)
            if match:
                score = float(match.group(1))
                # Strip out the match from text if needed
                processed_text = text.replace(match.group(0), "").strip()
                return processed_text, min(max(int(score), 0), 100)
        except:
            pass
        return text.strip(), 50


class ScrumMasterAgent(Agent):
    """
    Focus on agile ceremonies, identifying impediments, and driving continuous improvement.
    Methods reference best-in-class agile practices from top-tier tech companies.
    """
    def facilitate_sprint_improvement(self, current_impediments, sprint_goals):
        """
        Example specialized method:
        - Summarizes known impediments
        - Suggests best-in-class improvements from Google/Meta/OpenAI experiences
        """
        prompt = f"""
        You are a highly experienced Scrum Master with insight into agile practices at leading tech companies.
        Current Sprint Goals: {sprint_goals}
        Known Impediments: {current_impediments}

        1. Provide a concise plan to resolve these impediments.
        2. Suggest specific 'best in class' improvements inspired by top-tier organizations (Google, Meta, OpenAI).
        3. Offer next steps for continuous improvement, including retro ideas and success metrics.
        """

        response = self.interface.query(prompt)
        print(f"{Fore.BLUE}[ScrumMasterAgent] Facilitated Sprint Improvement:\n{response}{Style.RESET_ALL}")
        return response


class DevTeamAgent(Agent):
    """
    Handles day-to-day coding, architecture, and implementation tasks.
    Emphasizes best practices: code reviews, pair programming, testing, etc.
    """
    def propose_technical_solution(self, backlog_item, codebase_context):
        """
        Suggests a technical solution, referencing best-in-class engineering processes.
        """
        prompt = f"""
        You are a senior software engineer on a world-class Dev Team (like Google or OpenAI).
        Backlog Item: {backlog_item}
        Codebase Context: {codebase_context}

        Provide:
        1. A step-by-step technical approach (include data structures, algorithms, or frameworks).
        2. Integration points with existing code.
        3. A mini plan for code reviews, CI/CD, and potential automation or microservice patterns.
        4. Provide one or more relevant code snippets or config files (e.g., Dockerfile, CI/CD pipeline config, or application code) to implement the above. Be sure to use fenced code blocks (```language) and include brief inline explanations as comments.
        """

        response = self.interface.query(prompt)
        print(f"{Fore.BLUE}[DevTeamAgent] Proposed Technical Solution:\n{response}{Style.RESET_ALL}")
        return response


class TesterAgent(Agent):
    """
    Defines testing strategies, acceptance tests, advanced QA automation,
    and coverage metrics consistent with top-tier QA teams.
    """
    def create_comprehensive_test_plan(self, backlog_item, codebase_context):
        """
        Outlines a best-in-class test strategy: unit, integration, performance, security, etc.
        """
        prompt = f"""
        You are a QA expert with experience from leading tech companies.
        Backlog Item to Test: {backlog_item}
        Codebase Context: {codebase_context}

        1. Outline functional and non-functional test scenarios.
        2. Include unit, integration, performance, and security tests.
        3. Suggest advanced automation frameworks and coverage metrics (like Google's approach).
        4. Provide acceptance criteria to ensure the feature meets stakeholder needs.
        """

        response = self.interface.query(prompt)
        print(f"{Fore.BLUE}[TesterAgent] Comprehensive Test Plan:\n{response}{Style.RESET_ALL}")
        return response


class ReleaseTrainEngineerAgent(Agent):
    """
    Orchestrates multi-team coordination, release plans, and risk management
    at scale (inspired by large-scale agile transformations at Meta/Google).
    """
    def coordinate_release_plan(self, features, dependencies, organizational_goals):
        """
        Builds a multi-team release plan with clearly identified dependencies & risk mitigation.
        """
        prompt = f"""
        You are a Release Train Engineer managing multiple agile teams, like at a large tech org.
        Features: {features}
        Dependencies: {dependencies}
        Organizational Goals: {organizational_goals}

        Provide:
        1. A top-level release timeline (milestones, increments).
        2. Cross-team synchronization points.
        3. Risk/issue management strategies referencing large-scale agile at Google or Meta.
        4. Suggested metrics for tracking and success criteria.
        """

        response = self.interface.query(prompt)
        print(f"{Fore.BLUE}[ReleaseTrainEngineerAgent] Release Plan Coordination:\n{response}{Style.RESET_ALL}")
        return response


class SystemArchitectAgent(Agent):
    """
    Ensures solutions align with enterprise architecture, performance, and scalability
    in a manner consistent with globally distributed systems at top tech companies.
    """
    def propose_architecture_design(self, feature_description, existing_infrastructure):
        """
        Provides a high-level architectural approach, referencing modern patterns (microservices,
        container orchestration, pub/sub, etc.) used by large-scale systems at e.g. Google Cloud.
        """
        prompt = f"""
        You are a seasoned System Architect (think Google-level scale).
        Feature to Architect: {feature_description}
        Current Infrastructure: {existing_infrastructure}

        1. Recommend an architecture overview (include domain boundaries, microservices, or event-driven patterns).
        2. Outline potential security and performance considerations for large-scale usage.
        3. Suggest frameworks or internal best practices from top-tier companies to ensure reliability and observability.
        """

        response = self.interface.query(prompt)
        print(f"{Fore.BLUE}[SystemArchitectAgent] Proposed Architecture:\n{response}{Style.RESET_ALL}")
        return response


class BusinessAnalystAgent(Agent):
    """
    Gathers and refines business requirements, clarifies scope, and defines KPIs.
    Emphasizes data-driven decision-making and stakeholder alignment akin to top orgs.
    """
    def define_business_requirements(self, project_goals, stakeholder_needs):
        """
        Elicits refined business requirements with measurable KPIs, referencing
        data-driven analysis & product frameworks used by leading tech companies.
        """
        prompt = f"""
        You are a Business Analyst working at the level of leading tech product teams.
        Project Goals: {project_goals}
        Stakeholder Needs: {stakeholder_needs}

        Provide:
        1. A refined set of business requirements with any assumptions clearly stated.
        2. Concrete KPIs or metrics that reflect success (include growth, engagement, or ROI metrics).
        3. Recommended scope boundaries to avoid feature creep and maintain focus on MVP.
        4. Additional data or user-research suggestions in line with best-in-class practices.
        """

        response = self.interface.query(prompt)
        print(f"{Fore.BLUE}[BusinessAnalystAgent] Defined Business Requirements:\n{response}{Style.RESET_ALL}")
        return response

class EvaluatorAgent(Agent):
    """
    Evaluates solutions for alignment, clarity, completeness.
    Provide a confidence score.
    """
    def execute(self, agent_name, agent_response, problem_statement):
        prompt = self.prompt_template.format(problem=problem_statement, context=agent_response)
        raw_eval = self.interface.query(prompt)
        print(f"{Fore.YELLOW}[EvaluatorAgent] Evaluation for {agent_name}:\n{raw_eval}{Style.RESET_ALL}")
        return raw_eval


class CommunicatorAgent(Agent):
    """Summarizes final outcome into an executive-level update."""


class ResponseCritiqueAgent(Agent):
    """
    Critiques a given agent's response and returns a refined version if improvements
    are needed.
    """
    def execute(self, agent_name, agent_response):
        prompt = self.prompt_template.format(problem=agent_name, context=agent_response)
        refined_response = self.interface.query(prompt)
        if refined_response.strip() != agent_response.strip():
            print(f"{Fore.GREEN}✅ {agent_name} Response Optimized!{Style.RESET_ALL}")
            return refined_response
        return agent_response

# ===============================
# ===== MULTIAGENTSYSTEM =======
# ===============================
class MultiAgentSystem:
    def __init__(self, config_file="agents_config_agilec.json"):
        self.agents = {}
        self.load_agents(config_file)

    def load_agents(self, config_file):
        with open(config_file, "r") as f:
            agent_configs = json.load(f)

        for name, details in agent_configs.items():
            role = details["role"]
            template = details["prompt_template"]

            if name == "ProductOwnerAgent":
                self.agents[name] = ProductOwnerAgent(name, role, template)
            elif name == "ScrumMasterAgent":
                self.agents[name] = ScrumMasterAgent(name, role, template)
            elif name == "DevTeamAgent":
                self.agents[name] = DevTeamAgent(name, role, template)
            elif name == "TesterAgent":
                self.agents[name] = TesterAgent(name, role, template)
            elif name == "ReleaseTrainEngineerAgent":
                self.agents[name] = ReleaseTrainEngineerAgent(name, role, template)
            elif name == "SystemArchitectAgent":
                self.agents[name] = SystemArchitectAgent(name, role, template)
            elif name == "BusinessAnalystAgent":
                self.agents[name] = BusinessAnalystAgent(name, role, template)
            elif name == "EvaluatorAgent":
                self.agents[name] = EvaluatorAgent(name, role, template)
            elif name == "CommunicatorAgent":
                self.agents[name] = CommunicatorAgent(name, role, template)
            elif name == "ResponseCritiqueAgent":
                self.agents[name] = ResponseCritiqueAgent(name, role, template)
            else:
                # Fallback to a base Agent if no specialized class is found.
                self.agents[name] = Agent(name, role, template)

    def clear_console(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def extract_confidence_score(text):
        """
        E.g. parse "**Confidence Score:** 8/10" → 80
        or "Confidence Score: 85%" → 85
        """
        try:
            match_fraction = re.search(r"Confidence Score:\s*([0-9]+(?:\.[0-9]+)?)/10", text, re.IGNORECASE)
            if match_fraction:
                return float(match_fraction.group(1)) * 10
            match_percent = re.search(r"Confidence Score:\s*([0-9]+(?:\.[0-9]+)?)%", text, re.IGNORECASE)
            if match_percent:
                return float(match_percent.group(1))
        except:
            pass
        return 50.0

    def run(self, problem_statement):
        self.clear_console()
        print(f"{Fore.CYAN}=== Running Multi-Agent System (SAFe Roles) ==={Style.RESET_ALL}")

        # 1) Optionally let Product Owner refine the backlog item
        if "ProductOwnerAgent" in self.agents:
            refined, conf = self.agents["ProductOwnerAgent"].refine_backlog_item(problem_statement)
            problem_statement = refined
            print(f"{Fore.GREEN}[Refined Backlog Item] (Confidence: {conf}%)\n{refined}{Style.RESET_ALL}")
        elif "DevTeamAgent":
            dev_agent = self.agents["DevTeamAgent"]
            dev_code = dev_agent.generate_code_snippets(refined_problem, outputs)
            outputs["DevTeamAgent_code"] = dev_code
            
       # Decide on execution order
        # (In practice, you could also do dynamic selection. This is a static example.)
        role_order = [
            "BusinessAnalystAgent",
            "SystemArchitectAgent",
            "DevTeamAgent",
            "TesterAgent",
            "ScrumMasterAgent",
            "ReleaseTrainEngineerAgent",
            "EvaluatorAgent",
            "CommunicatorAgent",
            "ResponseCritiqueAgent"
        ]

        outputs = {}
        for role_name in role_order:
            if role_name in self.agents:
                agent = self.agents[role_name]
                print(f"\n{Fore.BLUE}=== Executing {role_name} ==={Style.RESET_ALL}")

                # The EvaluatorAgent's .execute() signature differs
                if role_name == "EvaluatorAgent":
                    agent_response = agent.execute(role_name, outputs, problem_statement)
                    conf_score = self.extract_confidence_score(agent_response)
                    if conf_score < CONFIDENCE_THRESHOLD:
                        print(f"{Fore.YELLOW}→ Low Confidence ({conf_score}%). Attempting refinements...{Style.RESET_ALL}")
                        # Try critique → re-evaluate loop
                        for attempt in range(3):
                            if "ResponseCritiqueAgent" in self.agents:
                                critiqued = self.agents["ResponseCritiqueAgent"].execute(role_name, agent_response)
                                agent_response = critiqued
                                re_eval = agent.execute(role_name, critiqued, problem_statement)
                                conf_score = self.extract_confidence_score(re_eval)
                                if conf_score >= CONFIDENCE_THRESHOLD:
                                    break
                    print(f"{Fore.GREEN}[EvaluatorAgent] Final Confidence: {conf_score}%{Style.RESET_ALL}")
                elif role_name == "ResponseCritiqueAgent":
                    # Typically you'd pass in the last agent's output to critique
                    last_agent_name = list(outputs.keys())[-1] if outputs else "NoAgent"
                    last_agent_response = outputs[last_agent_name] if last_agent_name in outputs else ""
                    agent_response = agent.execute(last_agent_name, last_agent_response)
                else:
                    # Standard approach: pass the entire 'outputs' dict as context
                    agent_response = agent.execute(problem_statement, context=outputs)

                outputs[role_name] = agent_response

        # Summarize final
        return "\n\n".join(f"**{k}** Output:\n{v}" for k, v in outputs.items())


#************************************************
class SAFeOrchestrator:
    def __init__(self):
        self.agents = {
            "ProductOwnerAgent": ProductOwnerAgent("ProductOwnerAgent", "Product Owner"),
            "BusinessAnalystAgent": BusinessAnalystAgent("BusinessAnalystAgent", "Business Analyst"),
            "SystemArchitectAgent": SystemArchitectAgent("SystemArchitectAgent", "System Architect"),
            "ScrumMasterAgent": ScrumMasterAgent("ScrumMasterAgent", "Scrum Master"),
            "DevTeamAgent": DevTeamAgent("DevTeamAgent", "Dev Team"),
            "TesterAgent": TesterAgent("TesterAgent", "Tester"),
            "ReleaseTrainEngineerAgent": ReleaseTrainEngineerAgent("ReleaseTrainEngineerAgent", "Release Train Engineer"),
            "EvaluatorAgent": EvaluatorAgent("EvaluatorAgent", "Solution Evaluator"),
            "CommunicatorAgent": CommunicatorAgent("CommunicatorAgent", "Agile Communicator"),
            "ResponseCritiqueAgent": ResponseCritiqueAgent("ResponseCritiqueAgent", "Response Refinement Expert")
        }

    def run_sprint(self):
        """
        Simulate a 'sprint' in which each SAFe role produces its artifact.
        """
        results = []

        # Product Owner → refine backlog
        po_output = self.agents["ProductOwnerAgent"].produce_refined_backlog_item()
        results.append((self.agents["ProductOwnerAgent"].name, po_output))

        # BA → business requirements
        ba_output = self.agents["BusinessAnalystAgent"].produce_business_requirements()
        results.append((self.agents["BusinessAnalystAgent"].name, ba_output))

        # System Architect → architecture
        sa_output = self.agents["SystemArchitectAgent"].produce_architecture_overview()
        results.append((self.agents["SystemArchitectAgent"].name, sa_output))

        # Scrum Master → process improvements
        sm_output = self.agents["ScrumMasterAgent"].produce_impediments_and_resolutions()
        results.append((self.agents["ScrumMasterAgent"].name, sm_output))

        # Dev Team → code snippet
        dt_output = self.agents["DevTeamAgent"].produce_code_snippet()
        results.append((self.agents["DevTeamAgent"].name, dt_output))

        # Tester → test plan
        tester_output = self.agents["TesterAgent"].produce_test_plan()
        results.append((self.agents["TesterAgent"].name, tester_output))

        # RTE → release plan
        rte_output = self.agents["ReleaseTrainEngineerAgent"].produce_release_plan()
        results.append((self.agents["ReleaseTrainEngineerAgent"].name, rte_output))

        # Evaluator → solution eval
        eval_output = self.agents["EvaluatorAgent"].produce_evaluation()
        results.append((self.agents["EvaluatorAgent"].name, eval_output))

        # Communicator → executive summary
        comm_output = self.agents["CommunicatorAgent"].produce_executive_summary()
        results.append((self.agents["CommunicatorAgent"].name, comm_output))

        # Response Critique → final refinement
        critique_output = self.agents["ResponseCritiqueAgent"].produce_refined_output()
        results.append((self.agents["ResponseCritiqueAgent"].name, critique_output))

        # Print out results in a simple aggregated format
        print(f"{Fore.GREEN}=== SAFe-Oriented Sprint Outputs ==={Style.RESET_ALL}\n")
        for agent_name, output_text in results:
            print(f"{Fore.YELLOW}--- {agent_name} Output ---{Style.RESET_ALL}\n{output_text}\n")

#************************************************

# ===============================
# ========== MAIN ENTRY =========
# ===============================
if __name__ == "__main__":
    sample_problem = (
        "As a user, I want to upload large files securely and quickly, "
        "so that I can share data with collaborators without risking data breaches."
    )

    system = MultiAgentSystem(config_file="agents_config_AGILE.json")
    final_result = system.run(sample_problem)

    print("\n=== Final Aggregated Output ===\n")
    print(final_result)



