#!/usr/bin/env python3
"""
市场状态识别 + 动态策略切换 联合测试
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.market_state_detector import MarketStateDetector, MarketState
from core.dynamic_strategy_switcher import DynamicStrategySwitcher
from datetime import datetime


def main():
    print("🧠 市场状态识别 + 动态策略切换 联合测试")
    print("=" * 70)
    
    # 初始化模块
    detector = MarketStateDetector()
    switcher = DynamicStrategySwitcher()
    
    # 测试场景
    scenarios = [
        {
            "name": "场景1: BTC暴涨 + 美股确认 (牛市)",
            "crypto": 0.75,
            "us": 0.65,
            "details": {
                "btc_momentum": 2.1,
                "eth_momentum": 1.8,
                "coin_momentum": 3.5,
                "nvda_momentum": 1.2,
                "qqq_momentum": 0.8,
            }
        },
        {
            "name": "场景2: BTC涨但美股弱 (不确定)",
            "crypto": 0.55,
            "us": 0.15,
            "details": {
                "btc_momentum": 1.2,
                "eth_momentum": 0.8,
                "coin_momentum": 0.3,
                "nvda_momentum": -0.2,
                "qqq_momentum": -0.1,
            }
        },
        {
            "name": "场景3: BTC暴跌 + 美股同步跌 (熊市)",
            "crypto": -0.65,
            "us": -0.55,
            "details": {
                "btc_momentum": -3.5,
                "eth_momentum": -4.2,
                "coin_momentum": -5.1,
                "nvda_momentum": -2.3,
                "qqq_momentum": -1.5,
            }
        },
        {
            "name": "场景4: 窄幅震荡 (震荡市)",
            "crypto": 0.05,
            "us": -0.08,
            "details": {
                "btc_momentum": 0.1,
                "eth_momentum": -0.2,
                "coin_momentum": 0.05,
                "nvda_momentum": -0.1,
                "qqq_momentum": -0.05,
            }
        },
    ]
    
    for scenario in scenarios:
        print(f"\n{'='*70}")
        print(f"📊 {scenario['name']}")
        print(f"{'='*70}")
        
        # Step 1: 市场状态识别
        print("\n1️⃣ 市场状态识别:")
        print(f"   Layer1 (Crypto): {scenario['crypto']:+.2f}")
        print(f"   Layer2 (US): {scenario['us']:+.2f}")
        
        signal = detector.detect(
            crypto_signal=scenario['crypto'],
            us_signal=scenario['us'],
            details=scenario['details']
        )
        
        print(f"\n   ✅ 识别结果: {signal.state.value.upper()}")
        print(f"   📈 置信度: {signal.confidence}")
        print(f"   📝 描述: {detector.get_state_description(signal.state)}")
        
        # 细分指标
        print(f"\n   📊 细分指标:")
        print(f"      BTC动量: {signal.btc_momentum:+.2f}%")
        print(f"      ETH动量: {signal.eth_momentum:+.2f}%")
        print(f"      COIN动量: {signal.coin_momentum:+.2f}%")
        print(f"      NVDA动量: {signal.nvda_momentum:+.2f}%")
        print(f"      QQQ动量: {signal.qqq_momentum:+.2f}%")
        
        # Step 2: 动态策略切换
        print("\n2️⃣ 动态策略切换:")
        
        result = switcher.switch_strategy(signal)
        params = result['params']
        
        print(f"   🔄 状态变化: {'是' if result['state_changed'] else '否'}")
        print(f"\n   📋 策略参数:")
        print(f"      仓位上限: {params['position_limit']*100:.0f}%")
        print(f"      最大持仓: {params['max_positions']}只")
        print(f"      持仓周期: {params['holding_period']}")
        print(f"      止损: {params['stop_loss']} | 止盈: {params['take_profit']}")
        print(f"      调仓频率: {params['rebalance_freq']}")
        print(f"      Beta偏好: {params['beta_preference']}")
        print(f"      关注板块: {', '.join(params['sector_focus'])}")
        
        print(f"\n   💡 操作建议:")
        print(f"      {result['recommendation']}")
    
    # 汇总
    print(f"\n{'='*70}")
    print("📊 策略参数对比表")
    print(f"{'='*70}")
    print(f"{'状态':<12} {'仓位':<8} {'周期':<10} {'止损':<8} {'止盈':<8} {'频率':<10}")
    print("-" * 70)
    
    for state in [MarketState.BULL, MarketState.BEAR, MarketState.RANGE, MarketState.UNCERTAIN]:
        test_signal = type('obj', (object,), {
            'state': state,
            'confidence': 0.85,
            'crypto_score': 0.6,
            'us_score': 0.5,
            'hk_volatility': 0.15,
            'timestamp': datetime.now().isoformat(),
            'btc_momentum': 1.0,
            'eth_momentum': 0.8,
            'coin_momentum': 2.0,
            'nvda_momentum': 1.5,
            'qqq_momentum': 1.0,
        })()
        
        result = switcher.switch_strategy(test_signal)
        params = result['params']
        
        print(f"{state.value.upper():<12} "
              f"{params['position_limit']*100:>3.0f}%    "
              f"{params['holding_period']:<10} "
              f"{params['stop_loss']:<8} "
              f"{params['take_profit']:<8} "
              f"{params['rebalance_freq']:<10}")
    
    print(f"\n{'='*70}")
    print("✅ 测试完成!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
