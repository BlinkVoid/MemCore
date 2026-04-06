from typing import List, Optional
from pydantic import BaseModel
from src.memcore.utils.llm import LLMInterface

class ClassificationResult(BaseModel):
    quadrant: str
    confidence: float
    reason: str

class GatekeeperRouter:
    def __init__(self, llm: LLMInterface):
        self.llm = llm
        self.quadrants = ["coding", "personal", "research", "ai_instructions"]

    async def classify_request(self, query: str) -> ClassificationResult:
        prompt = f"""
        Classify the following user query into one of these quadrants: {', '.join(self.quadrants)}.
        
        Query: "{query}"
        
        Return the result as a JSON object with keys: "quadrant", "confidence" (0-1), and "reason".
        """
        
        # In a real implementation, we'd use structured output features of the LLM
        # For now, we'll simulate it or use a simple parsing.
        response = await self.llm.completion(
            messages=[{"role": "system", "content": "You are a routing expert for an AI memory system."},
                      {"role": "user", "content": prompt}],
            response_format={ "type": "json_object" },
            tier="fast"
        )
        
        import json
        data = json.loads(response)
        return ClassificationResult(**data)
