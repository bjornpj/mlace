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

    goal = "To optimize hospital bed turnover by reducing the time between patient discharge and bed re-occupancy by 80%."
#    goal = "Develop a best in class investment strategy yeilding 10%-15% annual returns at lowest possible risk. Recommend up to four tickers for each strategy with percentage allocation."
    report = director.delegate_goal(goal)
    print(report)

if __name__ == "__main__":
    main()
