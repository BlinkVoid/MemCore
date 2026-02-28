# Initial Goal: MemCore - Standalone AI Memory Management System

The goal of this project is to create a robust, standalone memory management system for AI agents, moving beyond isolated short-term and long-term memory attempts.

## Key Requirements
- **Standalone System:** A centralized memory system accessible across different repositories, systems, and tools.
- **LLM Integration:** Support for both local LLMs and cloud-based services (e.g., Kimi K2.5, AWS Bedrock, DeepSeek).
- **Strand SDK:** The AI agent will run as a watched process using the Strand SDK.
- **MCP Integration:**
  - Acts as a gatekeeper with a set of MCP (Model Context Protocol) tools for self-management.
  - Responds to external MCP client requests to retrieve memory and provide context.
- **Memory Consolidation:** Ability to consolidate memories for efficient retrieval and context provision.

## Phased Approach
1. **Research:** Explore existing AI memory management methodologies, ArXiv research, and relevant open-source projects (specifically ByteDance's `openviking`).
2. **Architecture Design:** Define the system architecture and detailed requirements based on research findings.
3. **Implementation:** Build the core memory system, SDK integration, and MCP interfaces.
