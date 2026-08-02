import asyncio
import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database.session import init_db
from src.services.screener_service import ScreenerService
from src.services.entity_resolver import EntityResolver

async def main():
    print("Initializing Database...")
    await init_db()
    print("Initializing EntityResolver...")
    await EntityResolver.initialize_async()
    
    print("Testing get_dynamic_peers_from_db...")
    try:
        peers = await ScreenerService.get_dynamic_peers_from_db("Banks-Regional", "HDFCBANK")
        print("Success! Peers found:", peers)
    except Exception as e:
        print("Failed with error:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
