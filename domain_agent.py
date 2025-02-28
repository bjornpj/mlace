# domain_agent.py

class Session:
    """
    Represents a session for a given problem domain.
    """
    def __init__(self, session_id: str, domain: str):
        self.session_id = session_id
        self.domain = domain  # e.g., "Healthcare", "Investments", "Trauma"
        self.context = {}     # Session-specific context
        self.active_agents = []  # List of agents active for this domain

    def __str__(self):
        return f"Session(ID: {self.session_id}, Domain: {self.domain}, Active Agents: {self.active_agents})"


def reset_context(session: Session):
    """
    Clear session context and active agents.
    """
    session.context.clear()
    session.active_agents = []
    print(f"[INFO] Context reset for session '{session.session_id}'.")


def assign_agents(session: Session, domain_agent_mapping: dict):
    """
    Assign agents to the session based on the session's domain.
    
    Parameters:
      - domain_agent_mapping: a dictionary mapping domain tags to agent name lists.
    """
    agents = domain_agent_mapping.get(session.domain, [])
    session.active_agents = agents
    print(f"[INFO] Agents assigned to session '{session.session_id}': {session.active_agents}")
