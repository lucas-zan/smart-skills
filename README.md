# Smart Skills

A centralized repository for advanced, reusable AI assistant skills. These skills provide standardized, robust workflows to extend the capabilities of AI agents, making them more reliable at handling complex, multi-step tasks.

## 📦 Available Skills

- **[git-orchestrator](./git-orchestrator/README.md)**: A robust skill designed to manage Git and GitHub delivery processes systematically. Provides repeatable workflows for branch creation, PR generation, code verification, direct `share-and-land` operations, and automated release triggering.

## 🚀 Getting Started

### 1. Integration

To use these skills with your agent, you can typically place or mount this repository in your project's `skills/` directory, or instruct the agent to read specific skills from this path.

### 2. Configuration

Some skills (like `git-orchestrator`) may require sensitive environment variables (e.g., API tokens). 

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your actual configuration values (e.g., `CLAW_GITHUB_TOKEN`).

> **Note**: Be sure to reload your shell or agent context after updating environment variables so your agent can properly authenticate network requests.

## 🛠 Adding a New Skill

To introduce a new skill to this repository, create a dedicated directory that contains:

1. **`SKILL.md`** (Required): The main instruction file containing triggers, rules, and workflows for the AI agent.
2. **`README.md`**: Human-readable documentation for developers explaining what the skill does and its limitations.
3. **`scripts/`**: Executable scripts (Bash, Python, etc.) that the agent will invoke to perform actions reliably.
4. **`tests/`** & **`examples/`**: Verification scripts and usage examples to test the workflow logic.

## 🤝 Contributing

Contributions to enhance existing workflows or add new skills are highly encouraged.
When contributing, please ensure your changes include appropriate documentation updates and follow existing structures.
