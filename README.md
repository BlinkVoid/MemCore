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
- API Keys for Kimi (Moonshot), Bedrock, Gemini, or DeepSeek (configured in `.env`)

### Installation
```bash
uv sync
```

### Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Configure your LLM provider in `.env`:

**Kimi (Moonshot)** - Recommended for Chinese/English bilingual support:
```bash
LLM_PROVIDER=kimi
MOONSHOT_API_KEY=your_api_key_here
# Embedding model defaults to multilingual-e5-large (supports Chinese)
```

**AWS Bedrock**:
```bash
LLM_PROVIDER=bedrock
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION_NAME=us-east-1
```

**Google Gemini**:
```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_api_key_here
```

**DeepSeek**:
```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_api_key_here
```

> **Note on Embeddings & Languages:** By default, MemCore uses **multilingual embeddings** (`intfloat/multilingual-e5-large`, 1024-dim, 2.24GB) supporting **Chinese, English, and 100+ languages**. For English-only deployments, you can switch to `BAAI/bge-base-en-v1.5` (768-dim, 210MB) for smaller footprint. You can switch LLM providers without re-indexing, but changing the embedding model requires database re-indexing. See [Multilingual Strategy](docs/multilingual-strategy.md) and [Embedding Strategy](docs/embedding-strategy.md) for details.

3. Verify your configuration:
```bash
uv run scripts/verify_config.py
```

### Running the Gatekeeper
```bash
uv run src/memcore/main.py
```

## Documentation
- [QUICKSTART for Tomorrow](docs/QUICKSTART-TOMORROW.md) - **Start here if resuming development**
- [Development Log (2026-03-02)](docs/development-log-2026-03-02.md) - Initialization and configuration work
- [Core Concepts](docs/core-concepts.md)
- [Architecture](docs/research-memcore-architecture.md)
- [API Specification](docs/api-specification.md)
- [Implementation Plan](docs/implementation-plan.md)
- [Data Schema](docs/data-schema.md)
- [Embedding Strategy](docs/embedding-strategy.md) - Important: Read before first run
- [Multilingual Strategy](docs/multilingual-strategy.md) - Language support (Chinese, etc.)
- [Model Tier Strategy](docs/model-tier-strategy.md) - Fast vs Strong model usage
