"""
Agent 1: MarketHarvester
多市场数据采集器 - 币安实时数据 + 新闻采集
"""
import asyncio
import logging
from typing import Dict, List

from core.connectors.binance import (
    BinanceConnector, 
    convert_kline_to_standard,
    convert_trade_to_standard,
    convert_orderbook_to_standard,
)
from core.connectors.news import NewsConnector, convert_news_to_standard
from core.kafka import MessageBus
from core.models import MarketData, MarketType, DataType
from core.utils import generate_msg_id, generate_timestamp, setup_logging
from core.config import settings

logger = setup_logging("agent1_harvester")


class MarketHarvester:
    """
    Agent 1: 市场数据采集器
    
    职责：
    - BTC数据接入（Binance WebSocket实时）
    - 港股数据接入（老虎证券 - 待实现）
    - 美股数据接入（老虎证券 - 待实现）
    - 新闻数据采集（NewsAPI, Twitter, 财联社）
    - 数据校验和格式化
    """
    
    def __init__(self):
        self.agent_name = "agent1_harvester"
        self.bus = MessageBus(self.agent_name)
        self.running = False
        
        # 订阅的市场配置
        self.subscriptions = {
            MarketType.BTC: {
                "symbols": ["BTCUSDT", "ETHUSDT"],  # 币安交易对
                "intervals": ["1m", "5m", "15m"],
            },
            MarketType.HK_STOCK: {
                "symbols": [],  # 待配置
            },
            MarketType.US_STOCK: {
                "symbols": [],  # 待配置
            },
            MarketType.NEWS: {
                "symbols": ["BTC", "ETH", "AAPL", "NVDA", "00700", "09988"],
                "fetch_interval": 300,  # 每5分钟获取一次新闻
            }
        }
        
        # 连接器
        self.binance: BinanceConnector = None
        self.news: NewsConnector = None
        
        logger.info(f"{self.agent_name} initialized")
    
    async def start(self):
        """启动采集器"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 启动币安连接器
        await self._start_binance()
        
        # 启动新闻采集器
        await self._start_news_collector()
        
        # 发布状态
        self.bus.publish_status({
            "state": "running",
            "markets": [m.value for m in self.subscriptions.keys()],
            "symbols": {
                "btc": self.subscriptions[MarketType.BTC]["symbols"],
                "news": self.subscriptions[MarketType.NEWS]["symbols"],
            },
        })
        self.bus.flush()
        
        try:
            while self.running:
                await asyncio.sleep(10)
                # 定期健康检查
                await self._health_check()
        except asyncio.CancelledError:
            logger.info(f"{self.agent_name} cancelled")
        finally:
            await self.stop()
    
    async def stop(self):
        """停止采集器"""
        logger.info(f"{self.agent_name} stopping...")
        self.running = False
        
        # 断开币安
        if self.binance:
            await self.binance.disconnect()
        
        # 断开新闻
        if self.news:
            await self.news.disconnect()
        
        # 发布状态
        self.bus.publish_status({"state": "stopped"})
        self.bus.flush()
        self.bus.close()
        
        logger.info(f"{self.agent_name} stopped")
    
    async def _start_binance(self):
        """启动币安连接"""
        logger.info("Starting Binance connector...")
        
        self.binance = BinanceConnector(
            api_key=settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_SECRET,
            testnet=settings.BINANCE_TESTNET,
        )
        
        await self.binance.connect()
        
        # 订阅BTC数据
        btc_config = self.subscriptions[MarketType.BTC]
        
        for symbol in btc_config["symbols"]:
            # 订阅K线
            for interval in btc_config["intervals"]:
                await self.binance.subscribe_kline(
                    symbol, interval, self._on_binance_kline
                )
            
            # 订阅逐笔成交
            await self.binance.subscribe_trade(symbol, self._on_binance_trade)
            
            # 订阅订单簿
            await self.binance.subscribe_orderbook(symbol, 5, self._on_binance_orderbook)
            
            logger.info(f"Subscribed all streams for {symbol}")
        
        logger.info("Binance connector started successfully")
    
    async def _start_news_collector(self):
        """启动新闻采集循环"""
        logger.info("Starting news collector...")
        
        self.news = NewsConnector()
        await self.news.connect()
        
        # 启动新闻采集任务
        news_config = self.subscriptions[MarketType.NEWS]
        fetch_interval = news_config.get("fetch_interval", 300)
        
        asyncio.create_task(self._news_collection_loop(fetch_interval))
        
        logger.info(f"News collector started (interval: {fetch_interval}s)")
    
    async def _news_collection_loop(self, interval: int):
        """
        新闻采集循环
        
        Args:
            interval: 采集间隔（秒）
        """
        while self.running:
            try:
                logger.info("Fetching news data...")
                
                # 获取所有订阅标的的新闻
                news_data = await self.news.fetch_all_news()
                
                # 发布新闻到Kafka
                for symbol, data in news_data.items():
                    # 发布文章
                    for article in data.get("articles", []):
                        await self._publish_news(article)
                    
                    # 发布Twitter情绪
                    twitter_sentiment = data.get("twitter_sentiment", {})
                    if twitter_sentiment:
                        await self._publish_sentiment(twitter_sentiment)
                    
                    # 发布中文新闻
                    for cn_news in data.get("cn_news", []):
                        await self._publish_news(cn_news)
                
                logger.info(f"News collection complete: {len(news_data)} symbols")
                
            except Exception as e:
                logger.error(f"News collection error: {e}", exc_info=True)
            
            # 等待下一次采集
            await asyncio.sleep(interval)
    
    async def _publish_news(self, news_item: Dict):
        """发布新闻到Kafka"""
        try:
            standard_data = convert_news_to_standard("news", news_item)
            
            # 发布到新闻topic
            self.bus.send(
                topic="am-hk-raw-market-data",
                key=news_item.get("symbol", "NEWS"),
                value=standard_data
            )
            
            logger.debug(f"Published news: {news_item.get('title', '')[:50]}...")
        
        except Exception as e:
            logger.error(f"Error publishing news: {e}")
    
    async def _publish_sentiment(self, sentiment_data: Dict):
        """发布情绪数据到Kafka"""
        try:
            # 构造情绪数据
            sentiment_msg = {
                "symbol": sentiment_data.get("symbol", "MARKET"),
                "market": MarketType.NEWS.value,
                "timestamp": sentiment_data.get("timestamp", generate_timestamp().isoformat()),
                "data_type": "sentiment",
                "payload": {
                    "sentiment_score": sentiment_data.get("sentiment_score", 0),
                    "tweet_volume": sentiment_data.get("tweet_volume", 0),
                    "trending_hashtags": sentiment_data.get("trending_hashtags", []),
                    "source": sentiment_data.get("source", "unknown"),
                }
            }
            
            self.bus.send(
                topic="am-hk-raw-market-data",
                key=sentiment_data.get("symbol", "SENTIMENT"),
                value=sentiment_msg
            )
            
            logger.debug(f"Published sentiment for {sentiment_data.get('symbol')}: "
                        f"score={sentiment_data.get('sentiment_score', 0):.2f}")
        
        except Exception as e:
            logger.error(f"Error publishing sentiment: {e}")
    
    async def _on_binance_kline(self, stream: str, data: Dict):
        """币安K线回调"""
        try:
            # 提取symbol
            parts = stream.split("@")
            symbol = parts[0].upper()
            
            # 转换为标准格式
            standard_data = convert_kline_to_standard(symbol, data)
            
            # 发布到Kafka
            self.bus.publish_market_data(symbol, standard_data)
            
            # 检查K线是否闭合
            if standard_data["payload"].get("is_closed"):
                logger.debug(f"Kline closed: {symbol} {standard_data['payload']['interval']}")
        
        except Exception as e:
            logger.error(f"Error processing kline: {e}", exc_info=True)
    
    async def _on_binance_trade(self, stream: str, data: Dict):
        """币安成交回调"""
        try:
            parts = stream.split("@")
            symbol = parts[0].upper()
            
            standard_data = convert_trade_to_standard(symbol, data)
            self.bus.publish_market_data(symbol, standard_data)
        
        except Exception as e:
            logger.error(f"Error processing trade: {e}", exc_info=True)
    
    async def _on_binance_orderbook(self, stream: str, data: Dict):
        """币安订单簿回调"""
        try:
            parts = stream.split("@")
            symbol = parts[0].upper()
            
            standard_data = convert_orderbook_to_standard(symbol, data)
            self.bus.publish_market_data(symbol, standard_data)
        
        except Exception as e:
            logger.error(f"Error processing orderbook: {e}", exc_info=True)
    
    async def _health_check(self):
        """健康检查"""
        try:
            if self.binance:
                is_healthy = await self.binance.health_check()
                if not is_healthy:
                    logger.warning("Binance health check failed")
            
            if self.news:
                # 新闻连接器没有健康检查，只检查是否运行
                if not self.running:
                    logger.warning("News collector not running")
        
        except Exception as e:
            logger.error(f"Health check error: {e}")


if __name__ == "__main__":
    harvester = MarketHarvester()
    asyncio.run(harvester.start())
