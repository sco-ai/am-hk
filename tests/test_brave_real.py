#!/usr/bin/env python3
"""
Brave Search 实时新闻采集测试
使用真实 API Key 测试
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

import os
import json
import urllib.request
import ssl
from datetime import datetime

# API Key (从配置读取或环境变量)
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "BSALAGnFDtwhY_lbJZ3idSix8JgfY9e")

SYMBOLS = {
    "BTC": "Bitcoin BTC cryptocurrency news today",
    "NVDA": "NVIDIA stock news today",
    "00700": "腾讯股票 news",
    "COIN": "Coinbase stock news today",
}


def brave_search_news(query, count=5):
    """使用 Brave Search API 搜索新闻"""
    url = f"https://api.search.brave.com/res/v1/news/search?q={query.replace(' ', '+')}&count={count}&freshness=day"
    
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        
        # 跳过 SSL 验证 (测试环境)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            data = json.loads(response.read().decode())
            return data.get("results", [])
    except Exception as e:
        print(f"   ❌ 搜索失败: {e}")
        return []


def analyze_sentiment_simple(text):
    """简单情绪分析"""
    positive = ["surge", "rally", "bullish", "gain", "up", "rise", "growth", "approve",
                "上涨", "增长", "利好", "突破", "强劲", "accelerates", "record"]
    negative = ["crash", "bearish", "decline", "down", "fall", "drop", "ban", "investigation",
                "下跌", "暴跌", "利空", "监管", "调查", "风险", "concerns"]
    
    text_lower = text.lower()
    score = 0
    
    for w in positive:
        if w in text_lower:
            score += 0.25
    for w in negative:
        if w in text_lower:
            score -= 0.25
    
    return max(-1.0, min(1.0, score))


def categorize_news(text):
    """新闻分类"""
    text_lower = text.lower()
    
    if any(w in text_lower for w in ["earnings", "财报", "revenue", "profit", "业绩", "营收"]):
        return "earnings", 5
    elif any(w in text_lower for w in ["sec", "regulation", "监管", "policy", "approval"]):
        return "policy", 4
    elif any(w in text_lower for w in ["breaking", "surge", "crash", "暴跌", "暴涨"]):
        return "breaking", 5
    else:
        return "industry", 3


def main():
    print("🚀 Brave Search 实时新闻采集测试")
    print("="*70)
    print(f"\nAPI Key: {BRAVE_API_KEY[:10]}...{BRAVE_API_KEY[-4:]}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    for symbol, query in SYMBOLS.items():
        print(f"\n{'='*70}")
        print(f"📰 {symbol} - 实时新闻搜索")
        print(f"{'='*70}")
        print(f"搜索词: {query}")
        
        # 搜索新闻
        print("\n🔍 调用 Brave Search API...")
        results = brave_search_news(query)
        
        if not results:
            print("   ⚠️ 未获取到新闻")
            continue
        
        print(f"   ✅ 获取到 {len(results)} 条新闻")
        
        # 分析新闻
        sentiments = []
        categories = []
        
        print("\n📊 新闻标题:")
        for i, item in enumerate(results[:3], 1):
            title = item.get("title", "")
            source = item.get("source", {}).get("name", "Unknown")
            
            print(f"   {i}. {title[:65]}...")
            print(f"      来源: {source}")
            
            # 情绪分析
            sentiment = analyze_sentiment_simple(title)
            sentiments.append(sentiment)
            
            # 分类
            cat, _ = categorize_news(title)
            categories.append(cat)
        
        # 汇总分析
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
        main_category = max(set(categories), key=categories.count) if categories else "unknown"
        _, importance = categorize_news(" ".join([r.get("title", "") for r in results]))
        
        # 生成摘要
        direction = "看多" if avg_sentiment > 0.2 else "看空" if avg_sentiment < -0.2 else "中性"
        
        print(f"\n📈 分析结果:")
        print(f"   情绪分数: {avg_sentiment:+.2f} ({direction})")
        print(f"   新闻分类: {main_category}")
        print(f"   重要度: {importance}/5")
        print(f"   综合信号: {avg_sentiment * (importance/5):+.3f}")
    
    print("\n" + "="*70)
    print("✅ Brave Search 新闻采集测试完成!")
    print("="*70)


if __name__ == "__main__":
    main()
