#!/usr/bin/env python3
"""Check available embedding models and their dimensions."""
from fastembed import TextEmbedding

print("Available fastembed models:\n")
print(f"{'Model':<50} {'Dim':<6} {'Size':<8} {'Description'}")
print("-" * 100)

for model in TextEmbedding.list_supported_models():
    model_name = model["model"]
    dim = model.get("dim", "?")
    size = model.get("size_in_GB", "?")
    desc = model.get("description", "")[:30]
    print(f"{model_name:<50} {dim:<6} {size:<8} {desc}")
