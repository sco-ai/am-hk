#!/usr/bin/env python3
"""
AM-HK 完整系统启动测试（使用模拟数据）
测试内部数据流：Agent1 -> Agent2 -> Agent3 -> Agent4 -> 飞书通知
"""
import sys
import asyncio
import json
from datetime import datetime
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.kafka import MessageBus
from core.feishu import FeishuNotifier
from core.models import MarketData, MarketType, DataType, Signal, ActionType
from core.utils import generate_msg_id, generate_timestamp

# 模拟价格数据
mock_prices = {
    'BTCUSDT': [65000, 65100, 65200, 65150, 65300, 65400, 65500, 65450, 65600, 65700],
    'ETHUSDT': [3200, 3210, 3220, 3215, 3230, 3240, 3250, 3245, 3260, 3270],
}

def format_timestamp(dt):
    """格式化时间戳为字符串"""
    return dt.isoformat() if isinstance(dt, datetime) else str(dt)

async def simulate_agent1():
    """模拟Agent1：发送市场数据"""
    print("="*60)
    print("🚀 Agent1: MarketHarvester (模拟)")
    print("="*60)
    
    bus = MessageBus('agent1_harvester')
    
    for symbol, prices in mock_prices.items():
        for i, price in enumerate(prices[:3]):
            data = {
                'symbol': symbol,
                'market': MarketType.BTC.value,
                'timestamp': format_timestamp(generate_timestamp()),
                'data_type': DataType.TICK.value,
                'payload': {
                    'price': price,
                    'volume': 100.5,
                    'close': price,
                }
            }
            bus.publish_market_data(symbol, data)
            print(f"  📤 {symbol}: ${price:,.2f}")
    
    bus.flush()
    bus.close()
    print("✅ Agent1完成\n")

async def simulate_agent2():
    """模拟Agent2：计算因子"""
    print("="*60)
    print("🔬 Agent2: DataCurator (因子计算)")
    print("="*60)
    
    bus = MessageBus('agent2_curator')
    
    for symbol in mock_prices.keys():
        factors = {
            'mom_5m': 2.5,
            'mom_15m': 3.2,
            'rsi': 65.0,
            'macd': 0.05,
            'volatility_5m': 15.2,
            'volume_ma_ratio': 1.3,
            'ema_diff': 0.8,
            'close': mock_prices[symbol][-1],
        }
        
        factor_data = {
            'symbol': symbol,
            'market': MarketType.BTC.value,
            'timestamp': format_timestamp(generate_timestamp()),
            'factors': factors,
            'raw_data_hash': 'abc123',
        }
        
        bus.publish_factors(symbol, factor_data)
        print(f"  📊 {symbol}: 计算了 {len(factors)} 个因子")
    
    bus.flush()
    bus.close()
    print("✅ Agent2完成\n")

async def simulate_agent3():
    """模拟Agent3：生成信号"""
    print("="*60)
    print("🔍 Agent3: AlphaScanner (信号生成)")
    print("="*60)
    
    bus = MessageBus('agent3_scanner')
    
    signals = [
        {
            'symbol': 'BTCUSDT',
            'market': MarketType.BTC.value,
            'action': ActionType.BUY.value,
            'confidence': 0.75,
            'predicted_return': 3.5,
            'timeframe': '15min',
            'reasoning': 'BTC突破关键阻力位，动量强劲，RSI中性偏强',
            'agent_id': 'agent3_scanner',
            'timestamp': format_timestamp(generate_timestamp()),
            'factors': {
                'mom_5m': 2.5,
                'mom_15m': 3.2,
                'rsi': 65.0,
                'close': 65700,
            }
        },
    ]
    
    for signal_data in signals:
        message = {
            'msg_id': generate_msg_id(),
            'msg_type': 'signal',
            'source_agent': 'agent3_scanner',
            'target_agent': 'agent4_oracle',
            'timestamp': format_timestamp(generate_timestamp()),
            'payload': signal_data,
            'priority': 3,
        }
        
        bus.publish_signal(message)
        print(f"  🎯 {signal_data['symbol']}: {signal_data['action'].upper()}")
        print(f"     置信度: {signal_data['confidence']:.1%}")
        print(f"     预期收益: {signal_data['predicted_return']:+.1f}%")
    
    bus.flush()
    bus.close()
    print("✅ Agent3完成\n")
    return signals[0]

async def simulate_agent4(signal_data: dict):
    """模拟Agent4：决策并发送飞书通知"""
    print("="*60)
    print("🎯 Agent4: TrendOracle (决策 + 飞书通知)")
    print("="*60)
    
    print("  📈 模拟Informer预测...")
    print("  🤖 模拟RL决策...")
    print("  🧠 模拟LLM分析...")
    
    decision = {
        'symbol': signal_data['symbol'],
        'action': signal_data['action'],
        'confidence': signal_data['confidence'],
        'position_size': 0.05,
        'stop_loss': 0.02,
        'take_profit': 0.05,
        'reasoning': signal_data['reasoning'],
    }
    
    print(f"\n  📤 发送飞书通知...")
    notifier = FeishuNotifier()
    
    success = await notifier.send_signal_card(
        symbol=decision['symbol'],
        action=decision['action'],
        confidence=decision['confidence'],
        predicted_return=signal_data['predicted_return'],
        reasoning=decision['reasoning'],
        position_size=decision['position_size'],
        stop_loss=decision['stop_loss'],
        take_profit=decision['take_profit'],
        market='BTC',
    )
    
    if success:
        print("  ✅ 飞书通知发送成功!")
    else:
        print("  ⚠️ 飞书通知发送失败")
    
    await notifier.close()
    print("✅ Agent4完成\n")

async def main():
    """主测试流程"""
    print("\n" + "="*60)
    print("🚀 AM-HK 完整系统测试")
    print("   数据流: Agent1 → Agent2 → Agent3 → Agent4 → 飞书")
    print("="*60 + "\n")
    
    # 模拟完整数据流
    await simulate_agent1()
    await simulate_agent2()
    signal = await simulate_agent3()
    await simulate_agent4(signal)
    
    print("="*60)
    print("✅ 完整数据流测试完成!")
    print("="*60)
    print("\n请检查飞书群聊是否收到交易信号卡片")

if __name__ == "__main__":
    asyncio.run(main())
