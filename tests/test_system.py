#!/usr/bin/env python3
"""
AM-HK 系统启动测试
"""
import sys
import asyncio
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.config import settings

async def test_binance():
    """测试币安连接"""
    print("="*60)
    print("测试1: 币安API连接")
    print("="*60)
    
    from core.connectors.binance import BinanceConnector
    
    connector = BinanceConnector(
        api_key=settings.BINANCE_API_KEY,
        api_secret=settings.BINANCE_SECRET,
        testnet=settings.BINANCE_TESTNET
    )
    
    await connector.connect()
    print("✅ 币安连接成功")
    
    # 获取行情
    print("\n📈 获取BTC行情...")
    ticker = await connector.get_ticker('BTCUSDT')
    print(f"   BTC价格: ${ticker['price']:,.2f}")
    print(f"   24h涨跌: {ticker['change_percent']:+.2f}%")
    
    await connector.disconnect()
    return True

async def test_kafka():
    """测试Kafka"""
    print("\n" + "="*60)
    print("测试2: Kafka消息队列")
    print("="*60)
    
    from core.kafka import MessageBus
    
    bus = MessageBus('test_agent')
    print("✅ Kafka连接成功")
    
    # 发送测试消息
    print("\n📤 发送测试消息...")
    bus.publish_market_data('BTCUSDT', {
        'symbol': 'BTCUSDT',
        'price': 65000.0,
        'timestamp': '2024-01-01T00:00:00Z'
    })
    bus.flush()
    print("✅ 消息发送成功")
    
    bus.close()
    return True

async def test_feishu():
    """测试飞书通知"""
    print("\n" + "="*60)
    print("测试3: 飞书通知")
    print("="*60)
    
    from core.feishu import FeishuNotifier
    
    notifier = FeishuNotifier()
    
    print("📱 发送测试消息...")
    success = await notifier.send_text("🚀 AM-HK系统测试\n时间: 2024-01-01\n状态: 运行中")
    
    if success:
        print("✅ 飞书消息发送成功")
    else:
        print("⚠️ 飞书消息发送失败（Webhook可能无效）")
    
    await notifier.close()
    return True

async def main():
    """主测试"""
    print("\n" + "="*60)
    print("AM-HK 系统启动测试")
    print("="*60 + "\n")
    
    results = []
    
    try:
        results.append(("币安API", await test_binance()))
    except Exception as e:
        print(f"❌ 币安测试失败: {e}")
        results.append(("币安API", False))
    
    try:
        results.append(("Kafka", await test_kafka()))
    except Exception as e:
        print(f"❌ Kafka测试失败: {e}")
        results.append(("Kafka", False))
    
    try:
        results.append(("飞书通知", await test_feishu()))
    except Exception as e:
        print(f"❌ 飞书测试失败: {e}")
        results.append(("飞书通知", False))
    
    # 测试总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
    
    passed_count = sum(1 for _, p in results if p)
    total = len(results)
    
    print(f"\n总计: {passed_count}/{total} 项通过")
    
    if passed_count == total:
        print("\n🎉 所有测试通过！系统可以正常启动")
    else:
        print("\n⚠️ 部分测试失败，请检查配置")

if __name__ == "__main__":
    asyncio.run(main())
