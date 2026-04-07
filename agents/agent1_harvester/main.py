"""
Agent 1: MarketHarvester
多市场数据采集器 - 币安实时数据 + 老虎证券(港股/美股) + 新闻采集
"""
import asyncio
import logging
from typing import Dict, List

from core.connectors.binance_rest import (
    BinanceRESTConnector as BinanceConnector,
    convert_kline_to_standard as convert_binance_kline,
    convert_trade_to_standard as convert_binance_trade,
    convert_orderbook_to_standard as convert_binance_orderbook,
    convert_funding_rate_to_standard,
    convert_open_interest_to_standard,
    convert_long_short_ratio_to_standard,
)
from core.connectors.tiger import (
    TigerConnector,
    convert_us_kline_to_standard,
    convert_us_orderbook_to_standard,
    convert_us_premarket_to_standard,
    convert_us_darkpool_to_standard,
    convert_us_etf_flow_to_standard,
    convert_us_option_to_standard,
    convert_us_tick_to_standard,
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
                "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"],  # 币安交易对(5个币种)
                "intervals": ["1m", "5m", "15m"],
            },
            MarketType.HK_STOCK: {
                "symbols": [
                    # 科技巨头
                    "00700",  # 腾讯控股
                    "09988",  # 阿里巴巴
                    "03690",  # 美团
                    "09888",  # 百度
                    "01024",  # 快手
                    # 金融地产
                    "02318",  # 中国平安
                    "03988",  # 中国银行
                    "01299",  # 友邦保险
                    "01109",  # 华润置地
                    "06808",  # 高鑫零售
                    # 消费医药
                    "02020",  # 安踏体育
                    "06690",  # 海尔智家
                    "01093",  # 石药集团
                    "02269",  # 药明生物
                    # 新能源/汽车
                    "01211",  # 比亚迪
                    "09868",  # 小鹏汽车
                    "09618",  # 京东集团
                    "09626",  # 哔哩哔哩
                    # Web3/Crypto概念
                    "00863",  # OSL集团
                    "02211",  # 联想集团
                    # 其他热门
                    "01810",  # 小米集团
                    "00981",  # 中芯国际
                    "02015",  # 理想汽车
                ],  # 50只流动性股票池(核心22只)
                "intervals": ["1m", "5m", "1d"],
                "enable_level2": True,
                "enable_capital_flow": True,
                "poll_interval": 10,
            },
            MarketType.US_STOCK: {
                "symbols": [
                    # 加密链标的
                    "COIN",   # Coinbase
                    "MARA",   # Marathon Digital
                    # 科技核心
                    "NVDA",   # NVIDIA
                    "TSLA",   # Tesla
                    # 指数ETF
                    "QQQ",    # Invesco QQQ
                    "SPY",    # SPDR S&P 500
                ],
                "intervals": ["1m", "5m", "1d"],  # K线周期
                "enable_premarket": True,  # 启用盘前盘后数据
                "enable_level2": True,     # 启用Level2订单簿
                "enable_darkpool": True,   # 启用暗池数据
                "enable_options": True,    # 启用期权数据
                "enable_etf_flow": True,   # 启用ETF资金流
                "poll_interval": 10,       # 轮询间隔(秒)
            },
            MarketType.NEWS: {
                "symbols": ["BTC", "ETH", "AAPL", "NVDA", "00700", "09988", "COIN", "MARA", "TSLA", "QQQ", "SPY"],
                "fetch_interval": 300,  # 每5分钟获取一次新闻
            }
        }
        
        # 连接器
        self.binance: BinanceConnector = None
        self.tiger: TigerConnector = None
        self.news: NewsConnector = None
        
        logger.info(f"{self.agent_name} initialized")
    
    async def start(self):
        """启动采集器"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 启动币安连接器
        await self._start_binance()
        
        # 启动老虎证券连接器(美股/港股)
        await self._start_tiger()
        
        # 启动新闻采集器
        await self._start_news_collector()
        
        # 发布状态
        self.bus.publish_status({
            "state": "running",
            "markets": [m.value for m in self.subscriptions.keys()],
            "symbols": {
                "btc": self.subscriptions[MarketType.BTC]["symbols"],
                "us_stock": self.subscriptions[MarketType.US_STOCK]["symbols"],
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
        
        # 断开老虎证券
        if self.tiger:
            await self.tiger.disconnect()
        
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

            # 订阅资金数据（合约数据）
            await self.binance.subscribe_funding_rate(symbol, self._on_binance_funding_rate)
            await self.binance.subscribe_open_interest(symbol, self._on_binance_open_interest)
            await self.binance.subscribe_long_short_ratio(symbol, self._on_binance_long_short_ratio)

            logger.info(f"Subscribed all streams for {symbol} (including funding data)")
        
        logger.info("Binance connector started successfully")
        
        # 启动REST轮询
        asyncio.create_task(self.binance.start_polling())

        # 启动资金数据轮询（每5分钟一次）
        asyncio.create_task(self.binance.start_funding_polling(interval=300))

        logger.info("Binance funding data polling started (interval: 300s)")
    
    async def _start_tiger(self):
        """启动老虎证券连接器(美股/港股)"""
        logger.info("Starting Tiger connector...")
        
        self.tiger = TigerConnector(
            account=settings.TIGER_ACCOUNT,
            private_key=settings.TIGER_PRIVATE_KEY,
        )
        
        await self.tiger.connect()
        
        # 启动美股数据采集
        us_config = self.subscriptions[MarketType.US_STOCK]
        if us_config["symbols"]:
            asyncio.create_task(self._us_collection_loop())
            logger.info(f"US stock collection started for: {us_config['symbols']}")
        
        # 启动港股数据采集
        hk_config = self.subscriptions[MarketType.HK_STOCK]
        if hk_config["symbols"]:
            asyncio.create_task(self._hk_collection_loop())
            logger.info(f"HK stock collection started for: {hk_config['symbols']}")
        
        logger.info("Tiger connector started successfully")
    
    async def _us_collection_loop(self):
        """
        美股数据采集循环
        采集: K线、订单簿、盘前盘后、暗池、ETF资金流、期权数据
        """
        us_config = self.subscriptions[MarketType.US_STOCK]
        symbols = us_config["symbols"]
        intervals = us_config.get("intervals", ["1m", "5m", "1d"])
        poll_interval = us_config.get("poll_interval", 10)
        
        logger.info(f"Starting US stock collection loop for {len(symbols)} symbols")
        
        while self.running:
            try:
                for symbol in symbols:
                    # 1. 采集K线数据
                    for interval in intervals:
                        try:
                            # 转换间隔格式
                            period_map = {"1m": "min1", "5m": "min5", "1d": "day"}
                            period = period_map.get(interval, "day")
                            
                            klines = await self.tiger.get_klines(symbol, "US", period, limit=1)
                            if klines:
                                for kline in klines:
                                    kline["interval"] = interval
                                    standard_data = convert_us_kline_to_standard(symbol, kline)
                                    self._publish_us_data(symbol, standard_data)
                        except Exception as e:
                            logger.error(f"Error fetching kline for {symbol}: {e}")
                    
                    # 2. 采集Level2订单簿
                    if us_config.get("enable_level2", True):
                        try:
                            orderbook = await self.tiger.get_us_level2_orderbook(symbol, limit=10)
                            standard_data = convert_us_orderbook_to_standard(symbol, orderbook)
                            self._publish_us_data(symbol, standard_data)
                        except Exception as e:
                            logger.error(f"Error fetching orderbook for {symbol}: {e}")
                    
                    # 3. 采集盘前盘后数据
                    if us_config.get("enable_premarket", True):
                        try:
                            premarket = await self.tiger.get_us_premarket_quote(symbol)
                            standard_data = convert_us_premarket_to_standard(symbol, premarket)
                            self._publish_us_data(symbol, standard_data)
                        except Exception as e:
                            logger.error(f"Error fetching premarket for {symbol}: {e}")
                    
                    # 4. 采集暗池数据(仅限股票)
                    if us_config.get("enable_darkpool", True) and symbol not in ["QQQ", "SPY"]:
                        try:
                            darkpool = await self.tiger.get_us_dark_pool_data(symbol)
                            standard_data = convert_us_darkpool_to_standard(symbol, darkpool)
                            self._publish_us_data(symbol, standard_data)
                        except Exception as e:
                            logger.error(f"Error fetching darkpool for {symbol}: {e}")
                    
                    # 5. 采集ETF资金流(仅限ETF)
                    if us_config.get("enable_etf_flow", True) and symbol in ["QQQ", "SPY"]:
                        try:
                            etf_flow = await self.tiger.get_us_etf_flow(symbol)
                            standard_data = convert_us_etf_flow_to_standard(symbol, etf_flow)
                            self._publish_us_data(symbol, standard_data)
                        except Exception as e:
                            logger.error(f"Error fetching ETF flow for {symbol}: {e}")
                    
                    # 6. 采集期权数据
                    if us_config.get("enable_options", True):
                        try:
                            option_data = await self.tiger.get_us_option_data(symbol)
                            standard_data = convert_us_option_to_standard(symbol, option_data)
                            self._publish_us_data(symbol, standard_data)
                        except Exception as e:
                            logger.error(f"Error fetching option data for {symbol}: {e}")
                    
                    # 避免请求过快
                    await asyncio.sleep(0.5)
                
                logger.debug(f"US data collection cycle complete for {len(symbols)} symbols")
                
            except Exception as e:
                logger.error(f"US collection loop error: {e}", exc_info=True)
            
            # 等待下一次采集
            await asyncio.sleep(poll_interval)
    
    async def _hk_collection_loop(self):
        """
        港股数据采集循环
        核心数据: 资金流(北水) + 盘口结构 + 分时
        """
        hk_config = self.subscriptions[MarketType.HK_STOCK]
        symbols = hk_config["symbols"]
        intervals = hk_config.get("intervals", ["1m", "5m", "1d"])
        poll_interval = hk_config.get("poll_interval", 10)
        
        logger.info(f"Starting HK stock collection loop for {len(symbols)} symbols")
        
        while self.running:
            try:
                for symbol in symbols:
                    # 1. 采集K线数据(分时)
                    for interval in intervals:
                        try:
                            period_map = {"1m": "min1", "5m": "min5", "1d": "day"}
                            period = period_map.get(interval, "day")
                            
                            klines = await self.tiger.get_klines(symbol, "HK", period, limit=1)
                            if klines:
                                for kline in klines:
                                    kline["interval"] = interval
                                    standard_data = {
                                        "symbol": symbol,
                                        "market": "HK",
                                        "timestamp": int(asyncio.get_event_loop().time() * 1000),
                                        "data_type": "kline",
                                        "payload": {
                                            "timestamp": kline.get("timestamp"),
                                            "open": kline.get("open"),
                                            "high": kline.get("high"),
                                            "low": kline.get("low"),
                                            "close": kline.get("close"),
                                            "volume": kline.get("volume"),
                                            "interval": interval,
                                        },
                                    }
                                    self._publish_hk_data(symbol, standard_data)
                        except Exception as e:
                            logger.error(f"Error fetching HK kline for {symbol}: {e}")
                    
                    # 2. 采集Level2盘口数据
                    if hk_config.get("enable_level2", True):
                        try:
                            orderbook = await self.tiger.get_orderbook(symbol, "HK", limit=10)
                            standard_data = {
                                "symbol": symbol,
                                "market": "HK",
                                "timestamp": int(asyncio.get_event_loop().time() * 1000),
                                "data_type": "orderbook",
                                "payload": {
                                    "bids": orderbook.get("bids", []),
                                    "asks": orderbook.get("asks", []),
                                    "level": 2,
                                },
                            }
                            self._publish_hk_data(symbol, standard_data)
                        except Exception as e:
                            logger.error(f"Error fetching HK orderbook for {symbol}: {e}")
                    
                    # 3. 采集资金流数据(港股通-北水)
                    if hk_config.get("enable_capital_flow", True):
                        try:
                            capital_flow = await self.tiger.get_hk_capital_flow(symbol)
                            standard_data = {
                                "symbol": symbol,
                                "market": "HK",
                                "timestamp": int(asyncio.get_event_loop().time() * 1000),
                                "data_type": "capital_flow",
                                "payload": {
                                    "northbound_net_inflow": capital_flow.get("northbound_net_inflow"),
                                    "northbound_net_outflow": capital_flow.get("northbound_net_outflow"),
                                    "main_force_inflow": capital_flow.get("main_force_inflow"),
                                    "main_force_outflow": capital_flow.get("main_force_outflow"),
                                    "large_order_net": capital_flow.get("large_order_net"),
                                    "retail_net": capital_flow.get("retail_net"),
                                },
                            }
                            self._publish_hk_data(symbol, standard_data)
                        except Exception as e:
                            logger.error(f"Error fetching HK capital flow for {symbol}: {e}")
                    
                    # 4. 采集交易状态
                    try:
                        quote = await self.tiger.get_quote(symbol, "HK")
                        standard_data = {
                            "symbol": symbol,
                            "market": "HK",
                            "timestamp": int(asyncio.get_event_loop().time() * 1000),
                            "data_type": "status",
                            "payload": {
                                "is_halted": quote.get("is_halted", False),
                                "is_open": quote.get("is_open", True),
                                "auction_phase": quote.get("auction_phase"),
                                "last_price": quote.get("price"),
                                "change": quote.get("change"),
                                "change_percent": quote.get("change_percent"),
                            },
                        }
                        self._publish_hk_data(symbol, standard_data)
                    except Exception as e:
                        logger.error(f"Error fetching HK quote for {symbol}: {e}")
                    
                    await asyncio.sleep(0.5)
                
                logger.debug(f"HK data collection cycle complete for {len(symbols)} symbols")
                
            except Exception as e:
                logger.error(f"HK collection loop error: {e}", exc_info=True)
            
            await asyncio.sleep(poll_interval)
    
    def _publish_hk_data(self, symbol: str, data: Dict):
        """发布港股数据到Kafka"""
        try:
            self.bus.send(
                topic="am-hk-raw-market-data",
                key=symbol,
                value=data
            )
            logger.debug(f"Published HK {data['data_type']} data for {symbol}")
        except Exception as e:
            logger.error(f"Error publishing HK data for {symbol}: {e}")
        """发布美股数据到Kafka"""
        try:
            self.bus.send(
                topic="am-hk-raw-market-data",
                key=symbol,
                value=data
            )
            logger.debug(f"Published US {data['data_type']} data for {symbol}")
        except Exception as e:
            logger.error(f"Error publishing US data for {symbol}: {e}")
    
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
            standard_data = convert_binance_kline(symbol, data)
            
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
            
            standard_data = convert_binance_trade(symbol, data)
            self.bus.publish_market_data(symbol, standard_data)
        
        except Exception as e:
            logger.error(f"Error processing trade: {e}", exc_info=True)
    
    async def _on_binance_orderbook(self, stream: str, data: Dict):
        """币安订单簿回调"""
        try:
            parts = stream.split("@")
            symbol = parts[0].upper()

            standard_data = convert_binance_orderbook(symbol, data)
            self.bus.publish_market_data(symbol, standard_data)

        except Exception as e:
            logger.error(f"Error processing orderbook: {e}", exc_info=True)

    async def _on_binance_funding_rate(self, stream: str, data: Dict):
        """币安资金费率回调"""
        try:
            parts = stream.split("@")
            symbol = parts[0].upper()

            standard_data = convert_funding_rate_to_standard(symbol, data)
            self.bus.publish_market_data(symbol, standard_data)
            logger.debug(f"Published funding rate for {symbol}: {standard_data['payload']['funding_rate']}")

        except Exception as e:
            logger.error(f"Error processing funding rate: {e}", exc_info=True)

    async def _on_binance_open_interest(self, stream: str, data: Dict):
        """币安持仓量回调"""
        try:
            parts = stream.split("@")
            symbol = parts[0].upper()

            standard_data = convert_open_interest_to_standard(symbol, data)
            self.bus.publish_market_data(symbol, standard_data)
            logger.debug(f"Published open interest for {symbol}: {standard_data['payload']['open_interest']}")

        except Exception as e:
            logger.error(f"Error processing open interest: {e}", exc_info=True)

    async def _on_binance_long_short_ratio(self, stream: str, data: Dict):
        """币安多空比回调"""
        try:
            parts = stream.split("@")
            symbol = parts[0].upper()

            standard_data = convert_long_short_ratio_to_standard(symbol, data)
            self.bus.publish_market_data(symbol, standard_data)
            logger.debug(f"Published L/S ratio for {symbol}: {standard_data['payload']['long_short_ratio']}")

        except Exception as e:
            logger.error(f"Error processing long/short ratio: {e}", exc_info=True)

    async def _health_check(self):
        """健康检查"""
        try:
            if self.binance:
                is_healthy = await self.binance.health_check()
                if not is_healthy:
                    logger.warning("Binance health check failed")
            
            # 检查老虎证券连接
            if self.tiger:
                is_healthy = await self.tiger.health_check()
                if not is_healthy:
                    logger.warning("Tiger health check failed")
            
            if self.news:
                # 新闻连接器没有健康检查，只检查是否运行
                if not self.running:
                    logger.warning("News collector not running")
        
        except Exception as e:
            logger.error(f"Health check error: {e}")


if __name__ == "__main__":
    harvester = MarketHarvester()
    asyncio.run(harvester.start())
