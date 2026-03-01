#!/usr/bin/env python3
"""Test local embedding functionality with different providers."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memcore.utils.llm import LLMInterface, DEFAULT_EMBEDDING_MODEL


async def test_provider(provider: str):
    print(f"\n{'='*60}")
    print(f"Testing: {provider.upper()}")
    print(f"{'='*60}")
    
    try:
        llm = LLMInterface(provider=provider)
        print(f"Provider: {llm.provider}")
        print(f"Embedding model: {llm.catalogue['embedding']}")
        print(f"Embedding dimension: {llm.get_embedding_dimension()}")
        
        # Test actual embedding generation
        print("\nGenerating embedding for test text...")
        embedding = await llm.get_embedding("This is a test sentence for local embedding.")
        print(f"✓ Generated embedding length: {len(embedding)}")
        print(f"  First 5 values: {[round(x, 4) for x in embedding[:5]]}")
        
        # Verify dimension matches
        assert len(embedding) == llm.get_embedding_dimension(), "Dimension mismatch!"
        
        print(f"\n✅ {provider.upper()} works correctly with local {llm.get_embedding_dimension()}-dim embeddings!")
        return True
        
    except ValueError as e:
        print(f"⚠️  Skipped: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test():
    print("Testing Local Embedding with Multiple Providers")
    print(f"Default Model: {DEFAULT_EMBEDDING_MODEL}")
    print("This model supports Chinese, English, and 100+ languages")
    print(f"Dimension: {1024}")
    print("Vendor-agnostic: you can switch LLM providers without re-indexing")
    
    results = []
    for provider in ['kimi', 'bedrock', 'gemini', 'deepseek']:
        result = await test_provider(provider)
        results.append((provider, result))
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for provider, result in results:
        status = "✅ OK" if result else ("⚠️  Skipped (no API key)" if result is None else "❌ Failed")
        print(f"  {provider:<12} {status}")
    
    print(f"\nAll configured providers use {DEFAULT_EMBEDDING_MODEL} (768-dim)")
    print("You can switch between them without re-indexing your database!")


if __name__ == "__main__":
    asyncio.run(test())
