#!/usr/bin/env python3
"""
Agent 5 测试脚本 - RiskGuardian 风控层
测试三层风控体系：硬规则 + 动态规则 + 异常检测
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

import json
import time


class RiskGuardian:
    """Agent 5: 三层风控系统"""
    
    def __init__(self):
        # 风控状态追踪
        self.daily_pnl = 0.0  # 当日盈亏
        self.daily_trades = 0  # 当日交易数
        self.positions = {}   # 当前持仓
        self.risk_events = [] # 风控事件日志
        
        # 风控阈值配置
        self.thresholds = {
            "max_daily_loss": 0.02,      # 单日最大亏损 2%
            "max_single_loss": 0.005,    # 单笔最大亏损 0.5%
            "max_leverage": 2.0,         # 最大杠杆 2x
            "max_positions": 10,         # 最大持仓数
            "position_size_limit": 0.15  # 单仓位上限 15%
        }
    
    def layer1_hard_rules(self, decision, portfolio_value=100000):
        """Layer 1: 硬规则检查"""
        violations = []
        
        # 检查单日亏损限制
        if self.daily_pnl < -portfolio_value * self.thresholds["max_daily_loss"]:
            violations.append(f"单日亏损超限: {self.daily_pnl:.2f} ({self.thresholds['max_daily_loss']:.1%})")
        
        # 检查单笔仓位上限
        position_value = decision["position_size"] * portfolio_value
        max_position = portfolio_value * self.thresholds["position_size_limit"]
        if position_value > max_position:
            violations.append(f"仓位超限: {decision['position_size']:.2%} (> {self.thresholds['position_size_limit']:.1%})")
        
        # 检查最大持仓数
        if len(self.positions) >= self.thresholds["max_positions"]:
            violations.append(f"持仓数超限: {len(self.positions)} (>= {self.thresholds['max_positions']})")
        
        # 检查止损设置
        if decision.get("stop_loss", 0) == 0:
            violations.append("未设置止损")
        
        return {
            "passed": len(violations) == 0,
            "layer": "Layer 1 (硬规则)",
            "violations": violations
        }
    
    def layer2_dynamic_rules(self, decision, market_state="normal"):
        """Layer 2: 动态规则检查"""
        adjustments = []
        
        # 根据市场状态调整
        if market_state == "high_volatility":
            adjustments.append({
                "type": "position_reduction",
                "reason": "高波动市场",
                "original": decision["position_size"],
                "adjusted": decision["position_size"] * 0.5
            })
        elif market_state == "strong_trend":
            if decision["confidence"] > 0.7:
                adjustments.append({
                    "type": "position_increase",
                    "reason": "强趋势+高置信度",
                    "original": decision["position_size"],
                    "adjusted": min(decision["position_size"] * 1.2, 0.15)
                })
        
        # 根据连续亏损调整
        recent_losses = sum(1 for e in self.risk_events[-5:] if e.get("type") == "loss")
        if recent_losses >= 3:
            adjustments.append({
                "type": "cooling_down",
                "reason": f"连续{recent_losses}次亏损，进入冷静期",
                "action": "reject"
            })
        
        return {
            "passed": not any(a.get("action") == "reject" for a in adjustments),
            "layer": "Layer 2 (动态规则)",
            "market_state": market_state,
            "adjustments": adjustments
        }
    
    def layer3_anomaly_detection(self, decision):
        """Layer 3: 异常检测 (Isolation Forest模拟)"""
        anomalies = []
        anomaly_score = 0.0
        
        # 检查异常特征
        features = {
            "confidence_vs_score": abs(decision["confidence"] - decision["source_opportunity"]["score"]),
            "position_size": decision["position_size"],
            "stop_loss_distance": abs(decision["entry"]["price"] - decision["stop_loss"]) / decision["entry"]["price"],
            "take_profit_ratio": abs(decision["take_profit"] - decision["entry"]["price"]) / abs(decision["entry"]["price"] - decision["stop_loss"])
        }
        
        # 异常规则
        if features["confidence_vs_score"] > 0.3:
            anomalies.append("置信度与机会评分偏差过大")
            anomaly_score += 0.3
        
        if features["position_size"] > 0.12 and decision["confidence"] < 0.5:
            anomalies.append("高仓位+低置信度")
            anomaly_score += 0.4
        
        if features["take_profit_ratio"] < 1.5:
            anomalies.append("盈亏比异常(过低)")
            anomaly_score += 0.2
        
        # 模拟Isolation Forest异常分数 (0-1)
        isolation_score = min(anomaly_score, 1.0)
        
        return {
            "passed": isolation_score < 0.7,
            "layer": "Layer 3 (异常检测)",
            "isolation_score": round(isolation_score, 4),
            "anomalies": anomalies,
            "features": features
        }
    
    def evaluate(self, decision, market_state="normal", portfolio_value=100000):
        """完整风控评估"""
        print(f"\n{'='*60}")
        print(f"🛡️ {decision['symbol']} 风控评估")
        print(f"{'='*60}")
        
        # 三层风控检查
        layer1 = self.layer1_hard_rules(decision, portfolio_value)
        layer2 = self.layer2_dynamic_rules(decision, market_state)
        layer3 = self.layer3_anomaly_detection(decision)
        
        # 打印各层结果
        print(f"\n📋 {layer1['layer']}")
        print(f"   状态: {'✅ 通过' if layer1['passed'] else '❌ 未通过'}")
        if layer1['violations']:
            for v in layer1['violations']:
                print(f"   ⚠️ {v}")
        
        print(f"\n📋 {layer2['layer']} [市场状态: {market_state}]")
        print(f"   状态: {'✅ 通过' if layer2['passed'] else '❌ 未通过'}")
        for adj in layer2['adjustments']:
            print(f"   🔄 {adj['type']}: {adj['reason']}")
            if 'adjusted' in adj:
                print(f"      仓位调整: {adj['original']:.2%} → {adj['adjusted']:.2%}")
        
        print(f"\n📋 {layer3['layer']}")
        print(f"   状态: {'✅ 通过' if layer3['passed'] else '❌ 未通过'}")
        print(f"   异常分数: {layer3['isolation_score']:.2f} (<0.7通过)")
        if layer3['anomalies']:
            for a in layer3['anomalies']:
                print(f"   ⚠️ {a}")
        
        # 综合决策
        all_passed = layer1['passed'] and layer2['passed'] and layer3['passed']
        
        # 应用动态调整
        final_position = decision["position_size"]
        for adj in layer2.get('adjustments', []):
            if 'adjusted' in adj:
                final_position = adj['adjusted']
        
        result = {
            "symbol": decision["symbol"],
            "timestamp": int(time.time() * 1000),
            "original_action": decision["action"],
            "approved": all_passed,
            "final_action": decision["action"] if all_passed else "REJECTED",
            "final_position_size": round(final_position, 4),
            
            "risk_layers": {
                "layer1_hard": layer1,
                "layer2_dynamic": layer2,
                "layer3_anomaly": layer3
            },
            
            "trade_params": {
                "entry_price": decision["entry"]["price"],
                "take_profit": decision["take_profit"],
                "stop_loss": decision["stop_loss"],
                "max_hold_time": decision["max_hold_time"]
            },
            
            "risk_metrics": {
                "risk_reward_ratio": round(
                    abs(decision["take_profit"] - decision["entry"]["price"]) /
                    abs(decision["entry"]["price"] - decision["stop_loss"]), 2
                ),
                "potential_loss_pct": round(
                    abs(decision["entry"]["price"] - decision["stop_loss"]) /
                    decision["entry"]["price"] * 100, 2
                )
            },
            
            "approval_signature": f"RG_{int(time.time())}" if all_passed else None
        }
        
        print(f"\n{'='*60}")
        print(f"📊 风控结果: {'🟢 通过' if all_passed else '🔴 拒绝'}")
        if all_passed:
            print(f"   最终动作: {result['final_action']}")
            print(f"   仓位: {result['final_position_size']:.2%}")
            print(f"   盈亏比: {result['risk_metrics']['risk_reward_ratio']}:1")
            print(f"   最大亏损: {result['risk_metrics']['potential_loss_pct']:.2f}%")
            print(f"   风控签名: {result['approval_signature']}")
        
        return result


def main():
    """主测试函数"""
    print("🚀 Agent 5 (RiskGuardian) 测试")
    print("="*60)
    print("\n📥 输入: Agent4 的交易决策")
    
    # 模拟Agent4的输出
    decisions = [
        {
            "symbol": "XRPUSDT",
            "market": "CRYPTO",
            "timestamp": int(time.time() * 1000),
            "action": "BUY",
            "confidence": 0.5968,
            "entry": {"price": 100, "time": int(time.time() * 1000)},
            "take_profit": 105.04,
            "stop_loss": 98.0,
            "position_size": 0.0893,
            "max_hold_time": "4h",
            "source_opportunity": {"score": 0.7984, "pool": "top5", "rank": 1},
            "dual_track": {
                "track_a_informer": {"predicted_return": 2.98},
                "track_b_llm": {"risk_assessment": "中等"}
            }
        },
        {
            "symbol": "DOGEUSDT",
            "market": "CRYPTO",
            "timestamp": int(time.time() * 1000),
            "action": "BUY",
            "confidence": 0.4614,
            "entry": {"price": 100, "time": int(time.time() * 1000)},
            "take_profit": 104.36,
            "stop_loss": 98.0,
            "position_size": 0.0632,
            "max_hold_time": "4h",
            "source_opportunity": {"score": 0.7307, "pool": "top5", "rank": 2},
            "dual_track": {
                "track_a_informer": {"predicted_return": 2.31},
                "track_b_llm": {"risk_assessment": "中等"}
            }
        }
    ]
    
    print(f"\n接收 {len(decisions)} 个交易决策")
    
    guardian = RiskGuardian()
    results = []
    
    for decision in decisions:
        result = guardian.evaluate(decision, market_state="normal")
        results.append(result)
    
    # 输出汇总
    print("\n" + "="*60)
    print("📤 Agent5 输出格式 (Kafka: am-hk-risk-approved-trades)")
    print("="*60)
    
    approved_results = [r for r in results if r['approved']]
    if approved_results:
        print("\n示例输出 (已审批):")
        print(json.dumps(approved_results[0], indent=2, ensure_ascii=False))
    
    print("\n" + "="*60)
    print("📊 风控审批汇总")
    print("="*60)
    for r in results:
        status_icon = "🟢" if r['approved'] else "🔴"
        print(f"{status_icon} {r['symbol']:<10} | {r['original_action']:<4} → {r['final_action']:<8} | "
              f"仓位: {r['final_position_size']:.2%}")
    
    passed = sum(1 for r in results if r['approved'])
    print(f"\n✅ Agent5 测试完成")
    print(f"   审批通过: {passed}/{len(results)}")
    print(f"   推送到: am-hk-risk-approved-trades")
    
    return results


if __name__ == "__main__":
    main()
