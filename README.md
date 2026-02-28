# MemCore

**MemCore** is a standalone, agentic memory management system designed to serve as a centralized "brain" for AI agents across multiple systems and tools.

## Core Features
- **Tiered Context Disclosure:** Optimized L0 (Index), L1 (Snippet), and L2 (Full Detail) retrieval to minimize noise and token costs.
- **Agentic Gatekeeping:** A watched process (Strand SDK) that manages memory lifecycle, consolidation, and conflict resolution.
- **Dynamic Scoring:** Multi-factor retrieval based on **Relevance**, **Recency** (Ebbinghaus curve), and **Importance**.
- **Memory Consolidation:** Periodic background processing to convert short-term interactions into long-term facts and SOPs.
- **MCP Native:** Exposes its capabilities via the Model Context Protocol for seamless integration with any MCP-compatible client.

## Quick Start

### Prerequisites
- Python 3.12+
- `uv` (Fast Python package manager)
- API Keys for Kimi K2.5, Bedrock, or DeepSeek (configured in `.env`)

### Installation
```bash
uv sync
```

### Running the Gatekeeper
```bash
uv run src/memcore/main.py
```

## Documentation
- [Core Concepts](docs/core-concepts.md)
- [Architecture](docs/research-memcore-architecture.md)
- [API Specification](docs/api-specification.md)
- [Implementation Plan](docs/implementation-plan.md)
- [Data Schema](docs/data-schema.md)
