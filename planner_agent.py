"""
Planner Agent - Analyzes tasks and creates execution plans
"""
from base_agent import BaseAgent
from models import ExecutionPlan, PlanStep, SubTask, ExecutorType, TaskStatus
import json
import re


class PlannerAgent(BaseAgent):
    """Agent responsible for analyzing tasks and breaking them into execution plans"""

    def __init__(self, api_key: str):
        system_prompt = """You are a Planner Agent in a multi-agent system. Your role is to:

1. Analyze the task provided to you
2. Break it down into logical steps
3. For each step, define subtasks with specific executors
4. Create a structured execution plan

Available executor types:
- SEARCHER: For tasks involving searching, researching, gathering information, or finding data
- CODER: For tasks involving writing code, implementing features, or technical development
- REPORTER: For tasks involving creating reports, documentation, summaries, or presenting findings

You must respond with a JSON structure following this exact format:

{
  "task_description": "Brief description of the overall task",
  "steps": [
    {
      "step_number": 1,
      "description": "Description of this step",
      "subtasks": [
        {
          "description": "Specific subtask description",
          "executor": "searcher|coder|reporter"
        }
      ]
    }
  ]
}

Guidelines:
- Break down complex tasks into 3-7 major steps
- Each step can have 1-3 subtasks
- Be specific and actionable in subtask descriptions
- Choose the most appropriate executor for each subtask
- Ensure steps follow a logical sequence
- Keep descriptions clear and concise

IMPORTANT: Respond ONLY with valid JSON, no additional text."""

        super().__init__(api_key, "Planner", system_prompt)

    def create_plan(self, task_description: str) -> ExecutionPlan:
        """
        Create an execution plan from a task description

        Args:
            task_description: Clear description of the task

        Returns:
            ExecutionPlan: Structured execution plan
        """
        prompt = f"""Analyze this task and create a detailed execution plan:

Task: {task_description}

Provide the execution plan in the specified JSON format."""

        response = self.send_message(prompt)

        # Extract JSON from response (in case there's any extra text)
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            response = json_match.group()

        # Parse the JSON response
        try:
            plan_data = json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse planner response as JSON: {e}\nResponse: {response}")

        # Convert to ExecutionPlan object
        plan = self._parse_plan(plan_data)
        return plan

    def _parse_plan(self, plan_data: dict) -> ExecutionPlan:
        """Parse JSON data into ExecutionPlan object"""
        steps = []

        for step_data in plan_data.get("steps", []):
            subtasks = []

            for subtask_data in step_data.get("subtasks", []):
                executor_str = subtask_data["executor"].lower()
                executor = ExecutorType(executor_str)

                subtask = SubTask(
                    description=subtask_data["description"],
                    executor=executor
                )
                subtasks.append(subtask)

            step = PlanStep(
                step_number=step_data["step_number"],
                description=step_data["description"],
                subtasks=subtasks
            )
            steps.append(step)

        return ExecutionPlan(
            task_description=plan_data["task_description"],
            steps=steps
        )
