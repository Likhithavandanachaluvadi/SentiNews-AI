from sentence_transformers import SentenceTransformer
import os

# We'll use the bge-small-en-v1.5 model as it provides an excellent balance of speed and performance for financial data.
MODEL_NAME = "BAAI/bge-small-en-v1.5"

class EmbeddingService:
    def __init__(self):
        # Setting trust_remote_code=True is sometimes needed for BGE models, though v1.5 usually doesn't strictly need it.
        self.model = SentenceTransformer(MODEL_NAME)
        
    def get_embedding(self, text: str) -> list[float]:
        """Generate an embedding for a single string."""
        return self.model.encode(text, normalize_embeddings=True).tolist()
        
    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of strings."""
        return self.model.encode(texts, normalize_embeddings=True).tolist()

# Singleton instance
embedding_service = EmbeddingService()
