"""
FinBERT 情绪分析模块
基于金融领域的BERT模型，专门用于分析金融文本情绪
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import httpx
import numpy as np

from core.config import settings
from core.utils import setup_logging

logger = setup_logging("finbert_analyzer")


class FinBERTAnalyzer:
    """
    FinBERT 金融情绪分析器
    
    基于Hugging Face的FinBERT模型，专门针对金融文本训练
    支持：
    - 新闻情绪分析
    - 社交媒体情绪分析
    - 财报情绪分析
    - 实时情绪聚合
    
    情绪分数范围: -1 (极度看空) ~ +1 (极度看多)
    """
    
    # 情绪标签映射
    SENTIMENT_LABELS = {
        "positive": 1.0,
        "neutral": 0.0,
        "negative": -1.0,
    }
    
    def __init__(self, api_url: str = None, api_key: str = None):
        """
        初始化FinBERT分析器
        
        Args:
            api_url: FinBERT API地址（云部署）
            api_key: API密钥
        """
        self.api_url = api_url or settings.FINBERT_API_URL or "https://api.example.com/finbert"
        self.api_key = api_key or settings.FINBERT_API_KEY
        
        # HTTP客户端
        proxy = settings.HTTP_PROXY if hasattr(settings, 'HTTP_PROXY') else None
        if proxy:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                proxies=proxy,
            )
        else:
            self.client = httpx.AsyncClient(timeout=30.0)
        
        # 本地fallback模型（简单规则）
        self.use_local_fallback = True
        
        # 情绪词典（本地fallback用）
        self.positive_words = {
            "上涨", "涨", "牛市", "突破", "利好", "强劲", "增长", "盈利",
            "买入", "推荐", "看好", "乐观", "超预期", "新高", "反弹",
            "bullish", "surge", "rally", "breakout", "strong", "growth",
            "profit", "buy", "recommend", "optimistic", "beat", "moon",
            "rocket", "gain", "up", "moon", "pump", "🚀", "📈",
        }
        
        self.negative_words = {
            "下跌", "跌", "熊市", "跌破", "利空", "疲软", "衰退", "亏损",
            "卖出", "看空", "悲观", "不及预期", "新低", "崩盘", "暴跌",
            "bearish", "crash", "dump", "weak", "recession", "loss",
            "sell", "short", "pessimistic", "miss", "down", "plunge",
            "📉", "💥", " panic",
        }
        
        logger.info("FinBERT analyzer initialized")
    
    async def analyze_text(self, text: str) -> Dict:
        """
        分析单条文本的情绪
        
        Args:
            text: 待分析的文本
        
        Returns:
            {
                "sentiment": str,  # positive/neutral/negative
                "score": float,    # -1 ~ +1
                "confidence": float,  # 0 ~ 1
                "method": str,     # finbert_api / local_fallback
            }
        """
        if not text or len(text.strip()) < 10:
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "confidence": 0.0,
                "method": "skip",
            }
        
        try:
            # 优先尝试FinBERT API
            if self.api_key:
                result = await self._call_finbert_api(text)
                if result:
                    return result
            
            # Fallback到本地规则
            if self.use_local_fallback:
                return self._local_sentiment_analysis(text)
            
        except Exception as e:
            logger.error(f"FinBERT analysis failed: {e}")
            if self.use_local_fallback:
                return self._local_sentiment_analysis(text)
        
        return {
            "sentiment": "neutral",
            "score": 0.0,
            "confidence": 0.0,
            "method": "error",
        }
    
    async def analyze_news(self, news_item: Dict) -> Dict:
        """
        分析新闻的情绪
        
        Args:
            news_item: {
                "title": str,
                "content": str,
                "source": str,
            }
        
        Returns:
            带情绪分析结果的新闻项
        """
        # 合并标题和内容
        title = news_item.get("title", "")
        content = news_item.get("content", "")
        text = f"{title}. {content}"
        
        # 分析情绪
        sentiment_result = await self.analyze_text(text)
        
        # 合并结果
        analyzed_news = news_item.copy()
        analyzed_news["sentiment"] = sentiment_result["sentiment"]
        analyzed_news["sentiment_score"] = sentiment_result["score"]
        analyzed_news["sentiment_confidence"] = sentiment_result["confidence"]
        analyzed_news["sentiment_method"] = sentiment_result["method"]
        analyzed_news["analyzed_at"] = datetime.utcnow().isoformat()
        
        logger.debug(f"Analyzed news sentiment: {sentiment_result['sentiment']} "
                    f"({sentiment_result['score']:.2f})")
        
        return analyzed_news
    
    async def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """
        批量分析文本情绪
        
        Args:
            texts: 文本列表
        
        Returns:
            情绪结果列表
        """
        results = []
        for text in texts:
            result = await self.analyze_text(text)
            results.append(result)
        return results
    
    async def aggregate_sentiment(self, 
                                   items: List[Dict],
                                   symbol: str = None) -> Dict:
        """
        聚合多个文本的情绪
        
        Args:
            items: 带情绪分析的新闻/社交媒体列表
            symbol: 标的代码
        
        Returns:
            {
                "symbol": str,
                "overall_sentiment": str,
                "overall_score": float,
                "sentiment_distribution": Dict,
                "article_count": int,
                "weighted_score": float,
            }
        """
        if not items:
            return {
                "symbol": symbol or "UNKNOWN",
                "overall_sentiment": "neutral",
                "overall_score": 0.0,
                "sentiment_distribution": {"positive": 0, "neutral": 0, "negative": 0},
                "article_count": 0,
                "weighted_score": 0.0,
            }
        
        # 统计分布
        distribution = {"positive": 0, "neutral": 0, "negative": 0}
        total_score = 0.0
        weighted_sum = 0.0
        total_weight = 0.0
        
        for item in items:
            sentiment = item.get("sentiment", "neutral")
            score = item.get("sentiment_score", 0.0)
            confidence = item.get("sentiment_confidence", 0.5)
            
            distribution[sentiment] += 1
            total_score += score
            
            # 加权平均（置信度作为权重）
            weighted_sum += score * confidence
            total_weight += confidence
        
        count = len(items)
        avg_score = total_score / count
        weighted_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        # 确定整体情绪
        if weighted_score > 0.3:
            overall = "positive"
        elif weighted_score < -0.3:
            overall = "negative"
        else:
            overall = "neutral"
        
        return {
            "symbol": symbol or "UNKNOWN",
            "overall_sentiment": overall,
            "overall_score": avg_score,
            "sentiment_distribution": distribution,
            "article_count": count,
            "weighted_score": weighted_score,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def _call_finbert_api(self, text: str) -> Optional[Dict]:
        """调用FinBERT云API"""
        if not self.api_key:
            return None
        
        try:
            response = await self.client.post(
                f"{self.api_url}/analyze",
                json={"text": text},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "sentiment": data.get("label", "neutral"),
                "score": data.get("score", 0.0),
                "confidence": data.get("confidence", 0.5),
                "method": "finbert_api",
            }
        
        except Exception as e:
            logger.warning(f"FinBERT API call failed: {e}")
            return None
    
    def _local_sentiment_analysis(self, text: str) -> Dict:
        """本地规则情绪分析（fallback）"""
        text_lower = text.lower()
        
        # 统计正负向词
        pos_count = sum(1 for word in self.positive_words if word in text_lower)
        neg_count = sum(1 for word in self.negative_words if word in text_lower)
        
        # 计算得分
        total = pos_count + neg_count
        if total == 0:
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "confidence": 0.3,
                "method": "local_fallback",
            }
        
        score = (pos_count - neg_count) / max(total, 5)  # 归一化
        score = max(-1, min(1, score))  # 限制范围
        
        # 确定情绪标签
        if score > 0.2:
            sentiment = "positive"
        elif score < -0.2:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        # 置信度基于词数量
        confidence = min(total / 10, 0.8)
        
        return {
            "sentiment": sentiment,
            "score": score,
            "confidence": confidence,
            "method": "local_fallback",
        }
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()


# === Agent2集成函数 ===

async def analyze_news_sentiment(news_items: List[Dict]) -> List[Dict]:
    """
    批量分析新闻情绪（供Agent2调用）
    
    Args:
        news_items: 新闻列表
    
    Returns:
        带情绪分析的新闻列表
    """
    analyzer = FinBERTAnalyzer()
    try:
        analyzed_items = []
        for item in news_items:
            analyzed = await analyzer.analyze_news(item)
            analyzed_items.append(analyzed)
        return analyzed_items
    finally:
        await analyzer.close()


async def get_market_sentiment(symbol: str, news_items: List[Dict]) -> Dict:
    """
    获取标的整体市场情绪（供Agent3/Agent4调用）
    
    Args:
        symbol: 标的代码
        news_items: 相关新闻列表
    
    Returns:
        情绪聚合结果
    """
    analyzer = FinBERTAnalyzer()
    try:
        # 分析所有新闻
        analyzed_items = []
        for item in news_items:
            analyzed = await analyzer.analyze_news(item)
            analyzed_items.append(analyzed)
        
        # 聚合情绪
        return await analyzer.aggregate_sentiment(analyzed_items, symbol)
    finally:
        await analyzer.close()


# === 快捷函数 ===

def quick_sentiment_score(text: str) -> float:
    """
    快速获取文本情绪分数（同步，用于简单场景）
    
    Returns:
        -1 ~ +1 的情绪分数
    """
    analyzer = FinBERTAnalyzer()
    
    # 简单规则分析
    text_lower = text.lower()
    pos_words = ["上涨", "涨", "突破", "利好", "bullish", "surge", "gain"]
    neg_words = ["下跌", "跌", "跌破", "利空", "bearish", "crash", "loss"]
    
    pos_count = sum(1 for w in pos_words if w in text_lower)
    neg_count = sum(1 for w in neg_words if w in text_lower)
    
    total = pos_count + neg_count
    if total == 0:
        return 0.0
    
    return (pos_count - neg_count) / total
