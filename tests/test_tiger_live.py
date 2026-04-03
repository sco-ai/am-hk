#!/usr/bin/env python3
"""
老虎证券API测试
"""
import sys
import asyncio
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.config import settings

async def test_tiger():
    """测试老虎API"""
    print("="*60)
    print("老虎证券API测试")
    print("="*60)
    
    from core.connectors.tiger import TigerConnector
    
    print(f"\n📋 配置信息:")
    print(f"  Account: {settings.TIGER_ACCOUNT}")
    print(f"  Private Key: {'已配置' if settings.TIGER_PRIVATE_KEY else '未配置'}")
    
    connector = TigerConnector()
    
    print(f"\n🔌 连接测试...")
    await connector.connect()
    print("✅ HTTP客户端连接成功")
    
    # 测试账户查询
    print(f"\n💰 查询账户信息...")
    try:
        account = await connector.get_account()
        print(f"✅ 账户查询成功!")
        print(f"  账户: {account.get('account')}")
        print(f"  币种: {account.get('currency')}")
        print(f"  现金: {account.get('cash', 0):,.2f}")
        print(f"  净值: {account.get('net_liquidation', 0):,.2f}")
        print(f"  购买力: {account.get('buying_power', 0):,.2f}")
    except Exception as e:
        print(f"⚠️ 账户查询失败: {e}")
    
    # 测试行情查询
    print(f"\n📈 查询行情 (AAPL)...")
    try:
        quote = await connector.get_quote("AAPL", "US")
        print(f"✅ 行情查询成功!")
        print(f"  代码: {quote.get('symbol')}")
        print(f"  价格: ${quote.get('price', 0):,.2f}")
        print(f"  涨跌: {quote.get('change_percent', 0):+.2f}%")
    except Exception as e:
        print(f"⚠️ 行情查询失败: {e}")
    
    # 测试持仓查询
    print(f"\n📊 查询持仓...")
    try:
        positions = await connector.get_positions()
        print(f"✅ 持仓查询成功!")
        print(f"  持仓数量: {len(positions)}")
        for pos in positions[:3]:
            print(f"    - {pos.get('symbol')}: {pos.get('quantity')}股")
    except Exception as e:
        print(f"⚠️ 持仓查询失败: {e}")
    
    await connector.disconnect()
    print(f"\n✅ 老虎API测试完成")

if __name__ == "__main__":
    asyncio.run(test_tiger())
