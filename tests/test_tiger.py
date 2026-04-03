"""
老虎证券API连接测试
验证配置是否正确
"""
import asyncio
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.connectors.tiger import TigerConnector
from core.config import settings

async def test_tiger_connection():
    """测试老虎API连接"""
    print("=" * 60)
    print("老虎证券API连接测试")
    print("=" * 60)
    
    # 检查配置
    print(f"\n📋 配置信息:")
    print(f"  Account: {settings.TIGER_ACCOUNT}")
    print(f"  Paper Trading: {settings.TIGER_ENABLE_PAPER}")
    print(f"  Private Key: {'已配置' if settings.TIGER_PRIVATE_KEY else '未配置'}")
    
    # 创建连接器
    print(f"\n🔌 连接测试...")
    connector = TigerConnector()
    
    try:
        await connector.connect()
        print("✅ HTTP客户端连接成功")
        
        # 测试账户查询
        print(f"\n💰 查询账户信息...")
        account = await connector.get_account()
        print(f"✅ 账户查询成功!")
        print(f"  账户: {account.get('account')}")
        print(f"  币种: {account.get('currency')}")
        print(f"  现金: {account.get('cash', 0):,.2f}")
        print(f"  净值: {account.get('net_liquidation', 0):,.2f}")
        print(f"  购买力: {account.get('buying_power', 0):,.2f}")
        
        # 测试行情查询
        print(f"\n📈 查询行情 (AAPL)...")
        quote = await connector.get_quote("AAPL", "US")
        print(f"✅ 行情查询成功!")
        print(f"  代码: {quote.get('symbol')}")
        print(f"  价格: ${quote.get('price', 0):,.2f}")
        print(f"  涨跌: {quote.get('change_percent', 0):+.2f}%")
        
        # 测试持仓查询
        print(f"\n📊 查询持仓...")
        positions = await connector.get_positions()
        print(f"✅ 持仓查询成功!")
        print(f"  持仓数量: {len(positions)}")
        for pos in positions[:5]:  # 只显示前5个
            print(f"    - {pos.get('symbol')}: {pos.get('quantity')}股 "
                  f"(${pos.get('current_price', 0):.2f})")
        
        print(f"\n" + "=" * 60)
        print("✅ 所有测试通过! 老虎API配置正确")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 连接测试失败: {e}")
        print(f"\n可能的解决方案:")
        print("  1. 检查 Account ID 是否正确")
        print("  2. 检查 Private Key 格式 (应该是pk1格式)")
        print("  3. 检查是否已开通API权限")
        print("  4. 检查网络连接")
        return False
    
    finally:
        await connector.disconnect()
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_tiger_connection())
    sys.exit(0 if success else 1)
