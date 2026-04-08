#!/usr/bin/env python3
"""
Brave Search 新闻采集器
使用 web_search 工具获取实时新闻
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

import json
import asyncio
from typing import List, Dict
from datetime import datetime


def search_news_brave(query: str, count: int = 5) -> List[Dict]:
    """
    使用 Brave Search 搜索新闻
    
    注意: 这是一个同步包装函数
    实际使用时通过 web_search 工具调用
    """
    # 这里返回搜索参数配置
    return {
        "query": query,
        "count": count,
        "freshness": "day",  # 24小时内
        "search_type": "news"
    }


def analyze_sentiment_simple(text: str) -> float:
    """简单情绪分析"""
    positive = ["surge", "rally", "bullish", "gain", "up", "rise", "growth", "approve", 
                "上涨", "增长", "利好", "突破", "强劲"]
    negative = ["crash", "bearish", "decline", "down", "fall", "drop", "ban", "investigation",
                "下跌", "暴跌", "利空", "监管", "调查", "风险"]
    
    text_lower = text.lower()
    score = 0
    
    for word in positive:
        if word in text_lower:
            score += 0.2
    for word in negative:
        if word in text_lower:
            score -= 0.2
    
    return max(-1.0, min(1.0, score))


def categorize_news(text: str) -> str:
    """新闻分类"""
    text_lower = text.lower()
    
    if any(w in text_lower for w in ["earnings", "revenue", "profit", "财报", "业绩", "营收", "利润"]):
        return "earnings"
    elif any(w in text_lower for w in ["sec", "regulation", "policy", "监管", "政策", "approval", "批准"]):
        return "policy"
    elif any(w in text_lower for w in ["breaking", "突发", "紧急", "暴跌", "暴涨"]):
        return "breaking"
    else:
        return "industry"


def format_news_output(symbol: str, search_results: List[Dict]) -> Dict:
    """格式化新闻分析输出"""
    if not search_results:
        return {
            "symbol": symbol,
            "sentiment_score": 0.0,
            "importance": 1,
            "category": "unknown",
            "confidence": 0.0,
            "headlines": [],
            "summary": "无相关新闻",
            "timestamp": datetime.now().isoformat()
        }
    
    # 提取标题
    headlines = []
    total_sentiment = 0
    categories = []
    
    for item in search_results:
        title = item.get("title", "")
        if title:
            headlines.append(title)
            total_sentiment += analyze_sentiment_simple(title)
            categories.append(categorize_news(title))
    
    # 平均情绪
    avg_sentiment = total_sentiment / len(headlines) if headlines else 0
    
    # 主要分类
    from collections import Counter
    category_counts = Counter(categories)
    main_category = category_counts.most_common(1)[0][0] if categories else "unknown"
    
    # 重要度 (基于分类)
    importance_map = {"breaking": 5, "earnings": 4, "policy": 4, "industry": 3, "unknown": 1}
    importance = importance_map.get(main_category, 3)
    
    # 生成摘要
    direction = "看多" if avg_sentiment > 0.2 else "看空" if avg_sentiment < -0.2 else "中性"
    summary = f"{symbol}新闻情绪{direction}, 主要涉及{main_category}类别, 重要度{importance}/5"
    
    return {
        "symbol": symbol,
        "sentiment_score": round(avg_sentiment, 2),
        "importance": importance,
        "category": main_category,
        "confidence": 0.7 if headlines else 0.0,
        "headlines": headlines[:5],
        "summary": summary,
        "timestamp": datetime.now().isoformat()
    }


# 标的搜索词映射
SYMBOL_QUERIES = {
    "BTC": "Bitcoin BTC cryptocurrency news today",
    "ETH": "Ethereum ETH crypto news today",
    "COIN": "Coinbase stock news today",
    "NVDA": "NVIDIA stock news today",
    "TSLA": "Tesla stock news today",
    "AAPL": "Apple stock news today",
    "00700": "腾讯股票 news",
    "09988": "阿里巴巴 Alibaba news",
    "03690": "美团 Meituan news",
    "00863": "OSL 数字资产 news",
}


def get_search_queries(symbol: str) -> str:
    """获取标的的搜索词"""
    return SYMBOL_QUERIES.get(symbol, f"{symbol} stock news today")


if __name__ == "__main__":
    # 测试输出格式
    print("Brave Search 新闻采集配置")
    print("="*60)
    
    for symbol, query in SYMBOL_QUERIES.items():
        config = search_news_brave(query)
        print(f"\n{symbol}:")
        print(f"  搜索词: {config['query']}")
        print(f"  时间范围: {config['freshness']}")
        print(f"  结果数: {config['count']}")
