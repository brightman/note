"""
Guider Agent - Interacts with users and clarifies tasks
"""
from base_agent import BaseAgent


class GuiderAgent(BaseAgent):
    """Agent responsible for chatting with users and clarifying tasks"""

    def __init__(self, api_key: str):
        system_prompt = """You are a Guider Agent in a multi-agent system. Your role is to:

1. Interact with users in a friendly and professional manner
2. Understand their task requirements by asking clarifying questions
3. Ask follow-up questions to ensure you have all necessary details
4. Once the task is clear and well-defined, summarize it clearly

When a task is sufficiently clear, you should respond with a message that starts with "[TASK_CLEAR]" followed by a clear, concise summary of the task.

Guidelines for clarity:
- Ensure you understand the goal and expected outcome
- Clarify any ambiguous requirements
- Identify constraints or preferences
- Understand the scope of work

Be conversational but efficient. Ask targeted questions to quickly clarify the task."""

        super().__init__(api_key, "Guider", system_prompt)

    def chat(self, user_message: str) -> tuple[str, bool]:
        """
        Chat with the user to clarify the task

        Returns:
            tuple[str, bool]: (response message, is_task_clear)
        """
        response = self.send_message(user_message)

        # Check if task is clear
        is_clear = response.startswith("[TASK_CLEAR]")

        if is_clear:
            # Remove the marker from the response
            response = response.replace("[TASK_CLEAR]", "").strip()

        return response, is_clear

    def get_task_summary(self) -> str:
        """Get a clear summary of the task after clarification"""
        summary_request = "Please provide a final, clear, and concise summary of the task in 2-3 sentences."
        return self.send_message(summary_request)
