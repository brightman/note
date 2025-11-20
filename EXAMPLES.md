# Usage Examples

This document provides detailed examples of using the Multi-Agent System.

## Example 1: Simple Research Task

### User Input
```
Task: Research the benefits of TypeScript over JavaScript
```

### Expected Flow

**Phase 1: Clarification**
- Guider asks about scope, target audience, depth of analysis
- User provides additional context
- Task clarified: "Compare TypeScript and JavaScript, focusing on type safety, developer experience, and tooling benefits"

**Phase 2: Planning**
```
Step 1: Research TypeScript benefits
  - [SEARCHER] Research TypeScript type safety features
  - [SEARCHER] Research TypeScript developer tooling

Step 2: Research JavaScript characteristics
  - [SEARCHER] Research JavaScript flexibility and use cases

Step 3: Create comparison report
  - [REPORTER] Compile comprehensive comparison report
```

**Phase 3: Execution**
- Searcher executes research tasks
- Master reviews quality of findings
- Reporter creates structured report

**Phase 4: Summary**
- Final report delivered with key findings

---

## Example 2: Development Task

### User Input
```
Task: Create a Python script to analyze CSV files
```

### Expected Flow

**Phase 1: Clarification**
```
GUIDER: What kind of analysis would you like to perform?
USER: Calculate basic statistics - mean, median, standard deviation

GUIDER: Should the script handle missing values? Any specific CSV format?
USER: Yes, skip rows with missing values. Standard CSV with headers.

GUIDER: Where should the results be output?
USER: Print to console and save to a text file
```

**Phase 2: Planning**
```
Step 1: Design the solution
  - [SEARCHER] Research Python CSV analysis libraries
  - [CODER] Design script structure

Step 2: Implement the script
  - [CODER] Write CSV reader and statistics calculator
  - [CODER] Implement output formatting

Step 3: Create documentation
  - [REPORTER] Write usage documentation
```

**Phase 3: Execution**
- Searcher finds pandas and standard library options
- Coder implements the script
- Master validates code quality
- Reporter creates documentation

---

## Example 3: Complex Mixed Task

### User Input
```
Task: I want to understand and implement a simple REST API for a todo app
```

### Expected Flow

**Phase 1: Clarification**
```
GUIDER: What language/framework would you prefer?
USER: Python with Flask

GUIDER: What features should the API support?
USER: CRUD operations - create, read, update, delete todos

GUIDER: Should I include data persistence?
USER: Yes, use SQLite
```

**Phase 2: Planning**
```
Step 1: Research REST API best practices
  - [SEARCHER] Research Flask REST API patterns
  - [SEARCHER] Research SQLite integration with Flask

Step 2: Design the API
  - [CODER] Design database schema
  - [CODER] Plan API endpoints structure

Step 3: Implement the API
  - [CODER] Create Flask application skeleton
  - [CODER] Implement CRUD endpoints
  - [CODER] Add SQLite integration

Step 4: Documentation
  - [REPORTER] Create API documentation
  - [REPORTER] Write setup and usage guide
```

**Phase 3: Execution**
- All subtasks executed with quality checks
- Master ensures code quality and completeness

---

## Example 4: Analysis and Reporting

### User Input
```
Task: Analyze trends in AI development over the last 5 years
```

### Expected Flow

**Phase 1: Clarification**
```
GUIDER: What aspects of AI development interest you most?
USER: Focus on large language models and computer vision

GUIDER: What format should the final deliverable be?
USER: A detailed report with timeline and key milestones

GUIDER: Any specific sources or perspectives to include?
USER: Include both academic and industry perspectives
```

**Phase 2: Planning**
```
Step 1: Research LLM developments
  - [SEARCHER] Research GPT series evolution
  - [SEARCHER] Research other major LLM breakthroughs

Step 2: Research computer vision advances
  - [SEARCHER] Research vision transformer models
  - [SEARCHER] Research practical CV applications

Step 3: Compile timeline
  - [REPORTER] Create chronological timeline of developments

Step 4: Final report
  - [REPORTER] Create comprehensive analysis report
```

---

## Tips for Best Results

### 1. Be Specific During Clarification
- Provide clear requirements
- Specify constraints and preferences
- Mention expected output format

### 2. Review the Plan
- Check that steps are logical
- Ensure executor assignments make sense
- Confirm before execution starts

### 3. Save Important Results
- Use the save feature for valuable outputs
- Results include complete execution history

### 4. Task Complexity Guidelines

**Simple Tasks** (1-2 steps):
- Single research query
- Basic code snippet
- Simple report generation

**Medium Tasks** (3-5 steps):
- Multi-faceted research
- Small application development
- Comparative analysis

**Complex Tasks** (5+ steps):
- Full application development
- Comprehensive research with implementation
- Multi-stage analysis and reporting

---

## Common Task Patterns

### Research → Report
```
1. Searcher gathers information
2. Reporter compiles findings
```

### Research → Code → Document
```
1. Searcher finds best practices
2. Coder implements solution
3. Reporter creates documentation
```

### Analysis → Code → Report
```
1. Searcher analyzes requirements
2. Coder creates tools/implementations
3. Reporter summarizes results
```

---

## Troubleshooting Examples

### Issue: Task Not Clear After First Message
**Solution**: Continue conversation with Guider, provide more details

### Issue: Plan Seems Incorrect
**Solution**: Don't confirm execution, restart and clarify better

### Issue: Subtask Failed Quality Check
**System**: Automatically retries up to 2 times with feedback

### Issue: Want to Change Task Mid-Execution
**Solution**: Currently not supported - stop and restart
(Feature could be added in future versions)
