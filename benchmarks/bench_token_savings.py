#!/usr/bin/env python3
"""
Benchmark: Token Savings from Tiered Disclosure

Measures token savings achieved through MemCore's tiered disclosure (L0, L1, L2)
compared to full memory retrieval.

Usage:
    uv run python benchmarks/bench_token_savings.py --help
    uv run python benchmarks/bench_token_savings.py --memories 100
"""

import argparse
import asyncio
import json
import logging
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from uuid import uuid4

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("bench_token_savings")

# Ensure we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Synthetic memory content of varying lengths
SHORT_MEMORY = "User prefers dark mode in all applications."

MEDIUM_MEMORY = """
Project Phoenix is the internal codename for our next-generation API platform.
The goal is to replace the legacy monolith with microservices architecture.
Key components include: authentication service (OAuth2), rate limiter (Redis-based),
API gateway (Kong), and event bus (Kafka). Timeline: Q2 planning, Q3 development,
Q4 beta launch. Stakeholders include engineering, product, and SRE teams.
Current status: architecture review complete, pending budget approval.
""".strip()

LONG_MEMORY = """
COMPREHENSIVE ARCHITECTURE DOCUMENT: Multi-Tenant SaaS Platform v3.0

EXECUTIVE SUMMARY
This document outlines the complete technical architecture for the next-generation
multi-tenant SaaS platform. The system is designed to handle 10,000+ tenants with
99.99% uptime SLA while maintaining strict data isolation and compliance with
SOC2, GDPR, and HIPAA requirements.

INFRASTRUCTURE LAYER
The platform runs on Kubernetes clusters across three AWS regions (us-east-1,
us-west-2, eu-west-1) with automated failover. Each region has:
- 3 availability zones for redundancy
- Auto-scaling node groups (min: 10, max: 100 nodes)
- Dedicated GPU nodes for ML inference workloads
- Spot instance integration for 60% cost reduction

DATA ARCHITECTURE
We employ a hybrid approach combining:
1. PostgreSQL RDS for transactional data with row-level security for tenant isolation
2. DynamoDB for high-throughput session and cache data
3. S3 with lifecycle policies for document storage
4. Redshift for analytics workloads
5. OpenSearch for full-text search across tenant data

Each tenant's data is logically isolated through:
- Database: tenant_id column on all tables with RLS policies
- S3: prefix-based isolation with IAM policies per tenant
- Search: tenant-specific indexes with field-level security

MICROSERVICES ARCHITECTURE
The platform consists of 47 microservices organized into 8 domains:
- Identity & Access (auth, permissions, audit)
- Billing & Subscriptions (invoicing, payments, usage tracking)
- Core Platform (tenant management, configuration, webhooks)
- Data Processing (ETL pipelines, data export, import)
- Analytics (reporting, dashboards, alerts)
- Integrations (third-party connectors, API marketplace)
- ML Platform (feature store, model serving, training pipelines)
- Operations (monitoring, logging, incident response)

Communication patterns:
- Synchronous: gRPC for inter-service calls with circuit breakers
- Asynchronous: Event-driven architecture using Kafka topics
- CQRS pattern for read-heavy operations

SECURITY ARCHITECTURE
Defense in depth approach:
- Edge: CloudFlare for DDoS protection and WAF
- Network: VPC isolation, security groups, NACLs
- Application: OAuth2/OIDC, mTLS between services, request signing
- Data: AES-256 encryption at rest, TLS 1.3 in transit
- Audit: Comprehensive logging with tamper-proof storage

API DESIGN
- RESTful APIs following OpenAPI 3.0 specification
- GraphQL gateway for client-optimized queries
- Webhook system with idempotency keys and retry logic
- Rate limiting: Token bucket per tenant with burst allowance

MONITORING & OBSERVABILITY
- Metrics: Prometheus + Grafana for infrastructure and business metrics
- Tracing: Jaeger for distributed tracing across all services
- Logging: ELK stack with structured JSON logging
- Alerting: PagerDuty integration with severity-based routing
- SLOs: Defined per service with error budget tracking

DEPLOYMENT PIPELINE
GitOps-based deployment using ArgoCD:
- Feature branches auto-deploy to dev environment
- PR merge triggers staging deployment with integration tests
- Production promotion requires approval and passes canary analysis
- Rollback capability through automated traffic shifting

COST OPTIMIZATION
- Reserved Instances for predictable baseline capacity
- Spot instances for batch and ML training workloads
- S3 Intelligent-Tiering for document lifecycle management
- DynamoDB auto-scaling with on-demand fallback
- Right-sizing recommendations via AWS Compute Optimizer

DISASTER RECOVERY
- RPO: 5 minutes for critical data
- RTO: 30 minutes for full platform recovery
- Automated backups with cross-region replication
- Quarterly DR drills with documented runbooks

This architecture has been reviewed by the CTO, VP Engineering, and Security team.
Next review scheduled for Q2 2025.
""".strip()


def generate_memory_variations(base_content: str, count: int) -> List[str]:
    """Generate variations of a memory with slight modifications."""
    variations = []
    modifiers = [
        " [Updated]", " [Confirmed]", " [Priority]", " [Reviewed]",
        " v2.0", " (final)", " - approved", " [2024-Q3]",
    ]
    
    for i in range(count):
        mod = modifiers[i % len(modifiers)]
        variation = base_content + f"\n\nNote: {mod.strip(' []')}"
        variations.append(variation)
    
    return variations


def estimate_tokens(text: str) -> int:
    """Estimate token count using MemCore's algorithm."""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars * 0.25)


def generate_corpus(
    short_count: int = 40,
    medium_count: int = 40,
    long_count: int = 20
) -> List[Dict[str, Any]]:
    """Generate memory corpus with varying lengths."""
    logger.info(f"Generating corpus: {short_count} short, {medium_count} medium, {long_count} long")
    
    memories = []
    
    # Short memories (100-300 tokens)
    for content in generate_memory_variations(SHORT_MEMORY, short_count):
        memories.append({
            "id": str(uuid4()),
            "content": content,
            "summary": content[:60] + "...",
            "quadrants": random.choice([["coding"], ["personal"], ["research"]]),
            "type": "raw",
            "importance": random.uniform(0.4, 0.8),
            "tokens": estimate_tokens(content),
        })
    
    # Medium memories (300-800 tokens)
    for content in generate_memory_variations(MEDIUM_MEMORY, medium_count):
        memories.append({
            "id": str(uuid4()),
            "content": content,
            "summary": "Project Phoenix API platform architecture and timeline.",
            "quadrants": random.choice([["coding"], ["research"]]),
            "type": "raw",
            "importance": random.uniform(0.6, 0.9),
            "tokens": estimate_tokens(content),
        })
    
    # Long memories (800-2000+ tokens)
    for content in generate_memory_variations(LONG_MEMORY, long_count):
        memories.append({
            "id": str(uuid4()),
            "content": content,
            "summary": "Multi-tenant SaaS platform v3.0 comprehensive architecture document.",
            "quadrants": ["research"],
            "type": "raw",
            "importance": 0.95,
            "tokens": estimate_tokens(content),
        })
    
    random.shuffle(memories)
    return memories


def simulate_l0_retrieval(memories: List[Dict], query_count: int = 50) -> Dict[str, Any]:
    """
    Simulate L0 (Index) retrieval - returns only minimal summaries.
    Average: ~5-10 tokens per memory
    """
    logger.info(f"Simulating L0 retrieval for {query_count} queries...")
    
    results = []
    for _ in range(query_count):
        # Simulate retrieving 10 memories per query
        retrieved = random.sample(memories, min(10, len(memories)))
        
        l0_items = []
        total_tokens = 0
        for mem in retrieved:
            # L0: just ID, summary, score indicator
            l0_content = f"[{mem['id'][:8]}] {mem['summary'][:50]}..."
            tokens = estimate_tokens(l0_content)
            l0_items.append({
                "id": mem["id"],
                "content": l0_content,
                "tokens": tokens,
            })
            total_tokens += tokens
        
        results.append({
            "items": l0_items,
            "total_tokens": total_tokens,
            "memory_count": len(l0_items),
        })
    
    avg_tokens = sum(r["total_tokens"] for r in results) / len(results)
    logger.info(f"  L0 average: {avg_tokens:.0f} tokens per query")
    
    return {
        "tier": "L0",
        "tokens_per_query": [r["total_tokens"] for r in results],
        "avg_tokens": avg_tokens,
        "description": "Index level - minimal summaries only",
    }


def simulate_l1_retrieval(memories: List[Dict], query_count: int = 50) -> Dict[str, Any]:
    """
    Simulate L1 (Snippet) retrieval - returns content previews.
    Average: ~50-100 tokens per memory
    """
    logger.info(f"Simulating L1 retrieval for {query_count} queries...")
    
    results = []
    for _ in range(query_count):
        # Retrieve 10 memories, promote top 5 to L1
        retrieved = random.sample(memories, min(10, len(memories)))
        
        total_tokens = 0
        items = []
        
        # L0 for all 10
        for mem in retrieved:
            l0_content = f"[{mem['id'][:8]}] {mem['summary'][:50]}..."
            total_tokens += estimate_tokens(l0_content)
        
        # L1 for top 5 (preview of content)
        high_confidence = retrieved[:5]
        for mem in high_confidence:
            preview = mem["content"][:150] + "..." if len(mem["content"]) > 150 else mem["content"]
            l1_content = f"[{mem['id'][:8]}] {mem['summary']}\n  Preview: {preview}"
            tokens = estimate_tokens(l1_content)
            items.append({
                "id": mem["id"],
                "content": l1_content,
                "tokens": tokens,
            })
            total_tokens += tokens
        
        results.append({
            "items": items,
            "total_tokens": total_tokens,
            "memory_count": len(retrieved),
        })
    
    avg_tokens = sum(r["total_tokens"] for r in results) / len(results)
    logger.info(f"  L1 average: {avg_tokens:.0f} tokens per query")
    
    return {
        "tier": "L1",
        "tokens_per_query": [r["total_tokens"] for r in results],
        "avg_tokens": avg_tokens,
        "description": "Snippet level - content previews for high-confidence matches",
    }


def simulate_l2_retrieval(memories: List[Dict], query_count: int = 50) -> Dict[str, Any]:
    """
    Simulate L2 (Full) retrieval - returns complete memory content.
    This is the baseline for comparison.
    """
    logger.info(f"Simulating L2 retrieval for {query_count} queries...")
    
    results = []
    for _ in range(query_count):
        # Retrieve 5 memories at full detail
        retrieved = random.sample(memories, min(5, len(memories)))
        
        total_tokens = 0
        items = []
        for mem in retrieved:
            tokens = mem["tokens"]
            items.append({
                "id": mem["id"],
                "content": mem["content"][:200] + "..." if len(mem["content"]) > 200 else mem["content"],
                "full_tokens": tokens,
            })
            total_tokens += tokens
        
        results.append({
            "items": items,
            "total_tokens": total_tokens,
            "memory_count": len(items),
        })
    
    avg_tokens = sum(r["total_tokens"] for r in results) / len(results)
    logger.info(f"  L2 average: {avg_tokens:.0f} tokens per query")
    
    return {
        "tier": "L2",
        "tokens_per_query": [r["total_tokens"] for r in results],
        "avg_tokens": avg_tokens,
        "description": "Full detail level - complete memory content",
    }


def calculate_savings(l2_tokens: float, comparison_tokens: float) -> Dict[str, float]:
    """Calculate token savings metrics."""
    saved = l2_tokens - comparison_tokens
    ratio = saved / l2_tokens if l2_tokens > 0 else 0
    
    return {
        "l2_baseline": l2_tokens,
        "comparison": comparison_tokens,
        "tokens_saved": saved,
        "savings_ratio": ratio,
        "savings_percent": ratio * 100,
    }


def generate_savings_distribution(
    l2_results: List[int],
    comparison_results: List[int]
) -> Dict[str, Any]:
    """Generate distribution statistics for savings."""
    savings = [l2 - comp for l2, comp in zip(l2_results, comparison_results)]
    ratios = [s / l2 if l2 > 0 else 0 for s, l2 in zip(savings, l2_results)]
    
    def percentile(lst, p):
        sorted_lst = sorted(lst)
        idx = int(len(sorted_lst) * p / 100)
        return sorted_lst[min(idx, len(sorted_lst) - 1)]
    
    return {
        "min_savings": min(savings),
        "max_savings": max(savings),
        "median_savings": percentile(savings, 50),
        "p25_savings": percentile(savings, 25),
        "p75_savings": percentile(savings, 75),
        "min_ratio": min(ratios),
        "max_ratio": max(ratios),
        "median_ratio": percentile(ratios, 50),
    }


def run_benchmark(
    memories: List[Dict],
    query_count: int = 50
) -> Dict[str, Any]:
    """Run the complete token savings benchmark."""
    logger.info(f"Running token savings benchmark with {query_count} queries...")
    
    # Simulate each tier
    l0_data = simulate_l0_retrieval(memories, query_count)
    l1_data = simulate_l1_retrieval(memories, query_count)
    l2_data = simulate_l2_retrieval(memories, query_count)
    
    # Calculate savings
    l0_savings = calculate_savings(l2_data["avg_tokens"], l0_data["avg_tokens"])
    l1_savings = calculate_savings(l2_data["avg_tokens"], l1_data["avg_tokens"])
    
    # Generate distributions
    l0_dist = generate_savings_distribution(l2_data["tokens_per_query"], l0_data["tokens_per_query"])
    l1_dist = generate_savings_distribution(l2_data["tokens_per_query"], l1_data["tokens_per_query"])
    
    return {
        "corpus_stats": {
            "total_memories": len(memories),
            "avg_tokens_per_memory": sum(m["tokens"] for m in memories) / len(memories),
            "min_tokens": min(m["tokens"] for m in memories),
            "max_tokens": max(m["tokens"] for m in memories),
        },
        "l0_results": {
            "tier": "L0",
            "avg_tokens_per_query": l0_data["avg_tokens"],
            "description": l0_data["description"],
            "savings_vs_l2": l0_savings,
            "distribution": l0_dist,
        },
        "l1_results": {
            "tier": "L1",
            "avg_tokens_per_query": l1_data["avg_tokens"],
            "description": l1_data["description"],
            "savings_vs_l2": l1_savings,
            "distribution": l1_dist,
        },
        "l2_baseline": {
            "tier": "L2",
            "avg_tokens_per_query": l2_data["avg_tokens"],
            "description": l2_data["description"],
        },
    }


def generate_markdown_table(results: Dict[str, Any]) -> str:
    """Generate markdown table of results."""
    l0 = results["l0_results"]
    l1 = results["l1_results"]
    l2 = results["l2_baseline"]
    corpus = results["corpus_stats"]
    
    lines = [
        "# Token Savings Benchmark Results",
        "",
        "## Corpus Statistics",
        "",
        f"- Total memories: {corpus['total_memories']}",
        f"- Average tokens per memory: {corpus['avg_tokens_per_memory']:.0f}",
        f"- Token range: {corpus['min_tokens']} - {corpus['max_tokens']}",
        "",
        "## Token Consumption by Tier",
        "",
        "| Tier | Description | Avg Tokens/Query | Savings vs L2 |",
        "|------|-------------|------------------|---------------|",
        f"| L0 | {l0['description']} | {l0['avg_tokens_per_query']:.0f} | {l0['savings_vs_l2']['savings_percent']:.1f}% |",
        f"| L1 | {l1['description']} | {l1['avg_tokens_per_query']:.0f} | {l1['savings_vs_l2']['savings_percent']:.1f}% |",
        f"| L2 | {l2['description']} | {l2['avg_tokens_per_query']:.0f} | 0.0% (baseline) |",
        "",
        "## Savings Distribution (L0 vs L2)",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Median savings | {l0['distribution']['median_savings']:.0f} tokens |",
        f"| P25 savings | {l0['distribution']['p25_savings']:.0f} tokens |",
        f"| P75 savings | {l0['distribution']['p75_savings']:.0f} tokens |",
        f"| Min savings | {l0['distribution']['min_savings']:.0f} tokens |",
        f"| Max savings | {l0['distribution']['max_savings']:.0f} tokens |",
        "",
        "## Savings Distribution (L1 vs L2)",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Median savings | {l1['distribution']['median_savings']:.0f} tokens |",
        f"| P25 savings | {l1['distribution']['p25_savings']:.0f} tokens |",
        f"| P75 savings | {l1['distribution']['p75_savings']:.0f} tokens |",
        "",
        "## Key Findings",
        "",
        f"- **L0 tier** achieves **{l0['savings_vs_l2']['savings_percent']:.0f}%** token savings",
        f"- **L1 tier** achieves **{l1['savings_vs_l2']['savings_percent']:.0f}%** token savings",
        f"- For typical queries, L0 saves **{l0['savings_vs_l2']['tokens_saved']:.0f}** tokens vs full retrieval",
        "",
        "Generated: " + datetime.now().isoformat(),
    ]
    
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(
        description="Benchmark token savings from MemCore's tiered disclosure"
    )
    parser.add_argument(
        "--memories",
        type=int,
        default=100,
        help="Number of memories to generate (default: 100)"
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=50,
        help="Number of test queries to simulate (default: 50)"
    )
    parser.add_argument(
        "--output-dir",
        default="benchmarks/results",
        help="Output directory for results (default: benchmarks/results)"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("MemCore Token Savings Benchmark")
    logger.info("=" * 60)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate corpus
    memories = generate_corpus(
        short_count=args.memories // 3,
        medium_count=args.memories // 3,
        long_count=args.memories // 3 + (args.memories % 3)
    )
    
    # Run benchmark
    results = run_benchmark(memories, args.queries)
    results["benchmark_metadata"] = {
        "timestamp": datetime.now().isoformat(),
        "memories": args.memories,
        "queries": args.queries,
    }
    
    # Save results
    json_path = output_dir / "bench_token_savings.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"JSON results saved to: {json_path}")
    
    md_path = output_dir / "bench_token_savings.md"
    with open(md_path, "w") as f:
        f.write(generate_markdown_table(results))
    logger.info(f"Markdown results saved to: {md_path}")
    
    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Results Summary")
    logger.info("=" * 60)
    logger.info(f"L0 (Index):     {results['l0_results']['avg_tokens_per_query']:.0f} tokens/query")
    logger.info(f"L1 (Snippet):   {results['l1_results']['avg_tokens_per_query']:.0f} tokens/query")
    logger.info(f"L2 (Full):      {results['l2_baseline']['avg_tokens_per_query']:.0f} tokens/query")
    logger.info(f"L0 Savings:     {results['l0_results']['savings_vs_l2']['savings_percent']:.1f}%")
    logger.info(f"L1 Savings:     {results['l1_results']['savings_vs_l2']['savings_percent']:.1f}%")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
