import asyncio
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.connectors.tiger_aiohttp import TigerConnector
from core.config import settings

async def test():
    print(f"Settings HTTP_PROXY: {settings.HTTP_PROXY}")
    
    tiger = TigerConnector()
    print(f"Tiger proxy: {tiger.proxy}")
    
    await tiger.connect()
    
    try:
        print("\n测试美股行情 (NVDA)...")
        quote = await tiger.get_quote("NVDA", "US")
        print(f"✅ Quote: {quote}")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
    
    try:
        print("\n测试港股行情 (00700)...")
        quote = await tiger.get_quote("00700", "HK")
        print(f"✅ Quote: {quote}")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
    
    await tiger.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
