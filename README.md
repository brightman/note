# Multi-Agent System with Claude

A sophisticated multi-agent system built with the Anthropic Claude Python SDK. This system coordinates multiple specialized AI agents to clarify, plan, and execute complex tasks with quality control.

## Overview

This multi-agent system features a hierarchical workflow with six specialized agents:

### Agents

1. **Guider Agent** - Interacts with users to clarify task requirements through conversational dialogue
2. **Planner Agent** - Analyzes tasks and breaks them down into structured execution plans
3. **Master Agent** - Orchestrates executor agents, performs quality control, and manages workflow
4. **Searcher Agent** - Executes research and information gathering tasks
5. **Coder Agent** - Handles coding and implementation tasks
6. **Reporter Agent** - Creates reports, documentation, and summaries

### Workflow

```
User Input
    ↓
[Guider] ──→ Clarifies task with user
    ↓
[Planner] ──→ Breaks down into steps & subtasks
    ↓
[Master] ──→ Coordinates execution
    ├─→ [Searcher] for research tasks
    ├─→ [Coder] for coding tasks
    └─→ [Reporter] for documentation tasks
    ↓
Quality Control & Summary
```

## Features

- **Interactive Task Clarification** - Natural conversation to understand requirements
- **Intelligent Planning** - Automatic task breakdown into logical steps
- **Quality Control** - Automated review and retry mechanism
- **Specialized Executors** - Task-specific agents for optimal results
- **Progress Tracking** - Real-time status updates during execution
- **Result Persistence** - Save execution results to JSON files

## Installation

### Prerequisites

- Python 3.8 or higher
- Anthropic API key

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd note
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your API key:
```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
```

## Usage

### Running the System

```bash
python main.py
```

### Example Interaction

```
PHASE 1: TASK CLARIFICATION
============================
GUIDER: Hello! Please tell me what task you'd like to accomplish...

YOU: I need to research Python web frameworks and create a comparison report

GUIDER: I'd be happy to help! To create a comprehensive comparison, could you tell me:
1. Which frameworks are you interested in? (e.g., Django, Flask, FastAPI)
2. What aspects should I compare? (e.g., performance, learning curve, features)
3. Who is the target audience for this report?

YOU: Compare Django, Flask, and FastAPI. Focus on performance and ease of use for beginners.

GUIDER: [TASK_CLEAR] Perfect! I'll research and compare Django, Flask, and FastAPI...

PHASE 2: PLANNING
=================
Step 1: Research each framework
  1. [SEARCHER] Research Django features and characteristics
  2. [SEARCHER] Research Flask features and characteristics
  3. [SEARCHER] Research FastAPI features and characteristics

Step 2: Create comparison report
  1. [REPORTER] Compile findings into structured comparison report

...
```

## Project Structure

```
note/
├── main.py              # Main application entry point
├── base_agent.py        # Base agent class with Claude integration
├── guider_agent.py      # Guider agent implementation
├── planner_agent.py     # Planner agent implementation
├── master_agent.py      # Master orchestrator agent
├── executor_agents.py   # Searcher, Coder, Reporter agents
├── models.py            # Data models and structures
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
└── README.md           # This file
```

## Architecture

### Agent Hierarchy

- **Guider** - User-facing agent for task clarification
- **Planner** - Strategic planning and task decomposition
- **Master** - Central orchestrator and quality controller
  - **Searcher** - Research and information gathering
  - **Coder** - Code implementation
  - **Reporter** - Documentation and reporting

### Communication Flow

1. User communicates with Guider until task is clear
2. Guider passes clarified task to Planner
3. Planner creates structured ExecutionPlan
4. Master receives plan and executes each step:
   - Assigns subtasks to appropriate executors
   - Reviews completed work for quality
   - Requests improvements if needed (up to 2 retries)
   - Proceeds to next step when quality is acceptable
5. Master provides final summary to user

## Data Models

### ExecutionPlan
```python
{
  "task_description": str,
  "steps": [PlanStep, ...]
}
```

### PlanStep
```python
{
  "step_number": int,
  "description": str,
  "subtasks": [SubTask, ...],
  "status": TaskStatus
}
```

### SubTask
```python
{
  "description": str,
  "executor": ExecutorType,  # searcher|coder|reporter
  "status": TaskStatus,
  "result": str
}
```

## Configuration

### Environment Variables

- `ANTHROPIC_API_KEY` - Your Anthropic API key (required)

### Model Configuration

The system uses `claude-sonnet-4-20250514` by default. You can modify the model in `base_agent.py`.

## Advanced Usage

### Saving Results

After execution, you'll be prompted to save results:
```
Would you like to save the results to a file? (yes/no): yes
Enter filename (default: results.json): my_task_results.json
```

Results include the complete execution plan with all subtask results.

### Custom Agents

To add new executor types:

1. Create agent class in `executor_agents.py`:
```python
class NewAgent(BaseAgent):
    def __init__(self, api_key: str):
        system_prompt = "Your role description..."
        super().__init__(api_key, "NewAgent", system_prompt)

    def execute_task(self, task_description: str) -> str:
        # Implementation
        pass
```

2. Add to `ExecutorType` enum in `models.py`
3. Register in `MasterAgent.__init__()` executors dictionary

## Troubleshooting

### API Key Issues
```
Error: ANTHROPIC_API_KEY not found in environment variables.
```
Solution: Ensure `.env` file exists with valid API key.

### JSON Parsing Errors
If Planner fails to generate valid JSON, check the response format in logs and ensure the system prompt is correctly formatted.

### Quality Check Failures
If subtasks repeatedly fail quality checks, review the Master's quality criteria or adjust the executor's system prompts for better output.

## Examples

### Example 1: Research Task
```
Task: Research climate change solutions and create a summary report
- Searcher gathers information on renewable energy, carbon capture, etc.
- Reporter compiles findings into structured report
```

### Example 2: Development Task
```
Task: Create a REST API for user management
- Planner breaks down into: design, implementation, documentation
- Coder implements the API endpoints
- Reporter creates API documentation
```

### Example 3: Mixed Task
```
Task: Analyze competitors and propose new features
- Searcher researches competitor products
- Coder creates feature comparison matrix (code/data)
- Reporter compiles strategic recommendations
```

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is provided as-is for educational and development purposes.

## Support

For issues or questions:
1. Check this README for common solutions
2. Review error messages and stack traces
3. Open an issue with detailed information about your problem

---

Built with Claude by Anthropic