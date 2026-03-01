import litellm
import os
from typing import List, Dict, Any, Optional
from fastembed import TextEmbedding

# Provider API key environment variable mapping
PROVIDER_API_KEYS = {
    "bedrock": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
    "gemini": ["GEMINI_API_KEY"],
    "kimi": ["MOONSHOT_API_KEY"],
    "deepseek": ["DEEPSEEK_API_KEY"],
}

# Default embedding model for all providers
# IMPORTANT: Changing this after data is stored requires re-indexing!
# DEFAULT: intfloat/multilingual-e5-large - Multilingual, supports 100+ languages including Chinese
# Alternative: BAAI/bge-base-en-v1.5 (768-dim, 210MB) - English-only, smaller
DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-large"  # 1024-dim, 2.24GB, multilingual

MODEL_CATALOGUE = {
    "bedrock": {
        "fast": "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0",
        "strong": "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "embedding": f"local/{DEFAULT_EMBEDDING_MODEL}"  # Vendor-agnostic local embedding
    },
    "gemini": {
        "fast": "gemini/gemini-2.0-flash",
        "strong": "gemini/gemini-2.0-pro-exp-02-05",
        "embedding": f"local/{DEFAULT_EMBEDDING_MODEL}"  # Vendor-agnostic local embedding
    },
    "kimi": {
        "fast": "moonshot/moonshot-v1-8k",
        "strong": "moonshot/moonshot-v2-5-32k",
        "embedding": f"local/{DEFAULT_EMBEDDING_MODEL}"  # Vendor-agnostic local embedding
    },
    "deepseek": {
        "fast": "deepseek/deepseek-chat",
        "strong": "deepseek/deepseek-reasoner",
        "embedding": f"local/{DEFAULT_EMBEDDING_MODEL}"  # Vendor-agnostic local embedding
    },
    "local": {
        "embedding": DEFAULT_EMBEDDING_MODEL
    }
}

class LLMInterface:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or os.getenv("LLM_PROVIDER", "bedrock")
        self.catalogue = MODEL_CATALOGUE.get(self.provider, MODEL_CATALOGUE["bedrock"])
        self._local_embedder = None
        self._validate_api_key()

    def _validate_api_key(self):
        """Validates that required API keys are set for the selected provider."""
        required_keys = PROVIDER_API_KEYS.get(self.provider, [])
        missing_keys = [key for key in required_keys if not os.getenv(key)]
        if missing_keys:
            raise ValueError(
                f"Provider '{self.provider}' requires the following environment variables: {', '.join(missing_keys)}. "
                f"Please set them in your .env file."
            )

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
        embedding_model = os.getenv("EMBEDDING_MODEL", self.catalogue.get("embedding", f"local/{DEFAULT_EMBEDDING_MODEL}"))
        
        if embedding_model.startswith("local/"):
            if self._local_embedder is None:
                model_name = embedding_model.replace("local/", "")
                # Initialize fastembed with the specified model
                try:
                    self._local_embedder = TextEmbedding(model_name=model_name)
                except Exception:
                    # Fallback to default if model name not recognized
                    self._local_embedder = TextEmbedding()
            
            # fastembed's embed() returns a generator of numpy arrays
            embeddings = list(self._local_embedder.embed([text]))
            return embeddings[0].tolist()
        
        # Fallback to cloud embedding via litellm (for vendors that require cloud embeddings)
        response = await litellm.aembedding(
            model=embedding_model,
            input=[text]
        )
        return response.data[0].embedding

    def get_embedding_dimension(self) -> int:
        """Returns the expected dimension of the current embedding model."""
        embedding_model = os.getenv("EMBEDDING_MODEL", self.catalogue.get("embedding", f"local/{DEFAULT_EMBEDDING_MODEL}"))
        
        if embedding_model.startswith("local/"):
            model_name = embedding_model.replace("local/", "")
            # Common local model dimensions
            if "bge-small" in model_name.lower():
                return 384  # BGE-small: 384-dim (lightweight, lower quality)
            if "bge-base" in model_name.lower():
                return 768  # BGE-base: 768-dim (recommended balance)
            if "bge-large" in model_name.lower():
                return 1024  # BGE-large: 1024-dim (highest quality, slower)
            if "bge-m3" in model_name.lower():
                return 1024  # BGE-M3: 1024-dim (multilingual, state-of-the-art)
            if "gte-large" in model_name.lower() or "mxbai-embed-large" in model_name.lower():
                return 1024  # Other 1024-dim models
            if "snowflake-arctic-embed-m" in model_name.lower():
                return 768  # Snowflake M series: 768-dim
            if "snowflake-arctic-embed-l" in model_name.lower():
                return 1024  # Snowflake L series: 1024-dim
            if "multilingual-e5-large" in model_name.lower():
                return 1024  # E5-large: 1024-dim
            if "minilm" in model_name.lower() or "all-minilm" in model_name.lower():
                return 384  # MiniLM: 384-dim
            if "jina-embeddings-v2" in model_name.lower() and "small" not in model_name.lower():
                return 768  # Jina base models: 768-dim
            if "nomic-embed" in model_name.lower():
                return 768  # Nomic: 768-dim
            return 768  # Default: assume 768-dim for unknown local models
        
        # Standard cloud dimensions (if user explicitly overrides to use cloud)
        if "titan-embed-text-v2" in embedding_model: return 1024
        if "text-embedding-3-small" in embedding_model: return 1536
        if "text-embedding-3-large" in embedding_model: return 3072
        if "text-embedding-004" in embedding_model: return 768
        if "moonshot-embed" in embedding_model: return 1536
        return 1536 # Default fallback
