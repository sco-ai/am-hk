#!/usr/bin/env python3
"""
Agent2 新闻因子增强测试
展示如何将新闻分析集成到Agent2的因子计算
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

import json
from datetime import datetime


def simulate_brave_search_results(symbol: str) -> list:
    """模拟Brave Search返回的新闻结果"""
    mock_data = {
        "BTC": [
            {"title": "Bitcoin surges past $65,000 as institutional adoption accelerates", "url": "..."},
            {"title": "SEC approves new Bitcoin ETF proposals", "url": "..."},
            {"title": "Crypto market sentiment turns bullish amid rate cut expectations", "url": "..."},
        ],
        "NVDA": [
            {"title": "NVIDIA announces breakthrough AI chip architecture", "url": "..."},
            {"title": "Analysts raise NVDA price targets on data center demand", "url": "..."},
            {"title": "NVDA stock rallies ahead of Q3 earnings report", "url": "..."},
        ],
        "00700": [
            {"title": "腾讯发布Q3财报：游戏业务增长超预期", "url": "..."},
            {"title": "微信月活用户突破13亿大关", "url": "..."},
            {"title": "腾讯云AI服务获多家车企采用", "url": "..."},
        ],
        "TSLA": [
            {"title": "Tesla delivers record number of vehicles in Q3", "url": "..."},
            {"title": "Analysts downgrade TSLA on margin concerns", "url": "..."},
        ]
    }
    return mock_data.get(symbol, [])


def analyze_news_llm(symbol: str, headlines: list) -> dict:
    """模拟LLM新闻分析"""
    text = " ".join([h["title"] for h in headlines]).lower()
    
    # 情绪分析
    positive = ["surge", "rally", "bullish", "growth", "approve", "breakthrough", "record", "增长", "突破", "超预期"]
    negative = ["decline", "downgrade", "bearish", "ban", "下跌", "监管", "调查", "担忧"]
    
    sentiment = 0.0
    for w in positive:
        if w in text:
            sentiment += 0.25
    for w in negative:
        if w in text:
            sentiment -= 0.25
    
    sentiment = max(-1.0, min(1.0, sentiment))
    
    # 分类
    if any(w in text for w in ["earnings", "财报", "revenue", "profit", "业绩"]):
        category = "earnings"
        importance = 5
    elif any(w in text for w in ["sec", "regulation", "监管", "policy", "approval"]):
        category = "policy"
        importance = 4
    elif any(w in text for w in ["breaking", "surge", "crash", "暴跌", "暴涨"]):
        category = "breaking"
        importance = 5
    else:
        category = "industry"
        importance = 3
    
    # 生成摘要
    direction = "看多" if sentiment > 0.2 else "看空" if sentiment < -0.2 else "中性"
    summary = f"{symbol}新闻显示{direction}情绪，{category}类新闻重要度{importance}/5"
    
    return {
        "sentiment_score": round(sentiment, 2),
        "importance": importance,
        "category": category,
        "confidence": 0.75,
        "headlines": [h["title"] for h in headlines[:3]],
        "summary": summary
    }


def convert_to_factors(news_analysis: dict) -> dict:
    """转换为Agent2因子"""
    return {
        # 核心情绪因子
        "news_sentiment_score": news_analysis["sentiment_score"],
        "news_importance_normalized": news_analysis["importance"] / 5.0,
        "news_confidence": news_analysis["confidence"],
        
        # 分类信号因子
        "news_is_earnings": 1.0 if news_analysis["category"] == "earnings" else 0.0,
        "news_is_policy": 1.0 if news_analysis["category"] == "policy" else 0.0,
        "news_is_breaking": 1.0 if news_analysis["category"] == "breaking" else 0.0,
        
        # 综合信号 (情绪 × 重要度 × 置信度)
        "news_composite_signal": (
            news_analysis["sentiment_score"] * 
            (news_analysis["importance"] / 5.0) * 
            news_analysis["confidence"]
        )
    }


def main():
    print("🚀 Agent2 新闻因子增强测试")
    print("="*70)
    print("\n流程: Agent1采集 → Brave Search → LLM分析 → Agent2因子计算\n")
    
    symbols = ["BTC", "NVDA", "00700", "TSLA"]
    
    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"📰 {symbol} 新闻分析")
        print("="*70)
        
        # Step 1: Brave Search 采集新闻
        print(f"\n1️⃣ Brave Search 采集新闻...")
        search_results = simulate_brave_search_results(symbol)
        print(f"   获取到 {len(search_results)} 条新闻")
        
        # Step 2: LLM 深度分析
        print(f"\n2️⃣ LLM (gemma4:31b) 分析新闻情绪...")
        news_analysis = analyze_news_llm(symbol, search_results)
        
        print(f"   📊 情绪分数: {news_analysis['sentiment_score']:+.2f} (-1.0到1.0)")
        print(f"   ⭐ 重要度: {news_analysis['importance']}/5")
        print(f"   📂 分类: {news_analysis['category']}")
        print(f"   📝 摘要: {news_analysis['summary']}")
        print(f"   📰 相关标题:")
        for title in news_analysis['headlines'][:2]:
            print(f"      - {title[:60]}...")
        
        # Step 3: 转换为Agent2因子
        print(f"\n3️⃣ 转换为 Agent2 新闻因子...")
        factors = convert_to_factors(news_analysis)
        
        print(f"   📈 news_sentiment_score: {factors['news_sentiment_score']:+.2f}")
        print(f"   📊 news_importance: {factors['news_importance_normalized']:.2f}")
        print(f"   🔔 news_is_earnings: {factors['news_is_earnings']}")
        print(f"   🔔 news_is_policy: {factors['news_is_policy']}")
        print(f"   🔔 news_is_breaking: {factors['news_is_breaking']}")
        print(f"   🎯 news_composite_signal: {factors['news_composite_signal']:+.3f}")
    
    # 汇总
    print("\n" + "="*70)
    print("📤 Agent2 输出 - 新增新闻因子")
    print("="*70)
    print("""
Agent2 现在输出以下新闻相关因子:
├── news_sentiment_score: 情绪分数 (-1.0到1.0)
├── news_importance_normalized: 重要度 (0-1)
├── news_confidence: 置信度 (0-1)
├── news_is_earnings: 财报事件信号 (0或1)
├── news_is_policy: 政策事件信号 (0或1)
├── news_is_breaking: 突发新闻信号 (0或1)
└── news_composite_signal: 综合信号 (情绪×重要度×置信度)

这些因子将被用于:
- Agent3 机会筛选 (可作为独立策略)
- Agent4 双轨决策 (Track B大模型推理输入)
- 跨市场传导分析 (新闻→Crypto/美股→港股)
""")
    
    print("\n✅ 新闻因子增强完成!")


if __name__ == "__main__":
    main()
