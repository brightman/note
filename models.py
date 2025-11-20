"""
Data models for the multi-agent system
"""
from dataclasses import dataclass
from typing import List, Literal
from enum import Enum


class ExecutorType(str, Enum):
    """Types of executor agents"""
    SEARCHER = "searcher"
    CODER = "coder"
    REPORTER = "reporter"


class TaskStatus(str, Enum):
    """Status of a task or subtask"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SubTask:
    """Represents a subtask within a plan step"""
    description: str
    executor: ExecutorType
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""

    def to_dict(self):
        return {
            "description": self.description,
            "executor": self.executor.value,
            "status": self.status.value,
            "result": self.result
        }


@dataclass
class PlanStep:
    """Represents a step in the execution plan"""
    step_number: int
    description: str
    subtasks: List[SubTask]
    status: TaskStatus = TaskStatus.PENDING

    def to_dict(self):
        return {
            "step_number": self.step_number,
            "description": self.description,
            "subtasks": [st.to_dict() for st in self.subtasks],
            "status": self.status.value
        }


@dataclass
class ExecutionPlan:
    """Complete execution plan from Planner"""
    task_description: str
    steps: List[PlanStep]

    def to_dict(self):
        return {
            "task_description": self.task_description,
            "steps": [step.to_dict() for step in self.steps]
        }
