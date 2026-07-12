from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import VectorParams, Distance
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Constants
COLLECTION_NAME = "financial_research"
VECTOR_SIZE = 384  # Size for bge-small-en-v1.5

def get_qdrant_client() -> AsyncQdrantClient:
    """Returns an asynchronous Qdrant client."""
    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None
    )
    return client

async def init_qdrant_collection():
    """Initializes the Qdrant collection if it doesn't exist."""
    client = get_qdrant_client()
    try:
        collections = await client.get_collections()
        collection_names = [col.name for col in collections.collections]
        
        if COLLECTION_NAME not in collection_names:
            logger.info(f"Creating Qdrant collection: {COLLECTION_NAME}")
            await client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
            )
            logger.info("Collection created successfully.")
        else:
            logger.info(f"Qdrant collection {COLLECTION_NAME} already exists.")
    except Exception as e:
        logger.error(f"Error initializing Qdrant collection: {e}")
        # In a real startup, we wouldn't silently fail, but for the MVP, we just log it.
