# MemCore Benchmarks

This directory contains benchmark scripts for measuring MemCore's performance against the metrics defined in the comparison document.

## Quick Start

Run all benchmarks:

```bash
# Run from project root
uv run python benchmarks/bench_retrieval_precision.py
uv run python benchmarks/bench_token_savings.py
uv run python benchmarks/bench_consolidation.py
uv run python benchmarks/bench_forgetting_curve.py --output-csv --generate-plot-script
```

## Benchmark Overview

### 1. bench_retrieval_precision.py

**Purpose:** Measures retrieval precision@k comparing raw vector search vs MemCore's multi-factor scoring.

**What it measures:**
- Precision@1, Precision@5, Precision@10
- Comparison between raw vector similarity vs MemCore's combined scoring (relevance + recency + importance)

**Usage:**
```bash
uv run python benchmarks/bench_retrieval_precision.py --memories 500 --queries 50
```

**Options:**
- `--memories`: Number of synthetic memories to create (default: 500)
- `--queries`: Number of test queries to run (default: 50)
- `--w-rel`: Weight for relevance (default: 0.5)
- `--w-rec`: Weight for recency (default: 0.3)
- `--w-imp`: Weight for importance (default: 0.2)
- `--collection`: Qdrant collection name (default: bench_retrieval_precision)
- `--qdrant-path`: Path for test Qdrant storage (default: data/benchmark_qdrant)
- `--keep-collection`: Keep test collection after run

**Output:**
- `results/bench_retrieval_precision.json` - Raw results
- `results/bench_retrieval_precision.md` - Markdown table

---

### 2. bench_token_savings.py

**Purpose:** Measures token savings from MemCore's tiered disclosure (L0, L1, L2).

**What it measures:**
- Token consumption at each disclosure tier
- Savings ratio vs full retrieval (L2 baseline)
- Distribution of savings across different memory lengths

**Usage:**
```bash
uv run python benchmarks/bench_token_savings.py --memories 100 --queries 50
```

**Options:**
- `--memories`: Number of memories to generate (default: 100)
- `--queries`: Number of test queries to simulate (default: 50)

**Output:**
- `results/bench_token_savings.json` - Raw results
- `results/bench_token_savings.md` - Markdown table

**Key Metrics:**
- L0 (Index): Minimal summaries only (~5-10 tokens per memory)
- L1 (Snippet): Content previews (~50-100 tokens per memory)
- L2 (Full): Complete memory content (100-2000+ tokens)

---

### 3. bench_consolidation.py

**Purpose:** Measures consolidation pipeline quality.

**What it measures:**
- Deduplication ratio (duplicate memories identified)
- Fact extraction count (atomic facts extracted)
- Conflict detection accuracy (conflicting memories identified)

**Usage:**
```bash
uv run python benchmarks/bench_consolidation.py --use-mock
```

**Options:**
- `--use-mock`: Use deterministic mock LLM (default: True, required for CI)
- `--verbose`: Enable debug logging

**Output:**
- `results/bench_consolidation.json` - Raw results
- `results/bench_consolidation.md` - Markdown table

**Test Data:**
The benchmark uses 20 sets of 5 related memories each, covering:
- Coffee preferences, coding style, project info
- Dietary restrictions (with contradictions), work schedule
- Tech stack (with duplicates), location, learning goals
- Communication preferences (with conflicts), reading habits

---

### 4. bench_forgetting_curve.py

**Purpose:** Visualizes Ebbinghaus decay curves for memory recency scoring.

**What it measures:**
- Recency score decay over time for different memory strengths
- Half-life calculations
- Survival time (time until score drops below 20%)

**Usage:**
```bash
# Basic run
uv run python benchmarks/bench_forgetting_curve.py

# With CSV output and matplotlib script
uv run python benchmarks/bench_forgetting_curve.py --output-csv --generate-plot-script

# Custom parameters
uv run python benchmarks/bench_forgetting_curve.py --max-days 180 --strengths 0.5 1.0 2.0 5.0 10.0 20.0
```

**Options:**
- `--max-days`: Maximum days to simulate (default: 90)
- `--strengths`: Memory strength values (default: 0.5 1.0 2.0 5.0 10.0)
- `--interval`: Hours between data points (default: 24)
- `--output-csv`: Also output CSV format
- `--generate-plot-script`: Generate standalone matplotlib script

**Output:**
- `results/bench_forgetting_curve.json` - Raw data
- `results/bench_forgetting_curve.md` - Markdown report
- `results/forgetting_curve_data.csv` - CSV data (if --output-csv)
- `results/plot_forgetting_curves.py` - Matplotlib script (if --generate-plot-script)

**Formula:**
```
Score = e^(-dt / S)
```
Where:
- `dt` = time elapsed (in days)
- `S` = memory strength (higher = slower decay)

---

## Results Directory

All benchmarks write results to `benchmarks/results/`:

```
benchmarks/results/
├── bench_retrieval_precision.json
├── bench_retrieval_precision.md
├── bench_token_savings.json
├── bench_token_savings.md
├── bench_consolidation.json
├── bench_consolidation.md
├── bench_forgetting_curve.json
├── bench_forgetting_curve.md
├── forgetting_curve_data.csv
└── plot_forgetting_curves.py
```

## CI Integration

All benchmarks are designed for CI environments:

1. **Deterministic results:** Use fixed seeds and mock LLM where possible
2. **No external dependencies:** Mock LLM avoids API costs in CI
3. **Configurable paths:** All file paths are configurable via arguments
4. **Exit codes:** Non-zero exit on failure for CI detection
5. **JSON output:** Machine-readable results for downstream processing

Example GitHub Actions workflow:

```yaml
name: Benchmarks
on: [push]
jobs:
  benchmarks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run python benchmarks/bench_retrieval_precision.py --queries 20
      - run: uv run python benchmarks/bench_token_savings.py --queries 20
      - run: uv run python benchmarks/bench_consolidation.py --use-mock
      - run: uv run python benchmarks/bench_forgetting_curve.py
      - uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: benchmarks/results/
```

## Interpreting Results

### Retrieval Precision

- **Precision@1**: How often the top result is relevant
- **Precision@5**: Relevance in top 5 results
- **Precision@10**: Relevance in top 10 results

MemCore's multi-factor scoring should show improvement over raw vector search by incorporating recency and importance.

### Token Savings

- **L0 savings**: Typically 70-90% vs full retrieval
- **L1 savings**: Typically 40-60% vs full retrieval

Higher savings with larger memories. L0 is sufficient for initial retrieval; L1 for high-confidence matches.

### Consolidation Quality

- **Deduplication ratio**: 10-30% for realistic data with some redundancy
- **Fact extraction**: Should extract 1-3 atomic facts per memory
- **Conflict detection**: Should identify explicit contradictions (e.g., vegetarian vs pescatarian)

### Forgetting Curves

- **Half-life**: Time to reach 50% recency score
  - Strength 1.0: ~0.7 days
  - Strength 5.0: ~3.5 days
  - Strength 10.0: ~7 days

- **Survival**: Time until score < 20% (effectively "forgotten")
  - Strength 1.0: ~1.6 days
  - Strength 5.0: ~8 days
  - Strength 10.0: ~16 days

## Dependencies

All benchmarks use the project's existing dependencies:

- `qdrant-client` - Vector storage (retrieval benchmark)
- Standard library only (other benchmarks)

Optional for visualization:
- `matplotlib` - For plotting forgetting curves

Install with:
```bash
uv add --dev matplotlib
```

## Contributing

When adding new benchmarks:

1. Follow the existing script structure
2. Use Python logging (not print)
3. Support argparse for configuration
4. Write results to `results/` directory
5. Generate both JSON and Markdown output
6. Include docstring with usage examples
7. Use deterministic behavior for CI compatibility
