#!/usr/bin/env python3
"""
Benchmark: Ebbinghaus Forgetting Curve Visualization

Generates data and visualizations showing how memory recency scores decay over time
based on the Ebbinghaus forgetting curve formula: Score = e^(-dt/S)

Usage:
    uv run python benchmarks/bench_forgetting_curve.py --help
    uv run python benchmarks/bench_forgetting_curve.py --output-csv
"""

import argparse
import csv
import json
import logging
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("bench_forgetting_curve")


def calculate_recency_score(hours_elapsed: float, strength: float = 1.0) -> float:
    """
    Calculate recency score using Ebbinghaus forgetting curve.
    
    Score = e^(-dt / S)
    
    Where:
    - dt = time elapsed (in hours)
    - S = memory strength (higher = slower decay)
    
    Args:
        hours_elapsed: Time since last access in hours
        strength: Memory strength factor (default 1.0)
    
    Returns:
        Recency score between 0 and 1
    """
    return math.exp(-hours_elapsed / (strength * 24))  # Scale to days


def generate_decay_curve(
    max_days: int = 90,
    strengths: List[float] = None,
    interval_hours: int = 24
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Generate decay curve data for different memory strengths.
    
    Args:
        max_days: Maximum days to simulate
        strengths: List of memory strength values
        interval_hours: Hours between data points
    
    Returns:
        Dictionary mapping strength to list of data points
    """
    if strengths is None:
        strengths = [0.5, 1.0, 2.0, 5.0, 10.0]
    
    results = {}
    total_points = (max_days * 24) // interval_hours
    
    logger.info(f"Generating {total_points} data points over {max_days} days")
    logger.info(f"Strength values: {strengths}")
    
    for strength in strengths:
        data_points = []
        
        for hour in range(0, max_days * 24 + 1, interval_hours):
            days = hour / 24
            score = calculate_recency_score(hour, strength)
            
            # Determine if memory is "surviving" (score above threshold)
            is_surviving = score > 0.2  # 20% threshold
            
            data_points.append({
                "hours": hour,
                "days": round(days, 2),
                "recency_score": round(score, 6),
                "strength": strength,
                "is_surviving": is_surviving,
            })
        
        results[f"strength_{strength}"] = data_points
        logger.info(f"  Strength {strength}: {len(data_points)} points, "
                   f"final score = {data_points[-1]['recency_score']:.4f}")
    
    return results


def calculate_half_life(strength: float) -> float:
    """Calculate the half-life (time to reach 50% score) for a given strength."""
    # Solve: 0.5 = e^(-dt/S) => dt = -S * ln(0.5) = S * ln(2)
    return strength * math.log(2)


def calculate_survival_time(strength: float, threshold: float = 0.2) -> float:
    """Calculate time until score drops below threshold."""
    # Solve: threshold = e^(-dt/S) => dt = -S * ln(threshold)
    return -strength * math.log(threshold)


def calculate_access_needed(
    target_score: float,
    current_score: float,
    strength: float
) -> int:
    """
    Calculate how many accesses needed to boost from current to target score.
    
    Each access increases strength by a factor.
    """
    if current_score >= target_score:
        return 0
    
    # Simplified model: each access increases strength by ~20%
    accesses = 0
    s = strength
    while calculate_recency_score(0, s) < target_score and accesses < 100:
        s *= 1.2
        accesses += 1
    
    return accesses


def generate_summary_stats(curve_data: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """Generate summary statistics for the decay curves."""
    stats = {
        "half_lives": {},
        "survival_times": {},
        "final_scores": {},
    }
    
    for strength_key, data_points in curve_data.items():
        strength = float(strength_key.replace("strength_", ""))
        
        # Calculate half-life
        half_life = calculate_half_life(strength)
        stats["half_lives"][strength_key] = round(half_life, 2)
        
        # Calculate survival time (to 20% threshold)
        survival = calculate_survival_time(strength, 0.2)
        stats["survival_times"][strength_key] = round(survival, 2)
        
        # Final score
        final_score = data_points[-1]["recency_score"]
        stats["final_scores"][strength_key] = round(final_score, 6)
    
    return stats


def write_csv(curve_data: Dict[str, List[Dict]], output_path: Path):
    """Write curve data to CSV file."""
    logger.info(f"Writing CSV to: {output_path}")
    
    # Flatten all data points
    all_points = []
    for strength_key, points in curve_data.items():
        for p in points:
            all_points.append({
                "strength": p["strength"],
                "hours": p["hours"],
                "days": p["days"],
                "recency_score": p["recency_score"],
                "is_surviving": p["is_surviving"],
            })
    
    # Sort by strength then hours
    all_points.sort(key=lambda x: (x["strength"], x["hours"]))
    
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["strength", "hours", "days", "recency_score", "is_surviving"])
        writer.writeheader()
        writer.writerows(all_points)
    
    logger.info(f"  Wrote {len(all_points)} rows")


def generate_matplotlib_code(curve_data: Dict[str, List[Dict]], output_path: Path):
    """Generate standalone Python script to visualize the curves."""
    logger.info(f"Generating matplotlib code: {output_path}")
    
    code = '''#!/usr/bin/env python3
"""
Generated visualization script for Ebbinghaus forgetting curves.
Run: uv run python {output_path}
"""

import matplotlib.pyplot as plt
import json

# Curve data (embedded for standalone use)
CURVE_DATA = {curve_data_json}

def plot_forgetting_curves():
    """Plot Ebbinghaus forgetting curves for different memory strengths."""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    colors = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#3498db', '#9b59b6']
    
    for i, (strength_key, data_points) in enumerate(CURVE_DATA.items()):
        strength = float(strength_key.replace("strength_", ""))
        days = [p["days"] for p in data_points]
        scores = [p["recency_score"] for p in data_points]
        
        ax.plot(days, scores, 
                label=f"Strength = {strength}",
                color=colors[i % len(colors)],
                linewidth=2)
    
    # Add threshold line at 20%
    ax.axhline(y=0.2, color='gray', linestyle='--', alpha=0.5, label="Survival threshold (20%)")
    
    # Formatting
    ax.set_xlabel("Days Since Last Access", fontsize=12)
    ax.set_ylabel("Recency Score", fontsize=12)
    ax.set_title("Ebbinghaus Forgetting Curve: Memory Decay Over Time", fontsize=14, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, max(days))
    ax.set_ylim(0, 1.05)
    
    plt.tight_layout()
    
    # Save figure
    output_file = "{output_dir}/forgetting_curves.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Saved plot to: {{output_file}}")
    
    plt.show()

if __name__ == "__main__":
    try:
        plot_forgetting_curves()
    except ImportError:
        print("matplotlib not installed. Install with: uv add matplotlib")
        print("Or use the CSV data to create your own plots.")
'''.format(
        curve_data_json=json.dumps(curve_data, indent=2),
        output_path=output_path.name,
        output_dir=output_path.parent.as_posix()
    )
    
    with open(output_path, "w") as f:
        f.write(code)
    
    logger.info(f"  Generated: {output_path}")


def generate_markdown_table(stats: Dict[str, Any], max_days: int) -> str:
    """Generate markdown report of the benchmark."""
    lines = [
        "# Ebbinghaus Forgetting Curve Analysis",
        "",
        "## Overview",
        "",
        "This benchmark visualizes how memory recency scores decay over time using the ",
        "scientifically-grounded Ebbinghaus forgetting curve formula:",
        "",
        "```",
        "Score = e^(-dt / S)",
        "```",
        "",
        "Where:",
        "- `dt` = time elapsed (in days)",
        "- `S` = memory strength (higher = slower decay)",
        "",
        "## Half-Life Analysis",
        "",
        "The half-life is the time required for the recency score to drop to 50%.",
        "",
        "| Memory Strength | Half-Life (days) |",
        "|-----------------|------------------|",
    ]
    
    for strength_key, half_life in sorted(stats["half_lives"].items(), key=lambda x: float(x[0].replace("strength_", ""))):
        strength = strength_key.replace("strength_", "")
        lines.append(f"| {strength} | {half_life} |")
    
    lines.extend([
        "",
        "## Survival Analysis",
        "",
        "Survival time is the duration until the score drops below 20% (considered 'forgotten').",
        "",
        "| Memory Strength | Survival Time (days) | Final Score ({0}d) |".format(max_days),
        "|-----------------|----------------------|----------------------|",
    ])
    
    for strength_key in sorted(stats["survival_times"].keys(), key=lambda x: float(x.replace("strength_", ""))):
        strength = strength_key.replace("strength_", "")
        survival = stats["survival_times"][strength_key]
        final = stats["final_scores"][strength_key]
        lines.append(f"| {strength} | {survival} | {final:.4f} |")
    
    lines.extend([
        "",
        "## Key Insights",
        "",
        "1. **Higher strength = slower decay**: Doubling memory strength approximately doubles half-life",
        "2. **Exponential decay**: All curves follow the same shape, just stretched/compressed",
        "3. **Access reinforcement**: Repeated access increases strength, extending memory lifetime",
        "4. **Natural forgetting**: Unaccessed memories naturally fade without explicit deletion",
        "",
        "## Applications in MemCore",
        "",
        "- **Auto-prioritization**: Stale memories naturally rank lower in retrieval",
        "- **No hard deletion needed**: Memories fade gracefully rather than disappearing",
        "- **Reinforcement learning**: Frequent access strengthens memories automatically",
        "",
        "## Data Files",
        "",
        "- `bench_forgetting_curve.json` - Raw data in JSON format",
        "- `forgetting_curve_data.csv` - CSV for external analysis",
        "- `plot_forgetting_curves.py` - Standalone matplotlib script",
        "",
        "Generated: " + datetime.now().isoformat(),
    ])
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Ebbinghaus forgetting curve data and visualizations"
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=90,
        help="Maximum days to simulate (default: 90)"
    )
    parser.add_argument(
        "--strengths",
        type=float,
        nargs="+",
        default=[0.5, 1.0, 2.0, 5.0, 10.0],
        help="Memory strength values to simulate (default: 0.5 1.0 2.0 5.0 10.0)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=24,
        help="Hours between data points (default: 24)"
    )
    parser.add_argument(
        "--output-dir",
        default="benchmarks/results",
        help="Output directory for results (default: benchmarks/results)"
    )
    parser.add_argument(
        "--output-csv",
        action="store_true",
        help="Also output CSV format"
    )
    parser.add_argument(
        "--generate-plot-script",
        action="store_true",
        help="Generate standalone matplotlib script"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("MemCore Ebbinghaus Forgetting Curve Benchmark")
    logger.info("=" * 60)
    logger.info(f"Max days: {args.max_days}")
    logger.info(f"Strengths: {args.strengths}")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate curve data
    curve_data = generate_decay_curve(
        max_days=args.max_days,
        strengths=args.strengths,
        interval_hours=args.interval
    )
    
    # Calculate summary statistics
    stats = generate_summary_stats(curve_data)
    
    # Compile results
    results = {
        "curve_data": curve_data,
        "summary_statistics": stats,
        "parameters": {
            "max_days": args.max_days,
            "strengths": args.strengths,
            "interval_hours": args.interval,
        },
        "benchmark_metadata": {
            "timestamp": datetime.now().isoformat(),
            "formula": "Score = e^(-dt / S)",
        }
    }
    
    # Save JSON results
    json_path = output_dir / "bench_forgetting_curve.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"JSON results saved to: {json_path}")
    
    # Save CSV if requested
    if args.output_csv:
        csv_path = output_dir / "forgetting_curve_data.csv"
        write_csv(curve_data, csv_path)
    
    # Generate matplotlib script if requested
    if args.generate_plot_script:
        plot_path = output_dir / "plot_forgetting_curves.py"
        generate_matplotlib_code(curve_data, plot_path)
    
    # Generate markdown report
    md_path = output_dir / "bench_forgetting_curve.md"
    with open(md_path, "w") as f:
        f.write(generate_markdown_table(stats, args.max_days))
    logger.info(f"Markdown report saved to: {md_path}")
    
    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Results Summary")
    logger.info("=" * 60)
    logger.info("Half-Lives (days to 50% score):")
    for strength_key, half_life in sorted(stats["half_lives"].items(), key=lambda x: float(x[0].replace("strength_", ""))):
        strength = strength_key.replace("strength_", "")
        logger.info(f"  Strength {strength}: {half_life} days")
    
    logger.info("")
    logger.info("Survival Times (days to 20% threshold):")
    for strength_key, survival in sorted(stats["survival_times"].items(), key=lambda x: float(x[0].replace("strength_", ""))):
        strength = strength_key.replace("strength_", "")
        logger.info(f"  Strength {strength}: {survival} days")
    
    logger.info("")
    logger.info(f"Data points generated: {sum(len(v) for v in curve_data.values())}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
