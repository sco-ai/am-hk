#!/usr/bin/env python3
"""注入测试信号到 am-hk-trading-opportunities topic"""
import json
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.kafka import MessageBus
from core.utils import generate_msg_id, generate_timestamp

def inject_test_signal():
    message_bus = MessageBus(agent_name="test_injector")
    
    test_signal = {
        "msg_id": generate_msg_id(),
        "timestamp": generate_timestamp(),
        "source_agent": "test_injector",
        "test_mode": True,
        "opportunities": [
            {
                "symbol": "TEST.HK",
                "market": "HK",
                "direction": "BUY",
                "confidence": 0.85,
                "score": 0.92,
                "pool": "top10",
                "strategy_scores": {
                    "momentum": 0.88,
                    "value": 0.75,
                    "sentiment": 0.82
                },
                "factors": {
                    "momentum_1d": 0.05,
                    "momentum_5d": 0.12,
                    "rsi": 65.0,
                    "volume_ratio": 1.8
                }
            }
        ],
        "market_state": {
            "trend": "bullish",
            "volatility": "normal",
            "liquidity": "good"
        }
    }
    
    try:
        message_bus.send("am-hk-trading-opportunities", test_signal)
        print(f"✅ 测试信号已注入: {test_signal['msg_id']}")
        print(f"   时间戳: {test_signal['timestamp']}")
        print(f"   标的: TEST.HK")
        return True
    except Exception as e:
        print(f"❌ 注入失败: {e}")
        return False
    finally:
        message_bus.close()

if __name__ == "__main__":
    success = inject_test_signal()
    sys.exit(0 if success else 1)
