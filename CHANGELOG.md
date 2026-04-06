# Changelog

All notable changes to MemCore will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- CLI provider backend support (`cli/kimi` and `cli/claude`) for LLMInterface
  - Routes consolidation through subscription CLI tools instead of API
  - Supports Kimi CLI with proper flag handling (`--print`, `--final-message-only`, `--output-format text`)
- Direct consolidation endpoint `POST /api/run-consolidation` for batch processing
  - Supports `batch_size`, `queue_first`, and `reset_stale` parameters
  - Bypasses Strands agent for direct memory consolidation
- `-CliProvider` parameter to `start-memcore.ps1` for selecting CLI-based LLM providers
- New test suite: `tests/test_kimi_cli.py` for CLI provider regression testing
- New script: `scripts/run_consolidation.py` for standalone consolidation runs
- Quick resume documentation: `docs/QUICKSTART-TOMORROW.md` for tracking work sessions

### Fixed
- DeepSeek `stream_options` error in consolidation agent
- DeepSeek `reasoning_content` bug in `model_adapter.py` (inject empty field for assistant messages)
- Subprocess leak on CLI timeout (kill process before raising)
- Fastembed pooling warnings suppressed
- Kimi CLI invocation flags updated for proper output handling
  - Added `--max-steps-per-turn 1` and `--max-ralph-iterations 0`

### Changed
- Updated `.env.example` with new provider configurations
- Refreshed configuration files (`.mcp.json`, `.mcp.json.example`)
- Documentation updates across all docs/ files
- AGENTS.md updated with latest agent guidelines

## [0.1.0] - 2026-03-15

### Added
- Initial release of MemCore
- Tiered memory system (L0/L1/L2 disclosure)
- Ebbinghaus forgetting curve implementation
- Conflict resolution with six-level priority hierarchy
- STM-to-LTM consolidation pipeline
- MCP server interface
- Local embeddings via fastembed
- Dashboard with analytics
- Multi-provider LLM support (Kimi, Bedrock, Gemini, DeepSeek, Ollama)
