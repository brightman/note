"""
Master Agent - Orchestrates executor agents and manages execution
"""
from base_agent import BaseAgent
from executor_agents import SearcherAgent, CoderAgent, ReporterAgent
from models import ExecutionPlan, PlanStep, SubTask, ExecutorType, TaskStatus
from typing import Dict


class MasterAgent(BaseAgent):
    """Agent responsible for orchestrating executor agents and quality control"""

    def __init__(self, api_key: str):
        system_prompt = """You are a Master Agent in a multi-agent system. Your role is to:

1. Orchestrate the execution of tasks by executor agents
2. Review and assess the quality of completed subtasks
3. Determine if work meets requirements
4. Decide when to proceed to the next step

When reviewing work:
- Check for completeness and accuracy
- Verify it addresses the task requirements
- Identify any issues or gaps
- Provide constructive feedback

Respond with quality assessments in this format:
QUALITY: [PASS/FAIL]
FEEDBACK: [Your detailed feedback]

Be thorough but fair in your assessments."""

        super().__init__(api_key, "Master", system_prompt)

        # Initialize executor agents
        self.executors: Dict[ExecutorType, BaseAgent] = {
            ExecutorType.SEARCHER: SearcherAgent(api_key),
            ExecutorType.CODER: CoderAgent(api_key),
            ExecutorType.REPORTER: ReporterAgent(api_key)
        }

    def execute_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Execute the complete plan step by step

        Args:
            plan: ExecutionPlan to execute

        Returns:
            ExecutionPlan: Updated plan with results
        """
        print(f"\n{'='*60}")
        print(f"MASTER: Starting execution of plan")
        print(f"Task: {plan.task_description}")
        print(f"Total steps: {len(plan.steps)}")
        print(f"{'='*60}\n")

        for step in plan.steps:
            print(f"\n--- STEP {step.step_number}: {step.description} ---")
            step.status = TaskStatus.IN_PROGRESS

            for subtask in step.subtasks:
                self._execute_subtask(subtask, step)

            step.status = TaskStatus.COMPLETED
            print(f"✓ Step {step.step_number} completed\n")

        print(f"\n{'='*60}")
        print("MASTER: All steps completed successfully!")
        print(f"{'='*60}\n")

        return plan

    def _execute_subtask(self, subtask: SubTask, step: PlanStep) -> None:
        """
        Execute a single subtask with quality control

        Args:
            subtask: SubTask to execute
            step: Parent step for context
        """
        print(f"\n  → Executing subtask [{subtask.executor.value}]: {subtask.description}")

        subtask.status = TaskStatus.IN_PROGRESS

        # Get the appropriate executor
        executor = self.executors[subtask.executor]

        # Execute the subtask
        result = executor.execute_task(subtask.description)

        # Review the quality
        max_retries = 2
        retry_count = 0

        while retry_count <= max_retries:
            quality_check = self._check_quality(subtask, result, step)

            if quality_check["passed"]:
                subtask.result = result
                subtask.status = TaskStatus.COMPLETED
                print(f"  ✓ Subtask completed successfully")
                print(f"  Quality feedback: {quality_check['feedback']}")
                break
            else:
                retry_count += 1
                if retry_count <= max_retries:
                    print(f"  ⚠ Quality check failed. Retry {retry_count}/{max_retries}")
                    print(f"  Feedback: {quality_check['feedback']}")

                    # Ask executor to improve
                    improvement_prompt = f"""Your previous result did not meet quality standards.

Feedback: {quality_check['feedback']}

Previous result:
{result}

Please improve your work to address the feedback."""

                    result = executor.send_message(improvement_prompt)
                else:
                    print(f"  ✗ Quality check failed after {max_retries} retries")
                    print(f"  Feedback: {quality_check['feedback']}")
                    subtask.result = result
                    subtask.status = TaskStatus.FAILED
                    break

    def _check_quality(self, subtask: SubTask, result: str, step: PlanStep) -> dict:
        """
        Check the quality of a subtask result

        Args:
            subtask: The subtask being reviewed
            result: The result to review
            step: Parent step for context

        Returns:
            dict: {"passed": bool, "feedback": str}
        """
        review_prompt = f"""Review the quality of this completed subtask.

Context - Step: {step.description}
Subtask: {subtask.description}
Executor: {subtask.executor.value}

Result:
{result}

Assess if this result adequately completes the subtask. Consider:
- Does it address the task requirements?
- Is it complete and thorough?
- Is the quality acceptable?

Respond in the specified format."""

        review = self.send_message(review_prompt)

        # Parse the review
        passed = "QUALITY: PASS" in review or "QUALITY:PASS" in review

        # Extract feedback
        feedback_start = review.find("FEEDBACK:")
        if feedback_start != -1:
            feedback = review[feedback_start + 9:].strip()
        else:
            feedback = review

        return {
            "passed": passed,
            "feedback": feedback
        }

    def get_final_summary(self, plan: ExecutionPlan) -> str:
        """
        Get a final summary of the execution

        Args:
            plan: Completed execution plan

        Returns:
            str: Summary of the execution
        """
        summary_prompt = f"""Provide a concise summary of the completed execution.

Task: {plan.task_description}

Steps completed: {len(plan.steps)}

Key results from each step:
"""

        for step in plan.steps:
            summary_prompt += f"\nStep {step.step_number}: {step.description}\n"
            for subtask in step.subtasks:
                summary_prompt += f"  - {subtask.description}: {subtask.status.value}\n"

        summary_prompt += "\nProvide a brief summary of what was accomplished."

        return self.send_message(summary_prompt)
