#!/usr/bin/env python3
"""
Benchmark: Retrieval Precision@K

Measures retrieval precision@k comparing raw vector search vs MemCore's 
multi-factor scoring (relevance + recency + importance + feedback boost).

Usage:
    uv run python benchmarks/bench_retrieval_precision.py --help
    uv run python benchmarks/bench_retrieval_precision.py --collection test_precision
"""

import argparse
import asyncio
import json
import logging
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
from uuid import uuid4

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("bench_retrieval_precision")

# Ensure we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
except ImportError as e:
    logger.error(f"Missing dependency: {e}. Install with: uv add qdrant-client")
    sys.exit(1)

# Synthetic memory content templates by quadrant
MEMORY_TEMPLATES = {
    "coding": [
        "Python decorator pattern: Use @functools.wraps to preserve function metadata when wrapping.",
        "Asyncio best practice: Always await coroutines, never call them directly.",
        "Type hints: Use Optional[T] instead of Union[T, None] for cleaner code.",
        "Docker optimization: Multi-stage builds reduce final image size significantly.",
        "Rust ownership: Each value has a single owner; borrowing prevents data races.",
        "GraphQL vs REST: GraphQL reduces over-fetching but adds query complexity.",
        "Database indexing: B-tree indexes excel at range queries; hash indexes for equality.",
        "Kubernetes pods: The smallest deployable unit; containers share network/IPC.",
        "CSS Grid: Two-dimensional layout system; combines with Flexbox for responsive design.",
        "React hooks: useEffect cleanup functions prevent memory leaks in subscriptions.",
    ],
    "personal": [
        "Birthday: March 15th. Prefer small gatherings over large parties.",
        "Dietary restriction: Lactose intolerant. Prefer oat milk in coffee.",
        "Work schedule: Most productive in mornings, 6-10 AM.",
        "Exercise routine: Run 5km three times weekly, typically Monday/Wednesday/Friday.",
        "Travel preference: Window seat on flights, aisle for train journeys.",
        "Reading habit: Enjoys sci-fi and non-fiction; currently reading Dune.",
        "Music taste: Indie folk and jazz; favorite artists include Bon Iver and Coltrane.",
        "Communication style: Prefers async messages over synchronous calls.",
        "Weekend activity: Hiking local trails with dog on Saturday mornings.",
        "Coffee order: Single-origin pour-over, black, no sugar.",
    ],
    "research": [
        "Transformer architecture: Self-attention mechanism enables parallelization.",
        "LLM scaling laws: Loss decreases predictably with model size and data.",
        "Retrieval augmentation: RAG reduces hallucination but adds latency.",
        "MoE models: Mixture of Experts activates subsets, reducing inference cost.",
        "Constitutional AI: RLHF alternative using principles instead of human labels.",
        "Diffusion models: Iterative denoising generates high-quality images.",
        "Quantization: INT8 inference reduces memory 4x with minimal accuracy loss.",
        "Chain-of-thought: Intermediate reasoning steps improve arithmetic accuracy.",
        "Emergent abilities: Capabilities appear suddenly at scale, unpredictably.",
        "Multimodal fusion: CLIP aligns vision and language in shared embedding space.",
    ],
    "ai_instructions": [
        "IMPORTANT: Always verify code compiles before suggesting changes.",
        "When refactoring: Preserve existing behavior; write tests first.",
        "Code review focus: Check for off-by-one errors in loop bounds.",
        "Documentation rule: Every public function needs docstring with examples.",
        "Security check: Never log credentials or API keys, even masked.",
        "Performance note: Profile before optimizing; premature optimization is evil.",
        "Error handling: Use specific exceptions, avoid bare except clauses.",
        "API design: Prefer explicit parameters over **kwargs for clarity.",
        "Testing mandate: Unit tests required for all new business logic.",
        "Git hygiene: Atomic commits with descriptive messages in present tense.",
    ],
}

# Query templates with known relevant memories (indexed by template index)
QUERY_TEMPLATES = [
    {
        "query": "How do I preserve function metadata when wrapping in Python?",
        "quadrant": "coding",
        "relevant_indices": [0],  # Index into coding templates
    },
    {
        "query": "What's the best practice for async Python code?",
        "quadrant": "coding",
        "relevant_indices": [1],
    },
    {
        "query": "Docker image optimization techniques",
        "quadrant": "coding",
        "relevant_indices": [3],
    },
    {
        "query": "When is your birthday and what kind of celebration do you prefer?",
        "quadrant": "personal",
        "relevant_indices": [0],
    },
    {
        "query": "What time of day are you most productive?",
        "quadrant": "personal",
        "relevant_indices": [2],
    },
    {
        "query": "What kind of coffee do you drink?",
        "quadrant": "personal",
        "relevant_indices": [9],
    },
    {
        "query": "How does self-attention work in transformers?",
        "quadrant": "research",
        "relevant_indices": [0],
    },
    {
        "query": "What are scaling laws in language models?",
        "quadrant": "research",
        "relevant_indices": [1],
    },
    {
        "query": "How does RAG help with hallucination?",
        "quadrant": "research",
        "relevant_indices": [2],
    },
    {
        "query": "What should I check during code review?",
        "quadrant": "ai_instructions",
        "relevant_indices": [2, 4],  # Multiple relevant
    },
    {
        "query": "Documentation requirements for functions",
        "quadrant": "ai_instructions",
        "relevant_indices": [3],
    },
    {
        "query": "Security practices for logging",
        "quadrant": "ai_instructions",
        "relevant_indices": [4],
    },
]


def generate_embedding(text: str, dim: int = 384) -> List[float]:
    """Generate a deterministic pseudo-embedding for testing."""
    # Use hash to create deterministic but varied vectors
    random.seed(text)
    vec = [random.uniform(-1, 1) for _ in range(dim)]
    # Normalize to unit length for cosine similarity
    norm = sum(x * x for x in vec) ** 0.5
    return [x / norm for x in vec]


def generate_corpus(total_memories: int = 500) -> List[Dict[str, Any]]:
    """Generate synthetic memory corpus with ground truth labels."""
    logger.info(f"Generating corpus of {total_memories} memories...")
    
    memories = []
    templates_per_quadrant = total_memories // 4
    
    for quadrant, templates in MEMORY_TEMPLATES.items():
        for i in range(templates_per_quadrant):
            template = templates[i % len(templates)]
            # Add variation to avoid exact duplicates
            variation = f" [{i//len(templates)}]" if i >= len(templates) else ""
            content = template + variation
            
            memory = {
                "id": str(uuid4()),
                "content": content,
                "summary": content[:50] + "..." if len(content) > 50 else content,
                "quadrants": [quadrant],
                "type": "raw",
                "importance": random.uniform(0.5, 0.9),
                "last_accessed": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
                "vector": generate_embedding(content),
            }
            memories.append(memory)
    
    # Shuffle to mix quadrants
    random.shuffle(memories)
    return memories


def create_test_collection(client: QdrantClient, collection_name: str, dim: int = 384):
    """Create a test collection, deleting existing if present."""
    logger.info(f"Creating test collection: {collection_name}")
    
    collections = client.get_collections().collections
    exists = any(c.name == collection_name for c in collections)
    
    if exists:
        logger.info(f"Deleting existing collection: {collection_name}")
        client.delete_collection(collection_name)
    
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    logger.info(f"Created collection with dimension {dim}")


def insert_memories(client: QdrantClient, collection_name: str, memories: List[Dict]):
    """Insert memories into Qdrant collection."""
    logger.info(f"Inserting {len(memories)} memories into {collection_name}...")
    
    batch_size = 100
    for i in range(0, len(memories), batch_size):
        batch = memories[i:i + batch_size]
        points = [
            PointStruct(
                id=m["id"],
                vector=m["vector"],
                payload={
                    "content": m["content"],
                    "summary": m["summary"],
                    "quadrants": m["quadrants"],
                    "type": m["type"],
                    "importance": m["importance"],
                    "last_accessed": m["last_accessed"],
                }
            )
            for m in batch
        ]
        client.upsert(collection_name=collection_name, points=points)
        logger.info(f"  Inserted batch {i//batch_size + 1}/{(len(memories)-1)//batch_size + 1}")


def calculate_recency_score(last_accessed_str: str, strength: float = 1.0) -> float:
    """Calculate recency score using Ebbinghaus curve."""
    from datetime import datetime
    import math
    
    last_accessed = datetime.fromisoformat(last_accessed_str)
    delta_t = (datetime.now() - last_accessed).total_seconds() / 3600.0
    return math.exp(-delta_t / (strength * 24 * 7))  # Scale strength to weeks


def multi_factor_score(
    relevance: float,
    recency: float,
    importance: float,
    w_rel: float = 0.5,
    w_rec: float = 0.3,
    w_imp: float = 0.2
) -> float:
    """Calculate multi-factor score matching MemCore's algorithm."""
    total = w_rel + w_rec + w_imp
    return (w_rel * relevance + w_rec * recency + w_imp * importance) / total


def raw_vector_search(
    client: QdrantClient,
    collection_name: str,
    query_vector: List[float],
    limit: int = 10,
    quadrant: str = None
) -> List[Dict]:
    """Perform raw vector search."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    search_filter = None
    if quadrant:
        search_filter = Filter(
            must=[FieldCondition(key="quadrants", match=MatchValue(value=quadrant))]
        )
    
    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=limit,
        query_filter=search_filter,
        with_payload=True
    )
    
    return [
        {
            "id": r.id,
            "score": r.score,
            "content": r.payload.get("content", ""),
            "quadrants": r.payload.get("quadrants", []),
            "importance": r.payload.get("importance", 0.5),
            "last_accessed": r.payload.get("last_accessed"),
        }
        for r in results.points
    ]


def memcore_multi_factor_search(
    client: QdrantClient,
    collection_name: str,
    query_vector: List[float],
    limit: int = 10,
    quadrant: str = None,
    w_rel: float = 0.5,
    w_rec: float = 0.3,
    w_imp: float = 0.2
) -> List[Dict]:
    """Perform search with MemCore's multi-factor scoring."""
    # First get more candidates than needed
    candidates = raw_vector_search(client, collection_name, query_vector, limit=limit * 2, quadrant=quadrant)
    
    # Apply multi-factor scoring
    scored = []
    for c in candidates:
        recency = calculate_recency_score(c["last_accessed"])
        final_score = multi_factor_score(
            relevance=c["score"],
            recency=recency,
            importance=c["importance"],
            w_rel=w_rel,
            w_rec=w_rec,
            w_imp=w_imp
        )
        scored.append({**c, "final_score": final_score, "recency": recency})
    
    # Sort by final score and return top k
    scored.sort(key=lambda x: x["final_score"], reverse=True)
    return scored[:limit]


def calculate_precision_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """Calculate precision@k."""
    if k == 0 or not retrieved_ids:
        return 0.0
    
    retrieved_k = retrieved_ids[:k]
    relevant_set = set(relevant_ids)
    
    hits = sum(1 for rid in retrieved_k if rid in relevant_set)
    return hits / min(k, len(retrieved_k))


def run_benchmark(
    client: QdrantClient,
    collection_name: str,
    num_queries: int = 50,
    w_rel: float = 0.5,
    w_rec: float = 0.3,
    w_imp: float = 0.2
) -> Dict[str, Any]:
    """Run the full benchmark."""
    logger.info(f"Running benchmark with {num_queries} queries...")
    logger.info(f"Weights: relevance={w_rel}, recency={w_rec}, importance={w_imp}")
    
    # Sample queries with replacement to get desired number
    test_queries = random.choices(QUERY_TEMPLATES, k=num_queries)
    
    raw_results = {"p@1": [], "p@5": [], "p@10": []}
    memcore_results = {"p@1": [], "p@5": [], "p@10": []}
    
    for i, query_data in enumerate(test_queries):
        query_text = query_data["query"]
        quadrant = query_data["quadrant"]
        
        # Get relevant memory IDs from corpus
        # We need to find which memories match the relevant indices
        relevant_content_patterns = [
            MEMORY_TEMPLATES[quadrant][idx] 
            for idx in query_data["relevant_indices"]
        ]
        
        # Find matching memory IDs by content pattern
        relevant_ids = []
        for pattern in relevant_content_patterns:
            # Search for memories containing this pattern
            all_memories = client.scroll(
                collection_name=collection_name,
                limit=1000,
                with_payload=True
            )[0]
            for m in all_memories:
                if pattern in m.payload.get("content", ""):
                    relevant_ids.append(m.id)
        
        query_vector = generate_embedding(query_text)
        
        # Raw vector search
        raw_results_list = raw_vector_search(
            client, collection_name, query_vector, limit=10, quadrant=quadrant
        )
        raw_ids = [r["id"] for r in raw_results_list]
        
        # MemCore multi-factor search
        memcore_results_list = memcore_multi_factor_search(
            client, collection_name, query_vector, limit=10, quadrant=quadrant,
            w_rel=w_rel, w_rec=w_rec, w_imp=w_imp
        )
        memcore_ids = [r["id"] for r in memcore_results_list]
        
        # Calculate precision@k
        for k in [1, 5, 10]:
            raw_results[f"p@{k}"].append(calculate_precision_at_k(raw_ids, relevant_ids, k))
            memcore_results[f"p@{k}"].append(calculate_precision_at_k(memcore_ids, relevant_ids, k))
        
        if (i + 1) % 10 == 0:
            logger.info(f"  Processed {i + 1}/{num_queries} queries")
    
    # Calculate averages
    def avg(lst): return sum(lst) / len(lst) if lst else 0.0
    
    results = {
        "raw_vector_search": {
            "precision@1": avg(raw_results["p@1"]),
            "precision@5": avg(raw_results["p@5"]),
            "precision@10": avg(raw_results["p@10"]),
            "num_queries": num_queries,
        },
        "memcore_multi_factor": {
            "precision@1": avg(memcore_results["p@1"]),
            "precision@5": avg(memcore_results["p@5"]),
            "precision@10": avg(memcore_results["p@10"]),
            "num_queries": num_queries,
            "weights": {"relevance": w_rel, "recency": w_rec, "importance": w_imp},
        },
        "improvement": {
            "precision@1": ((avg(memcore_results["p@1"]) - avg(raw_results["p@1"])) / avg(raw_results["p@1"]) * 100) if avg(raw_results["p@1"]) > 0 else 0,
            "precision@5": ((avg(memcore_results["p@5"]) - avg(raw_results["p@5"])) / avg(raw_results["p@5"]) * 100) if avg(raw_results["p@5"]) > 0 else 0,
            "precision@10": ((avg(memcore_results["p@10"]) - avg(raw_results["p@10"])) / avg(raw_results["p@10"]) * 100) if avg(raw_results["p@10"]) > 0 else 0,
        }
    }
    
    return results


def generate_markdown_table(results: Dict[str, Any]) -> str:
    """Generate markdown table of results."""
    lines = [
        "# Retrieval Precision Benchmark Results",
        "",
        "## Summary",
        "",
        "| Method | Precision@1 | Precision@5 | Precision@10 |",
        "|--------|-------------|-------------|--------------|",
    ]
    
    raw = results["raw_vector_search"]
    memcore = results["memcore_multi_factor"]
    
    lines.append(
        f"| Raw Vector Search | {raw['precision@1']:.3f} | {raw['precision@5']:.3f} | {raw['precision@10']:.3f} |"
    )
    lines.append(
        f"| MemCore Multi-Factor | {memcore['precision@1']:.3f} | {memcore['precision@5']:.3f} | {memcore['precision@10']:.3f} |"
    )
    
    lines.extend([
        "",
        "## Improvement",
        "",
        "| Metric | Improvement |",
        "|--------|-------------|",
        f"| Precision@1 | +{results['improvement']['precision@1']:.1f}% |",
        f"| Precision@5 | +{results['improvement']['precision@5']:.1f}% |",
        f"| Precision@10 | +{results['improvement']['precision@10']:.1f}% |",
        "",
        "## Configuration",
        "",
        f"- Queries: {results['raw_vector_search']['num_queries']}",
        f"- Weights: relevance={memcore['weights']['relevance']}, recency={memcore['weights']['recency']}, importance={memcore['weights']['importance']}",
        "",
        "Generated: " + datetime.now().isoformat(),
    ])
    
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(
        description="Benchmark retrieval precision comparing raw vector search vs MemCore multi-factor scoring"
    )
    parser.add_argument(
        "--collection",
        default="bench_retrieval_precision",
        help="Qdrant collection name for testing (default: bench_retrieval_precision)"
    )
    parser.add_argument(
        "--memories",
        type=int,
        default=500,
        help="Number of synthetic memories to create (default: 500)"
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=50,
        help="Number of test queries to run (default: 50)"
    )
    parser.add_argument(
        "--qdrant-path",
        default="data/benchmark_qdrant",
        help="Path for test Qdrant storage (default: data/benchmark_qdrant)"
    )
    parser.add_argument(
        "--w-rel",
        type=float,
        default=0.5,
        help="Weight for relevance (default: 0.5)"
    )
    parser.add_argument(
        "--w-rec",
        type=float,
        default=0.3,
        help="Weight for recency (default: 0.3)"
    )
    parser.add_argument(
        "--w-imp",
        type=float,
        default=0.2,
        help="Weight for importance (default: 0.2)"
    )
    parser.add_argument(
        "--output-dir",
        default="benchmarks/results",
        help="Output directory for results (default: benchmarks/results)"
    )
    parser.add_argument(
        "--keep-collection",
        action="store_true",
        help="Keep the test collection after benchmarking (default: delete)"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("MemCore Retrieval Precision Benchmark")
    logger.info("=" * 60)
    logger.info(f"Collection: {args.collection}")
    logger.info(f"Qdrant path: {args.qdrant_path}")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize Qdrant client
    client = QdrantClient(path=args.qdrant_path)
    
    try:
        # Generate and insert corpus
        corpus = generate_corpus(args.memories)
        create_test_collection(client, args.collection)
        insert_memories(client, args.collection, corpus)
        
        # Run benchmark
        start_time = time.time()
        results = run_benchmark(
            client, args.collection, args.queries,
            w_rel=args.w_rel, w_rec=args.w_rec, w_imp=args.w_imp
        )
        duration = time.time() - start_time
        
        results["benchmark_metadata"] = {
            "duration_seconds": duration,
            "memories": args.memories,
            "queries": args.queries,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Save results
        json_path = output_dir / "bench_retrieval_precision.json"
        with open(json_path, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"JSON results saved to: {json_path}")
        
        md_path = output_dir / "bench_retrieval_precision.md"
        with open(md_path, "w") as f:
            f.write(generate_markdown_table(results))
        logger.info(f"Markdown results saved to: {md_path}")
        
        # Print summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("Results Summary")
        logger.info("=" * 60)
        logger.info(f"Raw Vector Search: P@1={results['raw_vector_search']['precision@1']:.3f}, "
                   f"P@5={results['raw_vector_search']['precision@5']:.3f}, "
                   f"P@10={results['raw_vector_search']['precision@10']:.3f}")
        logger.info(f"MemCore Multi-Factor: P@1={results['memcore_multi_factor']['precision@1']:.3f}, "
                   f"P@5={results['memcore_multi_factor']['precision@5']:.3f}, "
                   f"P@10={results['memcore_multi_factor']['precision@10']:.3f}")
        logger.info(f"Improvement: P@1=+{results['improvement']['precision@1']:.1f}%, "
                   f"P@5=+{results['improvement']['precision@5']:.1f}%, "
                   f"P@10=+{results['improvement']['precision@10']:.1f}%")
        logger.info(f"Duration: {duration:.2f}s")
        logger.info("=" * 60)
        
    finally:
        if not args.keep_collection:
            logger.info(f"Cleaning up: deleting collection {args.collection}")
            try:
                client.delete_collection(args.collection)
            except Exception as e:
                logger.warning(f"Failed to delete collection: {e}")


if __name__ == "__main__":
    asyncio.run(main())
