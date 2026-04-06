from fastembed import TextEmbedding
import time

print("Starting FastEmbed test...")
start = time.time()
try:
    model = TextEmbedding(model_name="intfloat/multilingual-e5-large", providers=["CPUExecutionProvider"])
    print(f"Model loaded in {time.time() - start:.2f}s")
    
    print("Generating embedding...")
    embeddings = list(model.embed(["hello world"]))
    print(f"Success! Embedding size: {len(embeddings[0])}")
except Exception as e:
    print(f"FAILED: {e}")
