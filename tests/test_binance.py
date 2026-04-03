"""
币安API连接测试
验证配置是否正确
"""
import asyncio
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.connectors.binance import BinanceConnector
from core.config import settings

async def test_binance_connection():
    """测试币安API连接"""
    print("=" * 60)
    print("币安API连接测试")
    print("=" * 60)
    
    # 检查配置
    print(f"\n📋 配置信息:")
    print(f"  API Key: {'已配置' if settings.BINANCE_API_KEY else '未配置'}")
    print(f"  Secret: {'已配置' if settings.BINANCE_SECRET else '未配置'}")
    print(f"  Testnet: {settings.BINANCE_TESTNET}")
    
    # 创建连接器
    print(f"\n🔌 连接测试...")
    connector = BinanceConnector(
        api_key=settings.BINANCE_API_KEY,
        api_secret=settings.BINANCE_SECRET,
        testnet=settings.BINANCE_TESTNET,
    )
    
    try:
        await connector.connect()
        print("✅ HTTP客户端连接成功")
        
        # 健康检查
        print(f"\n🏥 健康检查...")
        is_healthy = await connector.health_check()
        if is_healthy:
            print("✅ 币安API连接正常")
        else:
            print("⚠️ 健康检查失败")
        
        # 测试行情查询
        print(f"\n📈 查询行情 (BTCUSDT)...")
        ticker = await connector.get_ticker("BTCUSDT")
        print(f"✅ 行情查询成功!")
        print(f"  代码: {ticker.get('symbol')}")
        print(f"  价格: ${ticker.get('price', 0):,.2f}")
        print(f"  24h涨跌: {ticker.get('change_percent', 0):+.2f}%")
        print(f"  24h成交量: {ticker.get('volume', 0):,.2f}")
        
        # 测试K线数据
        print(f"\n📊 查询K线数据...")
        klines = await connector.get_klines("BTCUSDT", "1h", limit=5)
        print(f"✅ K线查询成功!")
        print(f"  获取条数: {len(klines)}")
        if klines:
            latest = klines[-1]
            print(f"  最新K线:")
            print(f"    开盘: ${latest['open']:,.2f}")
            print(f"    收盘: ${latest['close']:,.2f}")
            print(f"    最高: ${latest['high']:,.2f}")
            print(f"    最低: ${latest['low']:,.2f}")
        
        # 测试订单簿
        print(f"\n📗 查询订单簿...")
        orderbook = await connector.get_orderbook("BTCUSDT", limit=5)
        print(f"✅ 订单簿查询成功!")
        print(f"  Buy (Top 3): {[f"${p:.2f}" for p, _ in orderbook['bids'][:3]]}")
        print(f"  Sell (Top 3): {[f"${p:.2f}" for p, _ in orderbook['asks'][:3]]}")
        
        # 测试账户信息（仅当非testnet时）
        if not settings.BINANCE_TESTNET:
            print(f"\n💰 查询账户信息...")
            account = await connector.get_account()
            print(f"✅ 账户查询成功!")
            balances = account.get('balances', [])
            print(f"  资产数量: {len(balances)}")
            for bal in balances[:5]:
                print(f"    - {bal['asset']}: {bal['free']:.4f} (可用)")
        
        print(f"\n" + "=" * 60)
        print("✅ 所有测试通过! 币安API配置正确")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 连接测试失败: {e}")
        print(f"\n可能的解决方案:")
        print("  1. 检查 API Key 和 Secret 是否正确")
        print("  2. 检查是否已开启IP白名单")
        print("  3. 检查网络连接")
        return False
    
    finally:
        await connector.disconnect()
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_binance_connection())
    sys.exit(0 if success else 1)