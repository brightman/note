"""
Executor Agents - Searcher, Coder, and Reporter
"""
from base_agent import BaseAgent


class SearcherAgent(BaseAgent):
    """Agent responsible for searching and gathering information"""

    def __init__(self, api_key: str):
        system_prompt = """You are a Searcher Agent in a multi-agent system. Your role is to:

1. Search for and gather relevant information
2. Research topics thoroughly
3. Find data, facts, and resources related to the task
4. Provide comprehensive and accurate information

When given a search task:
- Be thorough in your research
- Provide well-organized information
- Include relevant details and context
- Cite sources or reasoning when applicable
- Structure your response clearly

Focus on accuracy and completeness. Your output will be used by other agents or presented to users."""

        super().__init__(api_key, "Searcher", system_prompt)

    def execute_task(self, task_description: str) -> str:
        """
        Execute a search/research task

        Args:
            task_description: Description of what to search for

        Returns:
            str: Search results and findings
        """
        prompt = f"""Execute this search task:

{task_description}

Provide comprehensive results with clear organization."""

        return self.send_message(prompt)


class CoderAgent(BaseAgent):
    """Agent responsible for writing code and implementing features"""

    def __init__(self, api_key: str):
        system_prompt = """You are a Coder Agent in a multi-agent system. Your role is to:

1. Write clean, efficient, and well-documented code
2. Implement features according to specifications
3. Follow best practices and coding standards
4. Provide explanations for your implementation choices

When given a coding task:
- Write production-quality code
- Include appropriate comments and documentation
- Consider edge cases and error handling
- Use clear variable names and structure
- Explain your approach when needed

Focus on code quality and maintainability. Your code will be used in real projects."""

        super().__init__(api_key, "Coder", system_prompt)

    def execute_task(self, task_description: str, context: str = "") -> str:
        """
        Execute a coding task

        Args:
            task_description: Description of what to code
            context: Additional context or requirements

        Returns:
            str: Code implementation and explanation
        """
        context_section = f'Context: {context}' if context else ''

        prompt = f"""Execute this coding task:

{task_description}

{context_section}

Provide clean, well-documented code with explanations."""

        return self.send_message(prompt)


class ReporterAgent(BaseAgent):
    """Agent responsible for creating reports and documentation"""

    def __init__(self, api_key: str):
        system_prompt = """You are a Reporter Agent in a multi-agent system. Your role is to:

1. Create clear and comprehensive reports
2. Summarize findings and results
3. Present information in an organized manner
4. Generate documentation as needed

When given a reporting task:
- Structure information logically
- Use clear headings and sections
- Highlight key points and insights
- Make complex information accessible
- Ensure professional presentation

Focus on clarity and completeness. Your reports will be used for decision-making and communication."""

        super().__init__(api_key, "Reporter", system_prompt)

    def execute_task(self, task_description: str, data: str = "") -> str:
        """
        Execute a reporting task

        Args:
            task_description: Description of the report to create
            data: Data or information to include in the report

        Returns:
            str: Formatted report
        """
        data_section = f'Data/Information to include:\n{data}' if data else ''

        prompt = f"""Execute this reporting task:

{task_description}

{data_section}

Create a well-structured and comprehensive report."""

        return self.send_message(prompt)
