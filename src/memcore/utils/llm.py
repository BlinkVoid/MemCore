import litellm
import os
from typing import List, Dict, Any, Optional
from fastembed import TextEmbedding

MODEL_CATALOGUE = {
    "bedrock": {
        "fast": "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0",
        "strong": "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "embedding": "bedrock/amazon.titan-embed-text-v2:0"
    },
    "gemini": {
        "fast": "gemini/gemini-2.0-flash",
        "strong": "gemini/gemini-2.0-pro-exp-02-05",
        "embedding": "gemini/text-embedding-004"
    },
    "kimi": {
        "fast": "moonshot/moonshot-v1-8k",
        "strong": "moonshot/moonshot-v2-5-32k",
        "embedding": "moonshot/moonshot-embed-v1"
    },
    "deepseek": {
        "fast": "deepseek/deepseek-chat",
        "strong": "deepseek/deepseek-reasoner",
        "embedding": "local/bge-small"
    },
    "local": {
        "embedding": "BAAI/bge-small-en-v1.5"
    }
}

class LLMInterface:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or os.getenv("LLM_PROVIDER", "bedrock")
        self.catalogue = MODEL_CATALOGUE.get(self.provider, MODEL_CATALOGUE["bedrock"])
        self._local_embedder = None

    def get_model(self, tier: str) -> str:
        """Resolves the model string based on provider and tier."""
        env_override = os.getenv(f"LLM_MODEL_{tier.upper()}")
        if env_override:
            return env_override
        return self.catalogue.get(tier, self.catalogue["fast"])

    async def completion(self, messages: List[Dict[str, str]], tier: str = "fast", **kwargs) -> str:
        model = self.get_model(tier)
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content

    async def get_embedding(self, text: str) -> List[float]:
        embedding_model = os.getenv("EMBEDDING_MODEL", self.catalogue.get("embedding", "local/bge-small"))
        
        if embedding_model.startswith("local/"):
            if self._local_embedder is None:
                model_name = embedding_model.replace("local/", "")
                # Default to bge-small if name not recognized by fastembed defaults
                self._local_embedder = TextEmbedding() 
            
            # fastembed's embed() returns a generator of numpy arrays
            embeddings = list(self._local_embedder.embed([text]))
            return embeddings[0].tolist()
        
        # Fallback to cloud embedding via litellm
        response = await litellm.aembedding(
            model=embedding_model,
            input=[text]
        )
        return response.data[0].embedding

    def get_embedding_dimension(self) -> int:
        """Returns the expected dimension of the current embedding model."""
        embedding_model = os.getenv("EMBEDDING_MODEL", self.catalogue.get("embedding", "local/bge-small"))
        if embedding_model.startswith("local/"):
            return 384 # BGE-small dimension
        
        # Standard cloud dimensions
        if "titan-embed-text-v2" in embedding_model: return 1024 # Adjustable, but default often 1024
        if "text-embedding-3-small" in embedding_model: return 1536
        if "text-embedding-004" in embedding_model: return 768
        return 1536 # Default fallback
