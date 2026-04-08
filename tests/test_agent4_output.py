#!/usr/bin/env python3
"""
Agent 4 测试脚本 - TrendOracle 决策层
测试双轨AI决策：Informer时序预测 + DeepSeek大模型推理
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

import json
import time
import os

# 模拟DeepSeek API调用
def mock_deepseek_decision(opportunity):
    """模拟DeepSeek大模型推理"""
    symbol = opportunity["symbol"]
    score = opportunity["score"]
    direction = opportunity["direction"]
    
    # 基于评分和因子生成决策理由
    reasoning = f"""
基于多维度分析：
1. 动量因子显示{symbol}短期趋势{'强劲' if score > 0.7 else '一般'}
2. RSI指标处于{'超买' if opportunity['factors'].get('rsi_14', 50) > 70 else '超卖' if opportunity['factors'].get('rsi_14', 50) < 30 else '中性'}区域
3. 市场情绪偏向{'乐观' if score > 0.6 else '谨慎'}
4. 跨市场传导信号{'确认' if score > 0.65 else '待定'}
"""
    
    return {
        "model": "deepseek-chat",
        "decision": direction,
        "confidence": opportunity["confidence"],
        "reasoning": reasoning.strip(),
        "risk_assessment": "中等" if score > 0.6 else "偏高"
    }


def mock_informer_prediction(opportunity):
    """模拟Informer时序预测"""
    symbol = opportunity["symbol"]
    current_price = 65000 if "BTC" in symbol else 3500 if "ETH" in symbol else 100
    
    # 基于评分生成价格预测
    predicted_return = (opportunity["score"] - 0.5) * 0.1  # -5% ~ +5%
    predicted_price = current_price * (1 + predicted_return)
    
    # 预测区间
    volatility = 0.02
    price_high = predicted_price * (1 + volatility)
    price_low = predicted_price * (1 - volatility)
    
    return {
        "model": "informer",
        "current_price": round(current_price, 2),
        "predicted_price": round(predicted_price, 2),
        "predicted_return": round(predicted_return * 100, 2),
        "confidence": opportunity["confidence"],
        "time_horizon": "1h",
        "price_range": {
            "low": round(price_low, 2),
            "high": round(price_high, 2)
        }
    }


def calculate_position_size(confidence, score, max_position=0.15):
    """计算仓位大小"""
    # 基于置信度和评分计算仓位
    base_size = max_position * confidence * (score / 0.8)
    return min(base_size, max_position)


def calculate_tp_sl(current_price, predicted_price, direction, volatility=0.02):
    """计算止盈止损"""
    if direction == "BUY":
        tp = predicted_price * 1.02  # 2%止盈
        sl = current_price * 0.98    # 2%止损
    else:
        tp = predicted_price * 0.98
        sl = current_price * 1.02
    
    return round(tp, 2), round(sl, 2)


def simulate_agent4_decision(opportunity):
    """模拟Agent4双轨决策"""
    symbol = opportunity["symbol"]
    
    # Track A: Informer时序预测 (80%权重)
    track_a = mock_informer_prediction(opportunity)
    
    # Track B: DeepSeek大模型推理 (20%权重)
    track_b = mock_deepseek_decision(opportunity)
    
    # 双轨融合
    final_confidence = track_a["confidence"] * 0.8 + track_b["confidence"] * 0.2
    
    # 决策逻辑
    action = opportunity["direction"]
    if final_confidence < 0.4:
        action = "HOLD"
    
    # 计算交易参数
    current_price = track_a["current_price"]
    position_size = calculate_position_size(final_confidence, opportunity["score"])
    tp, sl = calculate_tp_sl(current_price, track_a["predicted_price"], action)
    
    decision = {
        "symbol": symbol,
        "market": opportunity["market"],
        "timestamp": int(time.time() * 1000),
        "action": action,
        "confidence": round(final_confidence, 4),
        
        # 入场参数
        "entry": {
            "price": current_price,
            "time": int(time.time() * 1000)
        },
        
        # 止盈止损
        "take_profit": tp,
        "stop_loss": sl,
        
        # 仓位管理
        "position_size": round(position_size, 4),
        "max_hold_time": "4h",
        
        # 双轨决策详情
        "dual_track": {
            "track_a_informer": track_a,
            "track_b_llm": track_b,
            "fusion_weight": {"informer": 0.8, "llm": 0.2}
        },
        
        # 来源信息
        "source_opportunity": {
            "score": opportunity["score"],
            "pool": opportunity["pool"],
            "rank": opportunity["rank"]
        },
        
        # 风险警示
        "risk_warnings": [
            "波动率较高，建议分批入场" if opportunity["score"] > 0.75 else "正常波动"
        ]
    }
    
    return decision


def print_decision(decision):
    """打印决策结果"""
    print(f"\n{'='*60}")
    print(f"📊 {decision['symbol']} 交易决策")
    print(f"{'='*60}")
    
    print(f"\n🎯 核心决策:")
    print(f"   动作: {decision['action']}")
    print(f"   置信度: {decision['confidence']:.2%}")
    print(f"   入场价: ${decision['entry']['price']}")
    print(f"   止盈: ${decision['take_profit']}")
    print(f"   止损: ${decision['stop_loss']}")
    print(f"   仓位: {decision['position_size']:.2%}")
    
    print(f"\n🔬 Track A - Informer时序预测 (80%权重):")
    track_a = decision['dual_track']['track_a_informer']
    print(f"   预测价格: ${track_a['predicted_price']}")
    print(f"   预期收益: {track_a['predicted_return']:+.2f}%")
    print(f"   价格区间: ${track_a['price_range']['low']} ~ ${track_a['price_range']['high']}")
    
    print(f"\n🧠 Track B - DeepSeek大模型推理 (20%权重):")
    track_b = decision['dual_track']['track_b_llm']
    print(f"   模型: {track_b['model']}")
    print(f"   风险评估: {track_b['risk_assessment']}")
    print(f"   推理:\n{track_b['reasoning']}")
    
    print(f"\n⚠️ 风险提示:")
    for warning in decision['risk_warnings']:
        print(f"   - {warning}")


def main():
    """主测试函数"""
    print("🚀 Agent 4 (TrendOracle) 测试")
    print("="*60)
    print("\n📥 输入: Agent3 筛选的交易机会")
    
    # 模拟Agent3的输出
    opportunities = [
        {
            "symbol": "XRPUSDT",
            "market": "CRYPTO",
            "timestamp": int(time.time() * 1000),
            "direction": "BUY",
            "confidence": 0.5968,
            "score": 0.7984,
            "pool": "top5",
            "rank": 1,
            "factors": {"rsi_14": 77, "momentum_5m": 0.05}
        },
        {
            "symbol": "DOGEUSDT",
            "market": "CRYPTO",
            "timestamp": int(time.time() * 1000),
            "direction": "BUY",
            "confidence": 0.4614,
            "score": 0.7307,
            "pool": "top5",
            "rank": 2,
            "factors": {"rsi_14": 69, "momentum_5m": 0.04}
        }
    ]
    
    print(f"\n接收 {len(opportunities)} 个交易机会")
    
    decisions = []
    for opp in opportunities:
        print(f"\n处理: {opp['symbol']} (评分: {opp['score']:.4f})")
        decision = simulate_agent4_decision(opp)
        print_decision(decision)
        decisions.append(decision)
    
    # 输出汇总
    print("\n" + "="*60)
    print("📤 Agent4 输出格式 (Kafka: am-hk-trading-decisions)")
    print("="*60)
    
    if decisions:
        print("\n示例输出 (TOP1):")
        print(json.dumps(decisions[0], indent=2, ensure_ascii=False))
    
    print("\n" + "="*60)
    print("📊 决策汇总")
    print("="*60)
    for d in decisions:
        status_icon = "🟢" if d['action'] == "BUY" else "🔴" if d['action'] == "SELL" else "⚪"
        print(f"{status_icon} {d['symbol']:<10} | {d['action']:<4} | "
              f"置信度: {d['confidence']:.2%} | 仓位: {d['position_size']:.2%}")
    
    print("\n✅ Agent4 测试完成")
    print(f"   输出: {len(decisions)} 个交易决策")
    print(f"   推送到: am-hk-trading-decisions")
    
    return decisions


if __name__ == "__main__":
    main()
