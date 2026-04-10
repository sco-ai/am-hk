import asyncio
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.connectors.tiger_aiohttp import TigerConnector
from core.config import settings

async def test():
    tiger = TigerConnector()
    await tiger.connect()
    
    try:
        print("测试美股行情 (NVDA)...")
        quote = await tiger.get_quote("NVDA", "US")
        print(f"✅ Quote: {quote}")
    except Exception as e:
        import traceback
        print(f"❌ Error: {type(e).__name__}: {e}")
        traceback.print_exc()
    
    await tiger.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
