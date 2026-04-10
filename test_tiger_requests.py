import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.connectors.tiger_requests import TigerConnector
from core.config import settings

def test():
    print(f"Settings HTTP_PROXY: {settings.HTTP_PROXY}")
    
    tiger = TigerConnector()
    print(f"Tiger proxy: {tiger.proxy}")
    
    tiger.connect()
    
    try:
        print("\n测试美股行情 (NVDA)...")
        quote = tiger.get_quote("NVDA", "US")
        print(f"✅ Quote: {quote}")
    except Exception as e:
        import traceback
        print(f"❌ Error: {type(e).__name__}: {e}")
        traceback.print_exc()
    
    tiger.disconnect()

if __name__ == "__main__":
    test()
