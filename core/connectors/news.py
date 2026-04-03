"""
新闻数据连接器
支持多个新闻源：NewsAPI、Twitter/X、Reddit、财联社等
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

import httpx

from core.config import settings
from core.models import MarketType, DataType
from core.utils import setup_logging

logger = setup_logging("news_connector")


class NewsConnector:
    """
    新闻数据连接器
    
    支持：
    - NewsAPI (国际新闻)
    - Twitter/X API (社交媒体情绪)
    - Reddit (社区情绪)
    - 财联社/华尔街见闻 (中文财经)
    
    数据格式统一为NLP情绪分析可用的结构
    """
    
    def __init__(self):
        # API密钥 - 优先从settings读取，其次环境变量
        self.newsapi_key = settings.NEWSAPI_KEY or os.getenv("NEWSAPI_KEY", "")
        self.twitter_bearer = settings.TWITTER_BEARER_TOKEN or os.getenv("TWITTER_BEARER_TOKEN", "")
        self.reddit_client_id = settings.REDDIT_CLIENT_ID or os.getenv("REDDIT_CLIENT_ID", "")
        self.reddit_secret = settings.REDDIT_SECRET or os.getenv("REDDIT_SECRET", "")
        
        # HTTP客户端（带代理支持）
        proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        if proxy:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                proxies=proxy,
            )
            logger.info(f"News connector using proxy: {proxy}")
        else:
            self.client = httpx.AsyncClient(timeout=30.0)
        
        # 订阅的标的和关键词
        self.subscriptions: Dict[str, List[str]] = {
            "BTC": ["bitcoin", "BTC", "crypto", "cryptocurrency"],
            "ETH": ["ethereum", "ETH", "crypto"],
            "AAPL": ["Apple", "AAPL", "iPhone", "Tim Cook"],
            "TSLA": ["Tesla", "TSLA", "Elon Musk", "EV"],
            "NVDA": ["NVIDIA", "NVDA", "AI chips", "GPU"],
            "00700": ["腾讯", "Tencent", "00700", "WeChat"],
            "09988": ["阿里", "Alibaba", "09988", "淘宝"],
        }
        
        # 情绪缓存（用于去重）
        self.seen_articles: set = set()
        self.max_cache_size = 1000
        
        logger.info("News connector initialized")
    
    async def connect(self):
        """建立连接"""
        logger.info("News connector connected")
    
    async def disconnect(self):
        """断开连接"""
        await self.client.aclose()
        logger.info("News connector disconnected")
    
    # === NewsAPI ===
    
    async def fetch_newsapi(self, query: str = None, category: str = "business") -> List[Dict]:
        """
        从NewsAPI获取新闻
        
        Args:
            query: 搜索关键词
            category: 类别 (business, technology, etc.)
        
        Returns:
            新闻列表
        """
        if not self.newsapi_key:
            logger.warning("NewsAPI key not configured")
            return []
        
        url = "https://newsapi.org/v2/top-headlines"
        
        params = {
            "apiKey": self.newsapi_key,
            "category": category,
            "language": "en",
            "pageSize": 20,
        }
        
        if query:
            params["q"] = query
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            articles = []
            for article in data.get("articles", []):
                news_item = self._convert_newsapi_format(article)
                if news_item and self._is_new_article(news_item["id"]):
                    articles.append(news_item)
            
            logger.info(f"Fetched {len(articles)} articles from NewsAPI")
            return articles
        
        except Exception as e:
            logger.error(f"NewsAPI fetch failed: {e}")
            return []
    
    # === Twitter/X API ===
    
    async def fetch_twitter_sentiment(self, symbol: str) -> Dict:
        """
        获取Twitter情绪数据
        
        Returns:
            {
                "symbol": str,
                "sentiment_score": float,  # -1 to 1
                "tweet_volume": int,
                "trending_hashtags": List[str],
            }
        """
        if not self.twitter_bearer:
            logger.warning("Twitter bearer token not configured")
            return self._empty_sentiment(symbol)
        
        keywords = self.subscriptions.get(symbol, [symbol])
        query = " OR ".join(keywords[:3])
        
        url = "https://api.twitter.com/2/tweets/search/recent"
        
        headers = {
            "Authorization": f"Bearer {self.twitter_bearer}"
        }
        
        params = {
            "query": f"{query} -is:retweet lang:en",
            "max_results": 100,
            "tweet.fields": "public_metrics,created_at",
        }
        
        try:
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            tweets = data.get("data", [])
            
            # 简单情绪分析（基于关键词）
            sentiment = self._analyze_twitter_sentiment(tweets)
            
            result = {
                "symbol": symbol,
                "sentiment_score": sentiment["score"],
                "tweet_volume": len(tweets),
                "trending_hashtags": sentiment["hashtags"],
                "source": "twitter",
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            logger.info(f"Twitter sentiment for {symbol}: {result['sentiment_score']:.2f}")
            return result
        
        except Exception as e:
            logger.error(f"Twitter fetch failed: {e}")
            return self._empty_sentiment(symbol)
    
    # === 中文财经新闻 (模拟接口) ===
    
    async def fetch_cn_financial_news(self, symbol: str) -> List[Dict]:
        """
        获取中文财经新闻
        
        实际应接入：
        - 财联社 API
        - 华尔街见闻 API
        - 东方财富 API
        """
        logger.info(f"Fetching CN financial news for {symbol}")
        
        # TODO: 接入实际的中文财经API
        # 当前返回模拟数据
        
        mock_news = [
            {
                "id": f"cn_{symbol}_{datetime.now().strftime('%Y%m%d')}",
                "title": f"{symbol}相关市场动态",
                "content": "市场今日表现活跃，投资者情绪积极。",
                "source": "财联社",
                "timestamp": datetime.utcnow().isoformat(),
                "sentiment": "positive",
                "url": "https://www.cls.cn/",
            }
        ]
        
        return mock_news
    
    # === 内部方法 ===
    
    def _convert_newsapi_format(self, article: Dict) -> Optional[Dict]:
        """转换为统一格式"""
        try:
            return {
                "id": article.get("url", ""),  # 使用URL作为唯一ID
                "title": article.get("title", ""),
                "content": article.get("description", ""),
                "source": article.get("source", {}).get("name", "unknown"),
                "author": article.get("author", ""),
                "url": article.get("url", ""),
                "published_at": article.get("publishedAt", ""),
                "timestamp": datetime.utcnow().isoformat(),
                "sentiment": None,  # 待NLP分析
                "market": "news",
            }
        except Exception as e:
            logger.error(f"Error converting article: {e}")
            return None
    
    def _is_new_article(self, article_id: str) -> bool:
        """检查是否是新文章（去重）"""
        if article_id in self.seen_articles:
            return False
        
        self.seen_articles.add(article_id)
        
        # 限制缓存大小
        if len(self.seen_articles) > self.max_cache_size:
            self.seen_articles = set(list(self.seen_articles)[-500:])
        
        return True
    
    def _analyze_twitter_sentiment(self, tweets: List[Dict]) -> Dict:
        """简单Twitter情绪分析"""
        if not tweets:
            return {"score": 0.0, "hashtags": []}
        
        # 简单关键词匹配（实际应使用FinBERT或GPT）
        positive_words = ["bullish", "moon", "gain", "profit", "up", "buy", "🚀", "📈"]
        negative_words = ["bearish", "crash", "loss", "down", "sell", "dump", "📉"]
        
        score = 0
        hashtags = set()
        
        for tweet in tweets:
            text = tweet.get("text", "").lower()
            
            for word in positive_words:
                if word in text:
                    score += 0.1
            
            for word in negative_words:
                if word in text:
                    score -= 0.1
            
            # 提取hashtag
            for word in text.split():
                if word.startswith("#"):
                    hashtags.add(word)
        
        # 归一化到 -1 到 1
        score = max(-1, min(1, score / len(tweets) if tweets else 0))
        
        return {
            "score": score,
            "hashtags": list(hashtags)[:10],
        }
    
    def _empty_sentiment(self, symbol: str) -> Dict:
        """空情绪数据"""
        return {
            "symbol": symbol,
            "sentiment_score": 0.0,
            "tweet_volume": 0,
            "trending_hashtags": [],
            "source": "twitter",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def fetch_all_news(self) -> Dict[str, List[Dict]]:
        """
        获取所有订阅标的的新闻
        
        Returns:
            {
                "BTC": [...],
                "AAPL": [...],
                ...
            }
        """
        results = {}
        
        for symbol in self.subscriptions.keys():
            # NewsAPI
            newsapi_articles = await self.fetch_newsapi(query=symbol)
            
            # Twitter情绪
            twitter_sentiment = await self.fetch_twitter_sentiment(symbol)
            
            # 中文新闻
            cn_news = await self.fetch_cn_financial_news(symbol)
            
            results[symbol] = {
                "articles": newsapi_articles,
                "twitter_sentiment": twitter_sentiment,
                "cn_news": cn_news,
            }
        
        return results


# === 数据格式转换 ===

def convert_news_to_standard(source: str, data: Dict) -> Dict:
    """将新闻数据转换为标准格式"""
    return {
        "symbol": data.get("symbol", "NEWS"),
        "market": MarketType.NEWS.value,
        "timestamp": data.get("timestamp", datetime.utcnow().isoformat()),
        "data_type": DataType.NEWS.value,
        "payload": {
            "title": data.get("title", ""),
            "content": data.get("content", ""),
            "source": data.get("source", ""),
            "sentiment": data.get("sentiment"),
            "url": data.get("url", ""),
        },
    }


# === 便捷函数 ===

async def fetch_market_news(symbols: List[str] = None) -> Dict:
    """快速获取市场新闻"""
    connector = NewsConnector()
    try:
        if symbols:
            connector.subscriptions = {s: [s] for s in symbols}
        return await connector.fetch_all_news()
    finally:
        await connector.disconnect()
