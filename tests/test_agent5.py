"""
Agent 5 (RiskGuardian) 测试脚本
测试三层风控体系
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from datetime import datetime

from agents.agent5_guardian.main import (
    RiskGuardian, HardRulesLayer, DynamicRulesLayer, 
    AnomalyDetectionLayer, MarketRegime
)
from core.models import TradeDecision, Signal, ActionType, MarketType


def create_test_decision(symbol: str, action: ActionType, 
                        position_size: float = 0.1,
                        confidence: float = 0.75,
                        stop_loss: float = 0.02,
                        take_profit: float = 0.05) -> TradeDecision:
    """创建测试决策"""
    signal = Signal(
        symbol=symbol,
        market=MarketType.HK_STOCK,
        action=action,
        confidence=confidence,
        predicted_return=0.03,
        timeframe="5min",
        reasoning="Test signal",
        agent_id="agent4_oracle",
        timestamp=datetime.now(),
    )
    
    return TradeDecision(
        signal=signal,
        position_size=position_size,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_score=0.3,
        approved=False,
        approval_reason="",
    )


def test_hard_rules():
    """测试硬规则层"""
    print("\n" + "="*60)
    print("测试 Layer 1: 硬规则层")
    print("="*60)
    
    layer = HardRulesLayer()
    
    # 测试1: 正常决策
    decision = create_test_decision("00700.HK", ActionType.BUY, position_size=0.05)
    passed, results = layer.check(decision, account_value=1000000)
    print(f"\n测试1 - 正常决策 (00700.HK, 5%仓位):")
    print(f"  结果: {'✅ 通过' if passed else '❌ 拒绝'}")
    for r in results:
        status = "✅" if r.passed else "❌"
        print(f"  {status} {r.rule_name}: {r.message}")
    
    # 测试2: 超仓位限制
    decision = create_test_decision("00700.HK", ActionType.BUY, position_size=3.0)
    passed, results = layer.check(decision, account_value=1000000)
    print(f"\n测试2 - 超杠杆 (00700.HK, 3x仓位):")
    print(f"  结果: {'✅ 通过' if passed else '❌ 拒绝'}")
    for r in results:
        if not r.passed:
            print(f"  ❌ {r.rule_name}: {r.message}")
    
    # 测试3: 大额潜在亏损
    decision = create_test_decision("00700.HK", ActionType.BUY, 
                                    position_size=0.5, stop_loss=0.05)
    passed, results = layer.check(decision, account_value=1000000)
    print(f"\n测试3 - 大额潜在亏损 (50%仓位, 5%止损):")
    print(f"  结果: {'✅ 通过' if passed else '❌ 拒绝'}")
    for r in results:
        if not r.passed:
            print(f"  ❌ {r.rule_name}: {r.message}")


def test_dynamic_rules():
    """测试动态规则层"""
    print("\n" + "="*60)
    print("测试 Layer 2: 动态规则层")
    print("="*60)
    
    layer = DynamicRulesLayer()
    
    test_cases = [
        ("高波动", {"volatility_5m": 0.05, "volatility_20d": 0.02, "adx": 20}),
        ("强趋势", {"volatility_5m": 0.01, "volatility_20d": 0.015, "adx": 50, "mom_5m": 2.0}),
        ("震荡", {"volatility_5m": 0.005, "volatility_20d": 0.02, "adx": 15}),
        ("正常", {"volatility_5m": 0.01, "volatility_20d": 0.015, "adx": 30}),
    ]
    
    for name, factors in test_cases:
        decision = create_test_decision("00700.HK", ActionType.BUY, position_size=0.1)
        regime = layer.detect_market_regime("00700.HK", factors)
        passed, results, adjustments = layer.apply_rules(decision, factors)
        
        print(f"\n测试 - {name}环境:")
        print(f"  环境判定: {regime.value}")
        print(f"  仓位限制: {adjustments['position_limit']:.0%}")
        print(f"  止损调整: {'收紧' if adjustments['sl_adjustment'] > 0 else '放宽'} "
              f"{abs(adjustments['sl_adjustment']):.0%}")
        
        # 显示调整后的参数
        adj_position = layer.adjust_position_size(0.1, regime)
        adj_sl, adj_tp = layer.adjust_stops(0.02, 0.05, regime)
        print(f"  调整后仓位: {adj_position:.2%}")
        print(f"  调整后止损: {adj_sl:.4f}, 止盈: {adj_tp:.4f}")


def test_anomaly_detection():
    """测试异常检测层"""
    print("\n" + "="*60)
    print("测试 Layer 3: 异常检测层")
    print("="*60)
    
    layer = AnomalyDetectionLayer()
    
    test_cases = [
        ("正常交易", {
            "mom_5m": 1.0,
            "volume_ma_ratio": 1.2,
            "volatility_5m": 0.015,
            "rsi": 55,
            "macd": 0.001,
            "spread": 0.05,
            "price": 500,
        }),
        ("价格异常跳变", {
            "mom_5m": 8.0,  # 异常高的动量
            "volume_ma_ratio": 1.2,
            "volatility_5m": 0.015,
            "rsi": 55,
            "macd": 0.001,
            "spread": 0.05,
            "price": 500,
        }),
        ("成交量异常", {
            "mom_5m": 1.0,
            "volume_ma_ratio": 5.0,  # 成交量激增
            "volatility_5m": 0.015,
            "rsi": 55,
            "macd": 0.001,
            "spread": 0.05,
            "price": 500,
        }),
        ("波动率异常", {
            "mom_5m": 1.0,
            "volume_ma_ratio": 1.2,
            "volatility_5m": 0.08,  # 高波动
            "volatility_20d": 0.02,
            "rsi": 55,
            "macd": 0.001,
            "spread": 0.05,
            "price": 500,
        }),
    ]
    
    for name, factors in test_cases:
        decision = create_test_decision("00700.HK", ActionType.BUY, confidence=0.7)
        result = layer.detect(decision, factors)
        
        status = "⚠️ 异常" if result.is_anomaly else "✅ 正常"
        print(f"\n{name}: {status}")
        print(f"  异常分数: {result.anomaly_score:.4f}")
        print(f"  置信度: {result.confidence:.2f}")
        if result.anomaly_features:
            print(f"  异常特征: {', '.join(result.anomaly_features)}")


def test_full_workflow():
    """测试完整风控流程"""
    print("\n" + "="*60)
    print("测试完整风控流程")
    print("="*60)
    
    guardian = RiskGuardian()
    
    scenarios = [
        ("✅ 正常通过", {
            "symbol": "00700.HK",
            "position": 0.05,
            "confidence": 0.75,
            "factors": {"volatility_5m": 0.015, "volatility_20d": 0.02, "adx": 30, "mom_5m": 1.0},
        }),
        ("❌ 超杠杆", {
            "symbol": "09988.HK",
            "position": 3.0,
            "confidence": 0.75,
            "factors": {"volatility_5m": 0.015, "volatility_20d": 0.02, "adx": 30, "mom_5m": 1.0},
        }),
        ("📝 高波动调整", {
            "symbol": "03690.HK",
            "position": 0.15,
            "confidence": 0.75,
            "factors": {"volatility_5m": 0.06, "volatility_20d": 0.02, "adx": 20, "mom_5m": 1.0},
        }),
        ("⚠️ 异常检测", {
            "symbol": "01810.HK",
            "position": 0.1,
            "confidence": 0.95,  # 过高置信度可能是异常
            "factors": {"volatility_5m": 0.015, "volatility_20d": 0.02, "adx": 30, 
                       "mom_5m": 1.0, "volume_ma_ratio": 5.0},
        }),
    ]
    
    for name, params in scenarios:
        decision = create_test_decision(
            params["symbol"], 
            ActionType.BUY,
            position_size=params["position"],
            confidence=params["confidence"]
        )
        
        # 模拟三层风控
        hard_passed, hard_results = guardian.hard_rules.check(decision, 1000000)
        _, _, adjustments = guardian.dynamic_rules.apply_rules(decision, params["factors"])
        anomaly_result = guardian.anomaly_detector.detect(decision, params["factors"])
        
        print(f"\n{name}")
        print(f"  标的: {params['symbol']}")
        print(f"  原始仓位: {params['position']:.2%}")
        
        # Layer 1
        if hard_passed:
            print(f"  硬规则: ✅ 通过")
        else:
            failed = [r.rule_name for r in hard_results if not r.passed]
            print(f"  硬规则: ❌ 未通过 ({', '.join(failed)})")
        
        # Layer 2
        regime = guardian.dynamic_rules.detect_market_regime(params["symbol"], params["factors"])
        print(f"  市场环境: {regime.value}")
        
        # Layer 3
        status = "⚠️ 异常" if anomaly_result.is_anomaly else "✅ 正常"
        print(f"  异常检测: {status} (分数: {anomaly_result.anomaly_score:.4f})")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("Agent 5 (RiskGuardian) 三层风控体系测试")
    print("="*60)
    
    try:
        test_hard_rules()
        test_dynamic_rules()
        test_anomaly_detection()
        test_full_workflow()
        
        print("\n" + "="*60)
        print("✅ 所有测试完成")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
