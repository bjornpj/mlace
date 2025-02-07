# Multi-Layered Agent Collaboration Framework for Goal-Oriented Task Execution

# Project Overview
This project establishes a hierarchical agent-based system where Director, Manager, and Individual Agents work together to solve complex goals. The system is implemented in Python and utilizes an Ollama server for AI-driven decision-making. The agents interact dynamically, executing tasks and reporting results through structured communication.

# Agent Hierarchy & Responsibilities
The agent hierarchy follows a structured delegation model where tasks flow downward, and results propagate upward.

## Director Agent
- Role:
  - Acts as the top-level orchestrator, responsible for defining the overarching goal and breaking it down into actionable tasks.
- Responsibilities:
  - Translates a high-level goal into structured tasks for Manager Agents.
  - Delegates these tasks to Manager Agents for further breakdown and execution.
  - Aggregates results from managers and generates a final synthesis report.
  - Utilizes the Ollama server to assist with task definition, evaluation, and decision-making.
  - Ensures that the goal is met efficiently, balancing execution speed and accuracy.
  - Produces actionable conclusions and a final investment report summarizing the insights.
## Manager Agents
- Role:
  - Middle-layer coordinator that refines Director Agent’s tasks into detailed subtasks and delegates them to Individual Agents.
- Responsibilities:
  - Receives tasks from the Director Agent.
  - Translates tasks into subtasks using AI-assisted breakdown.
  - Classifies each subtask as either:
  - Programmatic: Requires execution (Python, Shell, or CMD commands).
  - General: Requires research, analysis, or conceptual work.
  - Assigns programmatic tasks to the OS Agent and general tasks to Individual Agents.
  - Ensures that subtasks are completed successfully, meeting predefined quality benchmarks.
  - Validates the results and reports structured feedback to the Director Agent.
## Individual Agents
- Role:
  - Executes general (non-programmatic) tasks assigned by Manager Agents.
- Responsibilities:
  - Receives a subtask and executes it.
  - Uses LLM-assisted reasoning to generate a response.
  - Ensures task quality through validation and verification.
  - Reports task status, results, and remarks back to the Manager Agent.
  - Handles data processing, research, and logical analysis tasks.
## OS Agent (Specialized Individual Agent)
- Role:
  - Executes programmatic (code execution) tasks assigned by Manager Agents.
- Responsibilities:
  - Receives a task requiring code execution.
  - Uses the Ollama server to generate Python, Shell, or CMD scripts.
  - Executes the command on the local system.
  - Verifies and logs the execution results.
  - Handles automation, scripting, and system-level operations.
  - Returns structured execution feedback to the Manager Agent.

# Use Case Example
For an investment strategy development, the Director Agent sets the goal to identify stocks for a 7-8% annual return with minimized risk. The Manager Agents break this down into subtasks such as market research, trend analysis, and risk assessment. The Individual - Agents research stocks, analyze risk factors, and generate reports. The OS Agent retrieves financial data using automation. The Director Agent consolidates results and generates an investment recommendation report.
## Investment Strategy Development
Goal: Develop an investment strategy yielding 7-8% annual return while minimizing risk.
### Director Agent:
- Breaks down the high-level goal into tasks:
- Analyze past investment trends.
- Identify low-risk stocks.
- Simulate portfolio performance.
- Assigns tasks to Manager Agents.
### Manager Agent:
- Further breaks down tasks into subtasks:
- Research economic indicators.
- Compare risk-adjusted returns.
- Identify three stock tickers per strategy.
- Assigns analytical subtasks to Individual Agents and programmatic stock simulations to OS Agents.
### Individual Agents & OS Agent:
- Individual Agents analyze stock performance, extract insights, and compile recommendations.
- OS Agent runs Python-based financial models to simulate investment performance.
### Manager Agent:
- Collects findings, validates data, and ensures results meet required quality standards.
- Reports structured insights to the Director Agent.
### Director Agent:
- Synthesizes key findings into an executive summary.
- Generates data-driven investment recommendations.
- Produces a final report with actionable insights.
# Conclusion
This multi-layered agent system provides a scalable, AI-driven framework for complex problem-solving. By leveraging LLM-powered task breakdown, classification, and automation, the system ensures efficient task execution across different levels of expertise. It is adaptable for diverse applications, such as financial analysis, strategic planning, and operations management.


# Technical Implementation
- Python Framework: Implements agent classes, task delegation, and execution logic.
- Ollama Server: Powers LLM-driven decision-making and task processing.
- Agent Logging & Reporting: Uses structured message logging to track execution.
- Hierarchical Task Delegation: Ensures structured workflow and efficient collaboration.
- Task Classification & Optimization: Uses AI-based classification for intelligent workload distribution.

## Prerequisites
Ollama should be installed and running (https://github.com/ollama/ollama).
Pull a model to use with the library: ollama pull <model> e.g. ollama pull llama3.2
See Ollama.com for more information on the models available.

## Implementation
### Install
`conda create ollama-env`
`conda activate ollama-env`
`pip install ollama`
### Download LLM model e.g. llama3.2
`ollama pull llama3.3`
### Start Ollama server
`ollama serve`
### Execute
`python combo_generic_a2.py`
