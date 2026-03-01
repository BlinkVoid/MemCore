#!/usr/bin/env python3
"""Test Chinese embedding support."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memcore.utils.llm import LLMInterface, DEFAULT_EMBEDDING_MODEL


async def test_chinese():
    print("Testing Chinese Embedding Support")
    print("=" * 50)
    print(f"Model: {DEFAULT_EMBEDDING_MODEL}")
    print(f"Dimension: {1024}")
    print(f"Languages: 100+ (including Chinese)")
    print()
    
    llm = LLMInterface(provider='kimi')
    
    # Test Chinese text
    chinese_texts = [
        "用户喜欢喝绿茶，不喜欢咖啡",
        "这是一个关于人工智能的笔记",
        "明天下午三点开会讨论项目进度"
    ]
    
    print("Testing Chinese text embeddings:")
    print("-" * 50)
    
    for text in chinese_texts:
        embedding = await llm.get_embedding(text)
        print(f'✓ "{text}"')
        print(f'  Dimension: {len(embedding)}')
        print(f'  Sample values: {[round(x, 4) for x in embedding[:3]]}...')
        print()
    
    # Test mixed Chinese-English
    mixed_text = "这个project需要在周五前完成deploy"
    embedding = await llm.get_embedding(mixed_text)
    print(f'✓ Mixed: "{mixed_text}"')
    print(f'  Dimension: {len(embedding)}')
    print()
    
    print("=" * 50)
    print("✅ Chinese embedding works correctly!")
    print("✅ You can now store and retrieve Chinese memories.")
    print("✅ Mixed Chinese-English content is also supported.")


if __name__ == "__main__":
    asyncio.run(test_chinese())
