#!/usr/bin/env python3
"""
Multi-Agent System Console Application

A sophisticated multi-agent system using Claude that coordinates:
- Guider: Clarifies tasks with users
- Planner: Breaks down tasks into execution plans
- Master: Orchestrates executors and ensures quality
- Executors: Searcher, Coder, Reporter
"""

import os
import sys
import json
from dotenv import load_dotenv

from guider_agent import GuiderAgent
from planner_agent import PlannerAgent
from master_agent import MasterAgent
from models import ExecutionPlan


class MultiAgentSystem:
    """Main orchestrator for the multi-agent system"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.guider = GuiderAgent(api_key)
        self.planner = PlannerAgent(api_key)
        self.master = MasterAgent(api_key)

    def run(self):
        """Run the multi-agent system workflow"""
        print("=" * 70)
        print(" " * 15 + "MULTI-AGENT SYSTEM")
        print(" " * 10 + "Powered by Claude Agent SDK")
        print("=" * 70)
        print("\nWelcome! I'm here to help you accomplish complex tasks.")
        print("I'll clarify your needs, plan the work, and execute it with quality control.")
        print("\nType 'quit' or 'exit' to stop at any time.")
        print("=" * 70)

        # Phase 1: Task Clarification with Guider
        task_description = self._clarify_task()

        if not task_description:
            print("\nTask clarification cancelled. Goodbye!")
            return

        # Phase 2: Planning with Planner
        print("\n" + "=" * 70)
        print("PHASE 2: PLANNING")
        print("=" * 70)
        print("\nAnalyzing task and creating execution plan...")

        try:
            plan = self.planner.create_plan(task_description)
        except Exception as e:
            print(f"\n✗ Error creating plan: {e}")
            return

        self._display_plan(plan)

        # Ask for confirmation
        confirm = input("\nProceed with this plan? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("\nExecution cancelled. Goodbye!")
            return

        # Phase 3: Execution with Master
        print("\n" + "=" * 70)
        print("PHASE 3: EXECUTION")
        print("=" * 70)

        try:
            completed_plan = self.master.execute_plan(plan)
        except Exception as e:
            print(f"\n✗ Error during execution: {e}")
            import traceback
            traceback.print_exc()
            return

        # Phase 4: Final Summary
        print("\n" + "=" * 70)
        print("PHASE 4: SUMMARY")
        print("=" * 70)

        summary = self.master.get_final_summary(completed_plan)
        print(f"\n{summary}")

        # Optionally save results
        self._save_results(completed_plan)

        print("\n" + "=" * 70)
        print("Task completed successfully! Thank you for using the Multi-Agent System.")
        print("=" * 70)

    def _clarify_task(self) -> str:
        """Phase 1: Clarify the task with the user"""
        print("\n" + "=" * 70)
        print("PHASE 1: TASK CLARIFICATION")
        print("=" * 70)
        print("\nLet me help you clarify your task. Please describe what you'd like to accomplish.\n")

        # Initial greeting from Guider
        greeting = "Hello! I'm your Guider agent. Please tell me what task you'd like to accomplish, and I'll ask questions to ensure I understand your needs clearly."
        print(f"GUIDER: {greeting}\n")

        task_clear = False
        task_summary = ""

        while not task_clear:
            user_input = input("YOU: ").strip()

            if user_input.lower() in ['quit', 'exit']:
                return ""

            if not user_input:
                print("Please enter a message.\n")
                continue

            try:
                response, task_clear = self.guider.chat(user_input)
                print(f"\nGUIDER: {response}\n")

                if task_clear:
                    task_summary = self.guider.get_task_summary()

            except Exception as e:
                print(f"\n✗ Error communicating with Guider: {e}\n")
                continue

        print("\n" + "-" * 70)
        print("Task Clarification Complete!")
        print("-" * 70)
        print(f"\nTask Summary:\n{task_summary}\n")

        return task_summary

    def _display_plan(self, plan: ExecutionPlan):
        """Display the execution plan in a readable format"""
        print("\n" + "-" * 70)
        print("EXECUTION PLAN")
        print("-" * 70)
        print(f"\nTask: {plan.task_description}\n")

        for step in plan.steps:
            print(f"Step {step.step_number}: {step.description}")

            for i, subtask in enumerate(step.subtasks, 1):
                print(f"  {i}. [{subtask.executor.value.upper()}] {subtask.description}")

            print()

        print("-" * 70)

    def _save_results(self, plan: ExecutionPlan):
        """Save execution results to a file"""
        save = input("\nWould you like to save the results to a file? (yes/no): ").strip().lower()

        if save not in ['yes', 'y']:
            return

        filename = input("Enter filename (default: results.json): ").strip()
        if not filename:
            filename = "results.json"

        if not filename.endswith('.json'):
            filename += '.json'

        try:
            with open(filename, 'w') as f:
                json.dump(plan.to_dict(), f, indent=2)
            print(f"\n✓ Results saved to {filename}")
        except Exception as e:
            print(f"\n✗ Error saving results: {e}")


def main():
    """Main entry point"""
    # Load environment variables
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in environment variables.")
        print("Please create a .env file with your API key:")
        print("  ANTHROPIC_API_KEY=your_api_key_here")
        sys.exit(1)

    # Create and run the multi-agent system
    system = MultiAgentSystem(api_key)

    try:
        system.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
