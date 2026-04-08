#!/usr/bin/env python3
"""
Agent 3 测试脚本 - 模拟Agent2输出，测试Agent3机会筛选
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

import json
import time
from datetime import datetime


def create_mock_processed_data():
    """创建模拟的Agent2输出数据"""
    return {
        "symbol": "BTCUSDT",
        "market": "CRYPTO",
        "timestamp": int(time.time() * 1000),
        "data_quality": {
            "completeness": 1.0,
            "freshness_ms": 45,
            "anomaly_flags": [],
            "quality_score": 0.98
        },
        "factors": {
            # 量价因子
            "momentum_5m": 0.0234,
            "momentum_15m": 0.0456,
            "momentum_1h": 0.0678,
            "volatility_24h": 0.0321,
            "liquidity_score": 0.89,
            "volume_ratio": 1.23,
            
            # 技术指标
            "rsi_14": 62.5,
            "macd_signal": 0.015,
            "bb_position": 0.65,
            "atr_14": 450.0,
            
            # 盘口因子
            "order_imbalance": 0.12,
            "bid_pressure": 0.78,
            "ask_pressure": 0.45,
            
            # 资金流
            "funding_rate": 0.0001,
            "long_short_ratio": 1.85,
            "open_interest_change": 0.034,
            
            # 跨市场传导
            "btc_lead": 0.8,
            "eth_confirmation": 0.6,
            "spx_correlation": 0.45
        },
        "cross_market_signals": {
            "layer1_crypto": {
                "btc": {"signal": 0.75, "strength": 0.8},
                "eth": {"signal": 0.65, "strength": 0.7}
            },
            "layer2_us": {
                "coin": {"signal": 0.60, "strength": 0.6}
            }
        }
    }


def create_mock_data_multi():
    """创建多个标的的模拟数据"""
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT"]
    data_list = []
    
    for i, symbol in enumerate(symbols):
        data = create_mock_processed_data()
        data["symbol"] = symbol
        # 给不同标的不同特征
        data["factors"]["momentum_5m"] = 0.01 + i * 0.01
        data["factors"]["rsi_14"] = 45 + i * 8
        data["factors"]["liquidity_score"] = 0.7 + i * 0.05
        data_list.append(data)
    
    return data_list


def simulate_agent3_processing(processed_data_list):
    """模拟Agent3的处理逻辑"""
    print("\n" + "="*60)
    print("🚀 Agent 3 - AlphaScanner 处理结果")
    print("="*60)
    
    opportunities = []
    
    for data in processed_data_list:
        symbol = data["symbol"]
        factors = data["factors"]
        
        # 模拟多策略评分
        momentum_score = min(1.0, factors["momentum_5m"] * 20 + factors["momentum_15m"] * 10)
        value_score = 0.5 if 30 < factors["rsi_14"] < 70 else 0.8
        sentiment_score = factors["liquidity_score"] * factors["volume_ratio"] / 2
        cross_market_score = data["cross_market_signals"]["layer1_crypto"]["btc"]["signal"]
        
        # 策略权重
        weights = {
            "momentum": 0.35,
            "value": 0.20,
            "sentiment": 0.25,
            "cross_market": 0.20
        }
        
        # 综合评分
        total_score = (
            momentum_score * weights["momentum"] +
            value_score * weights["value"] +
            sentiment_score * weights["sentiment"] +
            cross_market_score * weights["cross_market"]
        )
        
        # 确定方向和置信度
        direction = "BUY" if total_score > 0.6 else "SELL" if total_score < 0.4 else "HOLD"
        confidence = abs(total_score - 0.5) * 2
        
        opportunity = {
            "symbol": symbol,
            "market": "CRYPTO",
            "timestamp": data["timestamp"],
            "direction": direction,
            "confidence": round(confidence, 4),
            "score": round(total_score, 4),
            "pool": "top5" if total_score > 0.7 else "top10" if total_score > 0.55 else "top20",
            "strategy_scores": {
                "momentum": {"score": round(momentum_score, 4), "weight": weights["momentum"]},
                "value": {"score": round(value_score, 4), "weight": weights["value"]},
                "sentiment": {"score": round(sentiment_score, 4), "weight": weights["sentiment"]},
                "cross_market": {"score": round(cross_market_score, 4), "weight": weights["cross_market"]}
            },
            "factors": {
                "momentum_5m": factors["momentum_5m"],
                "rsi_14": factors["rsi_14"],
                "liquidity_score": factors["liquidity_score"]
            }
        }
        
        opportunities.append(opportunity)
    
    # 按评分排序
    opportunities.sort(key=lambda x: x["score"], reverse=True)
    
    # 分配排名
    for i, opp in enumerate(opportunities, 1):
        opp["rank"] = i
    
    return opportunities


def print_opportunities(opportunities):
    """打印机会列表"""
    print(f"\n📊 筛选结果：共 {len(opportunities)} 个交易机会\n")
    
    # 分层显示
    pools = {"top5": "🥇 Top 5 核心仓", "top10": "🥈 Top 6-10 机会仓", "top20": "🥉 Top 11-20 观察池"}
    
    for pool_key, pool_name in pools.items():
        pool_opps = [o for o in opportunities if o["pool"] == pool_key]
        if pool_opps:
            print(f"\n{pool_name}")
            print("-" * 50)
            for opp in pool_opps:
                print(f"  #{opp['rank']} {opp['symbol']:<10} | "
                      f"方向: {opp['direction']:<4} | "
                      f"置信度: {opp['confidence']:.2%} | "
                      f"综合评分: {opp['score']:.4f}")
                print(f"     策略分解: 动量({opp['strategy_scores']['momentum']['score']:.2f}) "
                      f"价值({opp['strategy_scores']['value']['score']:.2f}) "
                      f"情绪({opp['strategy_scores']['sentiment']['score']:.2f}) "
                      f"跨市场({opp['strategy_scores']['cross_market']['score']:.2f})")
    
    print("\n" + "="*60)
    print("📤 Agent3 输出格式 (Kafka: am-hk-trading-opportunities)")
    print("="*60)
    
    # 显示第一个机会的完整输出格式
    if opportunities:
        print("\n示例输出 (TOP1):")
        print(json.dumps(opportunities[0], indent=2, ensure_ascii=False))
    
    return opportunities


def main():
    print("🔍 Agent 3 (AlphaScanner) 测试")
    print("="*60)
    print("\n📥 输入: Agent2 处理后的因子数据 (模拟)")
    
    # 创建模拟输入数据
    mock_data = create_mock_data_multi()
    
    print(f"\n接收 {len(mock_data)} 个标的的因子数据:")
    for d in mock_data:
        print(f"  - {d['symbol']}: 动量={d['factors']['momentum_5m']:.4f}, "
              f"RSI={d['factors']['rsi_14']:.1f}, "
              f"流动性={d['factors']['liquidity_score']:.2f}")
    
    # 模拟Agent3处理
    opportunities = simulate_agent3_processing(mock_data)
    
    # 打印输出
    result = print_opportunities(opportunities)
    
    print("\n✅ Agent3 测试完成")
    print(f"   输出: {len(result)} 个交易机会")
    print(f"   推送到: am-hk-trading-opportunities")
    
    return result


if __name__ == "__main__":
    main()
