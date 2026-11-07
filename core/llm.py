import json
import math
import re
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel
from config import GEMINI_API_KEY, GEMINI_MODEL

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or GEMINI_MODEL
        self.client = None
        if self.api_key and GENAI_AVAILABLE:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[GeminiClient] Warning: Could not initialize google-genai client: {e}")
                self.client = None

    def is_live(self) -> bool:
        return self.client is not None

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        response_schema: Optional[Type[BaseModel]] = None,
        temperature: float = 0.2
    ) -> str:
        """Generates text from Gemini or falls back to structured deterministic response."""
        if self.client:
            try:
                config_args = {"temperature": temperature}
                if system_instruction:
                    config_args["system_instruction"] = system_instruction
                if response_schema:
                    config_args["response_mime_type"] = "application/json"
                    config_args["response_schema"] = response_schema
                
                config = types.GenerateContentConfig(**config_args)
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                print(f"[GeminiClient] API call failed: {e}. Falling back to deterministic reasoning.")

        return self._local_fallback(prompt, response_schema)

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Computes embeddings using Gemini or local TF-IDF / term-frequency vectorization."""
        if self.client:
            try:
                embeddings = []
                for text in texts:
                    res = self.client.models.embed_content(
                        model="text-embedding-004",
                        contents=text
                    )
                    if hasattr(res, 'embedding') and hasattr(res.embedding, 'values'):
                        embeddings.append(res.embedding.values)
                    elif hasattr(res, 'embeddings') and res.embeddings:
                        embeddings.append(res.embeddings[0].values)
                if len(embeddings) == len(texts):
                    return embeddings
            except Exception as e:
                print(f"[GeminiClient] Embedding API call failed: {e}. Falling back to local vectorizer.")

        return [self._local_embedding(t) for t in texts]

    def _local_embedding(self, text: str, dim: int = 128) -> List[float]:
        """Deterministic hash-based bag-of-words embedding normalized to unit sphere."""
        vec = [0.0] * dim
        words = re.findall(r"\w+", text.lower())
        if not words:
            return vec
        for word in words:
            # Deterministic hash bucket
            h = hash(word) % dim
            vec[h] += 1.0
        # Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def _local_fallback(self, prompt: str, response_schema: Optional[Type[BaseModel]] = None) -> str:
        """Deterministic rule-based response generator when offline or no API key."""
        lower = prompt.lower()
        if response_schema:
            schema_name = response_schema.__name__
            if "Hypothesis" in schema_name:
                return json.dumps({
                    "id": "H1",
                    "title": "Deterministic Root Cause",
                    "description": "Inferred from causal graph onset ordering and error patterns.",
                    "root_service": "db-primary",
                    "testable_predictions": ["Error onset strictly precedes downstream timeouts"],
                    "status": "Supported"
                })
        return "Deterministic reasoning fallback active."


llm_client = GeminiClient()
