## main.py
from src.agents.individual_agent import IndividualAgent
from src.agents.os_agent import OSAgent
from src.agents.manager_agent import ManagerAgent
from src.agents.director_agent import DirectorAgent
from src.interfaces.ollama_interface import OllamaInterface

def main():
    llm = OllamaInterface("llama3.2")
    individual_agents = [IndividualAgent(f"IndividualAgent-{i}", llm) for i in range(6)]
    os_agent = OSAgent("OSAgent", llm)
    manager_agents = [ManagerAgent(f"ManagerAgent-{i}", individual_agents, os_agent, llm) for i in range(3)]
    director = DirectorAgent("DirectorAgent", manager_agents, llm)

    goal = "Develop a investment strategy which yeild in 10%-15% returns at lowest possible risk. For each recommendation provide up to 3 proposed tickers."
    report = director.delegate_goal(goal)
    print(report)

if __name__ == "__main__":
    main()
