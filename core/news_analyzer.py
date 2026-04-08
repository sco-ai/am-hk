"""
增强型新闻推理模块 - NewsAnalyzer
使用 Brave Search + LLM 进行深度新闻分析
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import httpx

from core.utils import setup_logging

logger = setup_logging("news_analyzer")


class NewsAnalyzer:
    """
    新闻分析器 - 增强版
    
    功能:
    1. Brave Search 实时新闻搜索
    2. LLM 情绪分析 (Ollama/DeepSeek)
    3. 重要度评级
    4. 分类标签
    5. 标的关联度评分
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client  # 大模型客户端
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # 标的与关键词映射
        self.symbol_keywords = {
            "BTC": ["Bitcoin", "BTC", "crypto", "cryptocurrency", "blockchain"],
            "ETH": ["Ethereum", "ETH", "DeFi", "smart contract"],
            "COIN": ["Coinbase", "crypto exchange", "listing"],
            "NVDA": ["NVIDIA", "AI chips", "GPU", "data center"],
            "TSLA": ["Tesla", "Elon Musk", "EV", "electric vehicle"],
            "AAPL": ["Apple", "iPhone", "Tim Cook", "App Store"],
            "00700": ["腾讯", "Tencent", "WeChat", "游戏"],
            "09988": ["阿里巴巴", "Alibaba", "淘宝", "阿里云"],
            "03690": ["美团", "Meituan", "外卖"],
            "00863": ["OSL", "数字资产", "加密货币"],
        }
        
        # 情绪缓存
        self.sentiment_cache: Dict[str, Dict] = {}
    
    async def analyze_news_for_symbol(self, symbol: str) -> Dict:
        """
        为指定标的分析新闻
        
        Returns:
            {
                "symbol": str,
                "sentiment_score": float,  # -1.0 to 1.0
                "importance": int,         # 1-5
                "category": str,           # earnings/policy/industry/breaking
                "confidence": float,       # 0-1
                "headlines": List[str],    # 相关标题
                "summary": str,            # AI摘要
                "timestamp": str,
            }
        """
        # 1. Brave Search 搜索新闻
        headlines = await self._brave_search_news(symbol)
        
        if not headlines:
            return self._empty_analysis(symbol)
        
        # 2. LLM 深度分析
        analysis = await self._llm_analyze_news(symbol, headlines)
        
        result = {
            "symbol": symbol,
            "sentiment_score": analysis["sentiment"],
            "importance": analysis["importance"],
            "category": analysis["category"],
            "confidence": analysis["confidence"],
            "headlines": headlines[:5],
            "summary": analysis["summary"],
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info(f"News analysis for {symbol}: sentiment={result['sentiment_score']:.2f}, "
                   f"importance={result['importance']}, category={result['category']}")
        
        return result
    
    async def _brave_search_news(self, symbol: str) -> List[str]:
        """使用 Brave Search 搜索新闻 (模拟)"""
        # 实际调用 Brave Search API
        # 这里模拟搜索结果
        keywords = self.symbol_keywords.get(symbol, [symbol])
        
        # 模拟新闻标题
        mock_headlines = {
            "BTC": [
                "Bitcoin surges past $65K as institutional adoption grows",
                "SEC approves new Bitcoin ETF applications",
                "Crypto market sentiment turns bullish on rate cut hopes",
            ],
            "NVDA": [
                "NVIDIA announces new AI chip architecture",
                "Analysts raise price targets on strong data center demand",
                "NVDA stock rallies ahead of earnings report",
            ],
            "00700": [
                "腾讯发布Q3财报，游戏业务增长超预期",
                "微信月活用户突破13亿",
                "腾讯云AI服务获多家车企采用",
            ],
        }
        
        return mock_headlines.get(symbol, [f"{symbol} market update"])
    
    async def _llm_analyze_news(self, symbol: str, headlines: List[str]) -> Dict:
        """使用大模型分析新闻"""
        
        prompt = f"""你是一位专业的金融新闻分析师。请分析以下关于 {symbol} 的新闻标题：

新闻标题:
{chr(10).join(f"- {h}" for h in headlines)}

请输出 JSON 格式分析结果:
{{
    "sentiment": float,  // 情绪分数 -1.0(极度看空) 到 1.0(极度看多)
    "importance": int,   // 重要度 1-5 (5为最重要)
    "category": string,  // 分类: "earnings"(财报), "policy"(政策), "industry"(行业), "breaking"(突发)
    "confidence": float, // 置信度 0-1
    "summary": string    // 一句话摘要(中文)
}}

要求:
1. 基于新闻标题判断整体市场情绪
2. 如果是财报相关, importance 至少为4
3. 如果是监管政策, sentiment 需反映政策影响方向
4. summary 使用中文, 简洁明了
"""
        
        # 如果有 LLM 客户端, 调用大模型
        if self.llm_client:
            try:
                response = await self.llm_client.chat(
                    messages=[{"role": "user", "content": prompt}]
                )
                # 解析 JSON
                import re
                json_match = re.search(r'\{[^}]+\}', response)
                if json_match:
                    return json.loads(json_match.group())
            except Exception as e:
                logger.error(f"LLM analysis failed: {e}")
        
        # 默认分析结果 (模拟)
        return self._simulate_analysis(symbol, headlines)
    
    def _simulate_analysis(self, symbol: str, headlines: List[str]) -> Dict:
        """模拟分析结果"""
        # 基于关键词简单判断
        text = " ".join(headlines).lower()
        
        positive_words = ["surge", "rally", "bullish", "growth", "approve", "strong", "增长", "上涨", "超预期"]
        negative_words = ["crash", "bearish", "decline", "ban", "investigation", "下跌", "监管", "调查"]
        
        sentiment = 0.0
        for word in positive_words:
            if word in text:
                sentiment += 0.3
        for word in negative_words:
            if word in text:
                sentiment -= 0.3
        
        sentiment = max(-1.0, min(1.0, sentiment))
        
        # 重要度
        importance = 3
        if any(w in text for w in ["earnings", "财报", "earnings", "report"]):
            importance = 5
        elif any(w in text for w in ["SEC", "监管", "policy", "approval"]):
            importance = 4
        
        # 分类
        category = "industry"
        if any(w in text for w in ["earnings", "财报", "revenue", "profit"]):
            category = "earnings"
        elif any(w in text for w in ["SEC", "监管", "policy", "regulation", "approve"]):
            category = "policy"
        elif any(w in text for w in ["surge", "crash", "breaking", "突发"]):
            category = "breaking"
        
        return {
            "sentiment": round(sentiment, 2),
            "importance": importance,
            "category": category,
            "confidence": 0.75,
            "summary": f"{symbol}相关新闻显示{'积极' if sentiment > 0 else '谨慎'}情绪, "
                      f"{'重要' if importance >= 4 else '一般'}影响"
        }
    
    def _empty_analysis(self, symbol: str) -> Dict:
        """空分析结果"""
        return {
            "symbol": symbol,
            "sentiment_score": 0.0,
            "importance": 1,
            "category": "unknown",
            "confidence": 0.0,
            "headlines": [],
            "summary": "无相关新闻",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def analyze_all_symbols(self, symbols: List[str]) -> Dict[str, Dict]:
        """批量分析多个标的"""
        results = {}
        for symbol in symbols:
            results[symbol] = await self.analyze_news_for_symbol(symbol)
        return results


# === Agent2 集成函数 ===

def convert_news_to_factors(news_analysis: Dict) -> Dict[str, float]:
    """
    将新闻分析结果转换为Agent2可用的因子
    
    Returns:
        {
            "news_sentiment_score": float,    # -1.0 to 1.0
            "news_importance": float,         # 0.0 to 1.0 (归一化)
            "news_category_earnings": float,  # 0 or 1
            "news_category_policy": float,    # 0 or 1
            "news_category_breaking": float,  # 0 or 1
            "news_confidence": float,         # 0.0 to 1.0
        }
    """
    category = news_analysis.get("category", "unknown")
    
    return {
        "news_sentiment_score": news_analysis.get("sentiment_score", 0.0),
        "news_importance": news_analysis.get("importance", 1) / 5.0,
        "news_category_earnings": 1.0 if category == "earnings" else 0.0,
        "news_category_policy": 1.0 if category == "policy" else 0.0,
        "news_category_breaking": 1.0 if category == "breaking" else 0.0,
        "news_confidence": news_analysis.get("confidence", 0.0),
    }


# === 便捷函数 ===

async def fetch_enhanced_news_analysis(symbols: List[str], llm_client=None) -> Dict[str, Dict]:
    """
    获取增强型新闻分析
    
    Usage:
        analysis = await fetch_enhanced_news_analysis(["BTC", "NVDA", "00700"])
    """
    analyzer = NewsAnalyzer(llm_client=llm_client)
    return await analyzer.analyze_all_symbols(symbols)


# === 测试 ===

if __name__ == "__main__":
    async def test():
        analyzer = NewsAnalyzer()
        
        symbols = ["BTC", "NVDA", "00700"]
        results = await analyzer.analyze_all_symbols(symbols)
        
        for symbol, analysis in results.items():
            print(f"\n{symbol}:")
            print(f"  情绪: {analysis['sentiment_score']:+.2f}")
            print(f"  重要度: {analysis['importance']}/5")
            print(f"  分类: {analysis['category']}")
            print(f"  摘要: {analysis['summary']}")
            
            # 转换为因子
            factors = convert_news_to_factors(analysis)
            print(f"  因子: {factors}")
    
    asyncio.run(test())
