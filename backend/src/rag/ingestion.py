"""
Production-grade RAG ingestion pipeline:
- Text chunking with token counting
- Embedding generation with batching
- Qdrant vector store upsertion
- Metadata indexing for filtering
- Deduplication & update tracking
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime
import asyncio
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from src.core.config import settings
import hashlib
import json

logger = logging.getLogger(__name__)

# ============================================================================
# PRODUCTION INGESTION SERVICE
# ============================================================================

class RAGIngestionService:
    """
    Handles ingestion of financial documents into Qdrant vector store.
    Supports:
    - Automatic text chunking with token awareness
    - Batch embedding generation
    - Deduplication via content hashing
    - Metadata-aware ingestion
    """
    
    # Configuration
    CHUNK_SIZE_WORDS = 200  # ~512 tokens per chunk
    CHUNK_OVERLAP_WORDS = 50
    BATCH_SIZE = 32  # Embedding batch size
    EMBEDDING_DIM = 384  # sentence-transformers/all-MiniLM-L6-v2
    COLLECTION_NAME = "financial_documents"
    
    def __init__(self):
        """Initialize Qdrant client and embedding model."""
        try:
            self.qdrant_client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
            )
            logger.info(f"Connected to Qdrant at {settings.QDRANT_URL}")
            
            # Initialize embedding model (all-MiniLM-L6-v2 is good balance of speed/quality)
            self.embedding_model = SentenceTransformer(
                "sentence-transformers/all-MiniLM-L6-v2",
                cache_folder="./models"
            )
            logger.info("Embedding model loaded")
            
            # Ensure collection exists
            self._ensure_collection()
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            raise
    
    def _ensure_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        try:
            collections = self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.COLLECTION_NAME not in collection_names:
                self.qdrant_client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.EMBEDDING_DIM,
                        distance=Distance.COSINE,
                    ),
                    # Enable payload indexing for fast filtering
                    hnsw_config={
                        "m": 16,
                        "ef_construct": 100,
                    },
                )
                logger.info(f"Created Qdrant collection: {self.COLLECTION_NAME}")
            else:
                logger.info(f"Collection {self.COLLECTION_NAME} already exists")
                
        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}")
            raise
    
    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.
        Uses word-based splitting for readability.
        """
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), self.CHUNK_SIZE_WORDS - self.CHUNK_OVERLAP_WORDS):
            chunk = " ".join(words[i:i + self.CHUNK_SIZE_WORDS])
            if chunk.strip():
                chunks.append(chunk)
        
        return chunks
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate SHA256 hash of content for deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def ingest_article(
        self,
        title: str,
        content: str,
        source: str,
        ticker: str,
        url: str,
        published_at: str,
        sentiment_score: Optional[int] = None,
    ) -> Dict:
        """
        Ingest a single news article into Qdrant.
        
        Args:
            title: Article title
            content: Article text/body
            source: News source name
            ticker: Stock ticker symbol
            url: Source URL
            published_at: Publication date (ISO format)
            sentiment_score: Optional sentiment (-100 to +100)
        
        Returns:
            Ingestion result dict with statistics
        """
        try:
            # Chunk the content
            chunks = self._chunk_text(f"{title}\n\n{content}")
            logger.info(f"Split article into {len(chunks)} chunks")
            
            # Generate embeddings in batches
            embeddings = []
            for i in range(0, len(chunks), self.BATCH_SIZE):
                batch = chunks[i:i + self.BATCH_SIZE]
                batch_embeddings = self.embedding_model.encode(
                    batch,
                    show_progress_bar=False,
                    normalize_embeddings=True,
                )
                embeddings.extend(batch_embeddings.tolist())
            
            logger.info(f"Generated {len(embeddings)} embeddings")
            
            # Create points for Qdrant
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                point_id = int(self._generate_content_hash(chunk)[:15], 16)  # Use hash as ID
                
                point = PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "title": title,
                        "content": chunk,
                        "source": source,
                        "ticker": ticker.upper(),
                        "url": url,
                        "published_at": published_at,
                        "ingested_at": datetime.utcnow().isoformat(),
                        "sentiment_score": sentiment_score or 0,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    }
                )
                points.append(point)
            
            # Upsert to Qdrant (idempotent - overwrites duplicates)
            self.qdrant_client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=points,
            )
            
            logger.info(f"Successfully ingested {len(points)} document chunks from {source}")
            
            return {
                "status": "success",
                "chunks_created": len(points),
                "source": source,
                "ticker": ticker,
            }
            
        except Exception as e:
            logger.error(f"Ingestion failed for {title}: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "source": source,
                "ticker": ticker,
            }
    
    async def ingest_batch(self, articles: List[Dict]) -> Dict:
        """
        Ingest multiple articles concurrently.
        
        Args:
            articles: List of article dicts (see ingest_article params)
        
        Returns:
            Summary of ingestion results
        """
        tasks = [
            self.ingest_article(
                title=article["title"],
                content=article["content"],
                source=article["source"],
                ticker=article["ticker"],
                url=article["url"],
                published_at=article["published_at"],
                sentiment_score=article.get("sentiment_score"),
            )
            for article in articles
        ]
        
        results = await asyncio.gather(*tasks)
        
        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "failed")
        total_chunks = sum(r.get("chunks_created", 0) for r in results)
        
        logger.info(f"Batch ingestion complete: {successful} succeeded, {failed} failed, {total_chunks} total chunks")
        
        return {
            "total_articles": len(articles),
            "successful": successful,
            "failed": failed,
            "total_chunks_created": total_chunks,
            "details": results,
        }
    
    async def search(
        self,
        query: str,
        ticker: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict]:
        """
        Semantic search over ingested documents.
        
        Args:
            query: Search query
            ticker: Optional ticker filter
            limit: Max results to return
        
        Returns:
            List of relevant document chunks with scores
        """
        try:
            # Embed query
            query_embedding = self.embedding_model.encode(
                query,
                normalize_embeddings=True,
            ).tolist()
            
            # Build filter if ticker specified
            filter_condition = None
            if ticker:
                from qdrant_client.models import HasValueCondition, FieldCondition, MatchValue
                filter_condition = FieldCondition(
                    key="ticker",
                    match=MatchValue(value=ticker.upper()),
                )
            
            # Search Qdrant
            results = self.qdrant_client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_embedding,
                query_filter=filter_condition,
                limit=limit,
                with_payload=True,
                with_vectors=False,  # Don't need vector data in response
            )
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "content": result.payload.get("content", ""),
                    "title": result.payload.get("title", ""),
                    "source": result.payload.get("source", ""),
                    "url": result.payload.get("url", ""),
                    "published_at": result.payload.get("published_at", ""),
                    "score": result.score,
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

# Singleton instance
rag_service = RAGIngestionService()
