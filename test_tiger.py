"""
测试 Tiger API 连接
"""
import asyncio
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.connectors.tiger import TigerConnector
from core.config import settings

async def test_tiger():
    print(f"Settings HTTP_PROXY: {settings.HTTP_PROXY}")
    print(f"Settings TIGER_ACCOUNT: {settings.TIGER_ACCOUNT[:10]}..." if settings.TIGER_ACCOUNT else "No account")
    
    tiger = TigerConnector()
    print(f"Tiger proxy: {tiger.proxy}")
    
    await tiger.connect()
    
    try:
        print("\n测试美股行情 (NVDA)...")
        quote = await tiger.get_quote("NVDA", "US")
        print(f"Quote: {quote}")
    except Exception as e:
        print(f"Error type: {type(e).__name__}")
        print(f"Error repr: {repr(e)}")
        import traceback
        traceback.print_exc()
    
    try:
        print("\n测试港股行情 (00700)...")
        quote = await tiger.get_quote("00700", "HK")
        print(f"Quote: {quote}")
    except Exception as e:
        print(f"Error type: {type(e).__name__}")
        print(f"Error repr: {repr(e)}")
        import traceback
        traceback.print_exc()
    
    await tiger.disconnect()

if __name__ == "__main__":
    asyncio.run(test_tiger())
