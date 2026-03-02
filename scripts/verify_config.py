#!/usr/bin/env python3
"""
Configuration verification script for MemCore.
Tests LLM provider connectivity and embedding functionality.
"""
import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.memcore.utils.llm import LLMInterface, MODEL_CATALOGUE, PROVIDER_API_KEYS


def check_env_variables():
    """Check if required environment variables are set."""
    print("=" * 50)
    print("MemCore Configuration Check")
    print("=" * 50)
    
    provider = os.getenv("LLM_PROVIDER", "bedrock")
    print(f"\n📋 Selected Provider: {provider}")
    
    # Show embedding strategy
    from src.memcore.utils.llm import MODEL_CATALOGUE, DEFAULT_EMBEDDING_MODEL
    embedding_model = os.getenv("EMBEDDING_MODEL", MODEL_CATALOGUE.get(provider, {}).get("embedding", f"local/{DEFAULT_EMBEDDING_MODEL}"))
    dimension = 1024  # Default (bge-m3)
    if "bge-small" in embedding_model.lower():
        dimension = 384
    elif "bge-base" in embedding_model.lower() or "arctic-embed-m" in embedding_model.lower() or "nomic" in embedding_model.lower():
        dimension = 768
    elif "bge-large" in embedding_model.lower() or "arctic-embed-l" in embedding_model.lower() or "gte-large" in embedding_model.lower():
        dimension = 1024
    elif "bge-m3" in embedding_model.lower() or "multilingual-e5" in embedding_model.lower():
        dimension = 1024
    
    # Detect language support
    is_multilingual = any(x in embedding_model.lower() for x in ["m3", "multilingual", "paraphrase-multilingual"])
    
    print(f"\n🔤 Embedding Configuration:")
    print(f"   Type: {'LOCAL (vendor-agnostic)' if embedding_model.startswith('local/') else 'CLOUD (vendor-specific)'}")
    print(f"   Model: {embedding_model}")
    print(f"   Dimension: {dimension}")
    print(f"   Language Support: {'✓ Multilingual (Chinese, English, 100+ languages)' if is_multilingual else 'English-only'}")
    if is_multilingual:
        print(f"   ✓ Supports Chinese memories and queries")
    else:
        print(f"   ⚠️  For Chinese support, use: local/BAAI/bge-m3")
    print(f"   ⚠️  Note: Changing embedding model later requires re-indexing!")
    
    # Check provider-specific keys
    required_keys = PROVIDER_API_KEYS.get(provider, [])
    print(f"\n🔑 API Key Status:")
    all_present = True
    
    if provider == "ollama":
        print(f"  ✓ OLLAMA: No API key needed (local LLM)")
        print(f"    Make sure Ollama is running: http://localhost:11434")
    else:
        for key in required_keys:
            value = os.getenv(key)
            if value and value != f"your_{key.lower()}_key" and not value.startswith("your_"):
                print(f"  ✓ {key}: Set")
            else:
                print(f"  ✗ {key}: NOT SET")
                all_present = False
    
    # Check optional keys
    print(f"\n📁 Optional Configuration:")
    obsidian_path = os.getenv("OBSIDIAN_VAULT_PATH")
    if obsidian_path and not obsidian_path.startswith("/path/to"):
        print(f"  ✓ OBSIDIAN_VAULT_PATH: {obsidian_path}")
    else:
        print(f"  - OBSIDIAN_VAULT_PATH: Not configured (optional)")
    
    strands_key = os.getenv("STRANDS_API_KEY")
    if strands_key and not strands_key.startswith("your_"):
        print(f"  ✓ STRANDS_API_KEY: Set (platform mode)")
    else:
        print(f"  - STRANDS_API_KEY: Not set (local-only mode)")
    
    return all_present, provider


def show_model_catalogue():
    """Display available models for each provider."""
    print(f"\n📚 Model Catalogue:")
    print("-" * 50)
    for provider, models in MODEL_CATALOGUE.items():
        print(f"\n  {provider.upper()}:")
        for tier, model in models.items():
            print(f"    • {tier}: {model}")


async def test_llm_connection(provider: str):
    """Test LLM connection with a simple completion."""
    print(f"\n🧪 Testing LLM Connection ({provider})...")
    print("-" * 50)
    
    try:
        llm = LLMInterface(provider=provider)
        
        # Test fast model completion
        print("  Testing fast model completion...")
        response = await llm.completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Kimi API connection successful!' if you can read this."}
            ],
            tier="fast",
            max_tokens=20
        )
        print(f"  ✓ Fast model response: {response.strip()}")
        
        # Test embedding
        print("\n  Testing embedding...")
        embedding = await llm.get_embedding("This is a test sentence.")
        dimension = len(embedding)
        print(f"  ✓ Embedding generated: dimension={dimension}")
        
        print(f"\n✅ All tests passed for provider: {provider}")
        return True
        
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Connection Error: {e}")
        return False


def show_kimi_quickstart():
    """Show quickstart guide for Kimi."""
    from src.memcore.utils.llm import DEFAULT_EMBEDDING_MODEL
    print(f"\n🚀 Kimi (Moonshot) Quickstart:")
    print("-" * 50)
    print(f"""
1. Get your API key from: https://platform.moonshot.cn/

2. Update your .env file:
   LLM_PROVIDER=kimi
   MOONSHOT_API_KEY=your_actual_api_key_here

3. Default Configuration (Chinese & Multilingual Support):
   EMBEDDING_MODEL=local/{DEFAULT_EMBEDDING_MODEL}
   - 1024-dim, supports Chinese, English, and 100+ languages
   - Vendor-agnostic: switch LLM providers without re-indexing
   - Requires ~4GB RAM
   
   Optional - Override chat models:
   LLM_MODEL_FAST=moonshot/moonshot-v1-8k
   LLM_MODEL_STRONG=moonshot/moonshot-v2-5-32k

4. Run the gatekeeper:
   uv run src/memcore/main.py

💡 Tip: With Kimi + multilingual-e5-large, you can store and retrieve 
   memories in both Chinese and English seamlessly!
""")


async def main():
    keys_ok, provider = check_env_variables()
    show_model_catalogue()
    
    if not keys_ok:
        print(f"\n⚠️  Missing required API keys for provider: {provider}")
        if provider == "kimi":
            show_kimi_quickstart()
        elif provider == "ollama":
            show_ollama_quickstart()
        sys.exit(1)
    
    # Test connection
    success = await test_llm_connection(provider)
    
    if success and provider == "kimi":
        print(f"\n🎉 Kimi API is properly configured and ready to use!")
    elif not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
