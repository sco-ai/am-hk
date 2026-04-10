"""
币安 REST API 轮询模式 - 代理兼容版本
用于替代 WebSocket，支持 HTTP 代理
"""
import asyncio
import aiohttp
import logging
from typing import Callable, Dict, List, Optional
from datetime import datetime

from core.config import settings
from core.utils import setup_logging
from core.models import MarketType, DataType

logger = setup_logging("binance_rest_connector")


class BinanceRESTConnector:
    """
    币安 REST API 连接器
    
    使用轮询方式获取数据，完全兼容 HTTP 代理
    """
    
    API_BASE = "https://api.binance.com"
    
    def __init__(self, api_key: str = None, api_secret: str = None, proxy: str = None, testnet: bool = None):
        self.api_key = api_key or settings.BINANCE_API_KEY
        self.api_secret = api_secret or settings.BINANCE_SECRET
        self.proxy = proxy or settings.HTTP_PROXY
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        
        # 订阅配置
        self.subscriptions = {
            "kline": {},
            "trade": {},
            "orderbook": {},
            "ticker": {},
            "funding_rate": {},
            "open_interest": {},
            "long_short_ratio": {}
        }
        
        # 回调函数
        self.callbacks = {
            "kline": {},
            "trade": {},
            "orderbook": {},
            "ticker": {},
            "funding_rate": {},
            "open_interest": {},
            "long_short_ratio": {}
        }
        
        # 合约API基础地址
        self.FAPI_BASE = "https://fapi.binance.com"
        
        logger.info(f"BinanceRESTConnector initialized (proxy={self.proxy is not None})")
    
    async def connect(self):
        """建立连接"""
        connector = aiohttp.TCPConnector(limit=100)
        
        if self.proxy:
            self.session = aiohttp.ClientSession(
                connector=connector,
                trust_env=True,
            )
            logger.info(f"Using proxy: {self.proxy}")
        else:
            self.session = aiohttp.ClientSession(connector=connector)
        
        self.running = True
        logger.info("Binance REST connector connected")
    
    async def disconnect(self):
        """断开连接"""
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("Binance REST connector disconnected")
    
    async def _get(self, endpoint: str, params: dict = None) -> dict:
        """发送 GET 请求"""
        url = f"{self.API_BASE}{endpoint}"
        async with self.session.get(url, params=params, proxy=self.proxy) as resp:
            return await resp.json()
    
    async def subscribe_kline(self, symbol: str, interval: str, callback: Callable):
        """订阅K线数据（轮询模式）"""
        key = f"{symbol}_{interval}"
        self.subscriptions["kline"][key] = {
            "symbol": symbol,
            "interval": interval,
            "last_time": 0
        }
        self.callbacks["kline"][key] = callback
        logger.info(f"Subscribed kline: {symbol} {interval}")
    
    async def subscribe_trade(self, symbol: str, callback: Callable):
        """订阅成交数据（轮询模式）"""
        self.subscriptions["trade"][symbol] = {"last_id": 0}
        self.callbacks["trade"][symbol] = callback
        logger.info(f"Subscribed trade: {symbol}")
    
    async def subscribe_orderbook(self, symbol: str, level: int, callback: Callable):
        """订阅订单簿（轮询模式）"""
        self.subscriptions["orderbook"][symbol] = {"level": level}
        self.callbacks["orderbook"][symbol] = callback
        logger.info(f"Subscribed orderbook: {symbol} level={level}")
    
    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """订阅Ticker（轮询模式）"""
        self.subscriptions["ticker"][symbol] = {}
        self.callbacks["ticker"][symbol] = callback
        logger.info(f"Subscribed ticker: {symbol}")
    
    async def subscribe_funding_rate(self, symbol: str, callback: Callable):
        """订阅资金费率（轮询模式）"""
        self.subscriptions["funding_rate"][symbol] = {"last_fetch": 0}
        self.callbacks["funding_rate"][symbol] = callback
        logger.info(f"Subscribed funding rate: {symbol}")
    
    async def subscribe_open_interest(self, symbol: str, callback: Callable):
        """订阅持仓量（轮询模式）"""
        self.subscriptions["open_interest"][symbol] = {"last_fetch": 0}
        self.callbacks["open_interest"][symbol] = callback
        logger.info(f"Subscribed open interest: {symbol}")
    
    async def subscribe_long_short_ratio(self, symbol: str, callback: Callable):
        """订阅多空比（轮询模式）"""
        self.subscriptions["long_short_ratio"][symbol] = {"last_fetch": 0}
        self.callbacks["long_short_ratio"][symbol] = callback
        logger.info(f"Subscribed long/short ratio: {symbol}")
    
    async def start_polling(self):
        """开始轮询数据"""
        logger.info("Starting REST API polling...")
        
        while self.running:
            try:
                # 轮询K线数据
                await self._poll_klines()
                
                # 轮询成交数据
                await self._poll_trades()
                
                # 轮询订单簿
                await self._poll_orderbooks()
                
                # 轮询Ticker
                await self._poll_tickers()
                
                # 等待下次轮询
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(5)
    
    async def start_funding_polling(self, interval: int = 300):
        """
        开始资金数据轮询（每5分钟一次）
        
        Args:
            interval: 轮询间隔（秒），默认300秒（5分钟）
        """
        logger.info(f"Starting funding data polling (interval: {interval}s)...")
        
        while self.running:
            try:
                # 轮询资金费率
                await self._poll_funding_rates()
                
                # 轮询持仓量
                await self._poll_open_interest()
                
                # 轮询多空比
                await self._poll_long_short_ratio()
                
                logger.info(f"Funding data collection complete, sleeping {interval}s...")
                
            except Exception as e:
                logger.error(f"Funding polling error: {e}")
            
            # 等待下次轮询
            await asyncio.sleep(interval)
    
    async def _poll_klines(self):
        """轮询K线数据"""
        for key, config in self.subscriptions["kline"].items():
            try:
                symbol = config["symbol"]
                interval = config["interval"]
                
                data = await self._get("/api/v3/klines", {
                    "symbol": symbol,
                    "interval": interval,
                    "limit": 2
                })
                
                if data and len(data) > 0:
                    # 获取最新K线
                    kline = data[-1]
                    kline_data = {
                        "e": "kline",
                        "E": int(datetime.now().timestamp() * 1000),
                        "s": symbol,
                        "k": {
                            "t": kline[0],
                            "T": kline[6],
                            "s": symbol,
                            "i": interval,
                            "o": kline[1],
                            "h": kline[2],
                            "l": kline[3],
                            "c": kline[4],
                            "v": kline[5],
                            "x": True,  # 是否闭合
                        }
                    }
                    
                    callback = self.callbacks["kline"][key]
                    await callback(f"{symbol.lower()}@kline_{interval}", kline_data)
                    
            except Exception as e:
                logger.error(f"Error polling kline {key}: {e}")
    
    async def _poll_orderbooks(self):
        """轮询订单簿"""
        for symbol, config in self.subscriptions["orderbook"].items():
            try:
                level = config.get("level", 5)
                limit = min(level * 2, 100)
                
                data = await self._get("/api/v3/depth", {
                    "symbol": symbol,
                    "limit": limit
                })
                
                if data:
                    orderbook_data = {
                        "e": "depthUpdate",
                        "E": int(datetime.now().timestamp() * 1000),
                        "s": symbol,
                        "b": data.get("bids", [])[:level],
                        "a": data.get("asks", [])[:level],
                    }
                    
                    callback = self.callbacks["orderbook"][symbol]
                    await callback(f"{symbol.lower()}@depth{level}", orderbook_data)
                    
            except Exception as e:
                logger.error(f"Error polling orderbook {symbol}: {e}")
    
    async def _poll_tickers(self):
        """轮询Ticker"""
        for symbol, config in self.subscriptions["ticker"].items():
            try:
                data = await self._get("/api/v3/ticker/24hr", {
                    "symbol": symbol
                })
                
                if data:
                    ticker_data = {
                        "e": "24hrTicker",
                        "E": int(datetime.now().timestamp() * 1000),
                        "s": data.get("symbol"),
                        "c": data.get("lastPrice"),
                        "o": data.get("openPrice"),
                        "h": data.get("highPrice"),
                        "l": data.get("lowPrice"),
                        "v": data.get("volume"),
                        "q": data.get("quoteVolume"),
                        "P": data.get("priceChangePercent"),
                    }
                    
                    callback = self.callbacks["ticker"][symbol]
                    await callback(f"{symbol.lower()}@ticker", ticker_data)
                    
            except Exception as e:
                logger.error(f"Error polling ticker {symbol}: {e}")
    
    async def _poll_trades(self):
        """轮询成交数据"""
        for symbol, config in self.subscriptions["trade"].items():
            try:
                last_id = config.get("last_id", 0)
                
                # 获取最近成交
                data = await self._get("/api/v3/trades", {
                    "symbol": symbol,
                    "limit": 20
                })
                
                if data and len(data) > 0:
                    callback = self.callbacks["trade"][symbol]
                    
                    for trade in data:
                        trade_id = trade.get("id", 0)
                        # 只处理新的成交
                        if trade_id > last_id:
                            trade_data = {
                                "e": "trade",
                                "E": trade.get("time", int(datetime.now().timestamp() * 1000)),
                                "s": symbol,
                                "t": trade_id,
                                "p": trade.get("price"),
                                "q": trade.get("qty"),
                                "m": trade.get("isBuyerMaker", False),
                            }
                            await callback(f"{symbol.lower()}@trade", trade_data)
                    
                    # 更新最后ID
                    self.subscriptions["trade"][symbol]["last_id"] = max(
                        t.get("id", 0) for t in data
                    )
                    
            except Exception as e:
                logger.error(f"Error polling trades {symbol}: {e}")
    
    async def _poll_funding_rates(self):
        """轮询资金费率"""
        for symbol, config in list(self.subscriptions["funding_rate"].items()):
            try:
                # 使用合约API获取资金费率
                data = await self._get_fapi("/fapi/v1/fundingRate", {
                    "symbol": symbol,
                    "limit": 1
                })
                
                if data and len(data) > 0:
                    funding_data = {
                        "e": "fundingRate",
                        "E": int(datetime.now().timestamp() * 1000),
                        "s": symbol,
                        "r": data[0].get("fundingRate"),
                        "T": data[0].get("fundingTime"),
                    }
                    
                    callback = self.callbacks["funding_rate"][symbol]
                    await callback(f"{symbol.lower()}@fundingRate", funding_data)
                    logger.debug(f"Funding rate polled for {symbol}: {data[0].get('fundingRate')}")
                    
            except Exception as e:
                logger.error(f"Error polling funding rate {symbol}: {e}")
    
    async def _poll_open_interest(self):
        """轮询持仓量"""
        for symbol, config in list(self.subscriptions["open_interest"].items()):
            try:
                # 使用合约API获取持仓量
                data = await self._get_fapi("/fapi/v1/openInterest", {
                    "symbol": symbol
                })
                
                if data:
                    oi_data = {
                        "e": "openInterest",
                        "E": int(datetime.now().timestamp() * 1000),
                        "s": symbol,
                        "o": data.get("openInterest"),
                        "p": data.get("quoteVolume"),
                    }
                    
                    callback = self.callbacks["open_interest"][symbol]
                    await callback(f"{symbol.lower()}@openInterest", oi_data)
                    logger.debug(f"Open interest polled for {symbol}: {data.get('openInterest')}")
                    
            except Exception as e:
                logger.error(f"Error polling open interest {symbol}: {e}")
    
    async def _poll_long_short_ratio(self):
        """轮询多空比"""
        for symbol, config in list(self.subscriptions["long_short_ratio"].items()):
            try:
                # 使用合约API获取多空比（大户账户）
                data = await self._get_fapi("/fapi/v1/topLongShortAccountRatio", {
                    "symbol": symbol,
                    "period": "5m",
                    "limit": 1
                })
                
                if data and len(data) > 0:
                    ratio_data = {
                        "e": "longShortRatio",
                        "E": int(datetime.now().timestamp() * 1000),
                        "s": symbol,
                        "l": data[0].get("longAccount"),
                        "srt": data[0].get("shortAccount"),
                        "r": data[0].get("longShortRatio"),
                    }
                    
                    callback = self.callbacks["long_short_ratio"][symbol]
                    await callback(f"{symbol.lower()}@longShortRatio", ratio_data)
                    logger.debug(f"Long/Short ratio polled for {symbol}: {data[0].get('longShortRatio')}")
                    
            except Exception as e:
                logger.error(f"Error polling long/short ratio {symbol}: {e}")
    
    async def _get_fapi(self, endpoint: str, params: dict = None) -> dict:
        """发送合约API GET请求"""
        url = f"{self.FAPI_BASE}{endpoint}"
        async with self.session.get(url, params=params, proxy=self.proxy) as resp:
            return await resp.json()
    
    async def get_ticker(self, symbol: str) -> dict:
        """获取24小时ticker"""
        return await self._get("/api/v3/ticker/24hr", {"symbol": symbol})
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            await self._get("/api/v3/ping")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# 转换函数
def convert_kline_to_standard(symbol: str, data: dict) -> dict:
    """将币安K线数据转换为标准格式"""
    k = data.get("k", {})
    return {
        "symbol": symbol,
        "market": MarketType.CRYPTO.value,
        "timestamp": k.get("t", int(datetime.now().timestamp() * 1000)),
        "data_type": "kline",
        "payload": {
            "interval": k.get("i", "1m"),
            "open": float(k.get("o", 0)),
            "high": float(k.get("h", 0)),
            "low": float(k.get("l", 0)),
            "close": float(k.get("c", 0)),
            "volume": float(k.get("v", 0)),
            "is_closed": k.get("x", True),
        }
    }


def convert_trade_to_standard(symbol: str, data: dict) -> dict:
    """将币安成交数据转换为标准格式"""
    return {
        "symbol": symbol,
        "market": MarketType.CRYPTO.value,
        "timestamp": data.get("T", int(datetime.now().timestamp() * 1000)),
        "data_type": "trade",
        "payload": {
            "price": float(data.get("p", 0)),
            "amount": float(data.get("q", 0)),
            "side": "buy" if data.get("m") == False else "sell",
            "trade_id": str(data.get("t", "")),
        }
    }


def convert_orderbook_to_standard(symbol: str, data: dict) -> dict:
    """将币安订单簿数据转换为标准格式"""
    bids = [[float(b[0]), float(b[1])] for b in data.get("b", [])]
    asks = [[float(a[0]), float(a[1])] for a in data.get("a", [])]

    return {
        "symbol": symbol,
        "market": MarketType.CRYPTO.value,
        "timestamp": data.get("E", int(datetime.now().timestamp() * 1000)),
        "data_type": "orderbook",
        "payload": {
            "bids": bids,
            "asks": asks,
            "best_bid": bids[0] if bids else [0, 0],
            "best_ask": asks[0] if asks else [0, 0],
        }
    }


def convert_funding_rate_to_standard(symbol: str, data: dict) -> dict:
    """将币安资金费率数据转换为标准格式"""
    return {
        "symbol": symbol,
        "market": MarketType.CRYPTO.value,
        "timestamp": data.get("T", int(datetime.now().timestamp() * 1000)),
        "data_type": "funding_rate",
        "payload": {
            "funding_rate": float(data.get("r", 0)),
            "funding_time": data.get("T"),
            "collection_time": int(datetime.now().timestamp() * 1000),
        }
    }


def convert_open_interest_to_standard(symbol: str, data: dict) -> dict:
    """将币安持仓量数据转换为标准格式"""
    return {
        "symbol": symbol,
        "market": MarketType.CRYPTO.value,
        "timestamp": data.get("E", int(datetime.now().timestamp() * 1000)),
        "data_type": "open_interest",
        "payload": {
            "open_interest": float(data.get("o", 0)),
            "quote_volume": float(data.get("p", 0)),
            "collection_time": int(datetime.now().timestamp() * 1000),
        }
    }


def convert_long_short_ratio_to_standard(symbol: str, data: dict) -> dict:
    """将币安多空比数据转换为标准格式"""
    return {
        "symbol": symbol,
        "market": MarketType.CRYPTO.value,
        "timestamp": data.get("E", int(datetime.now().timestamp() * 1000)),
        "data_type": "long_short_ratio",
        "payload": {
            "long_account_ratio": float(data.get("l", 0)),
            "short_account_ratio": float(data.get("srt", 0)),
            "long_short_ratio": float(data.get("r", 1)),
            "collection_time": int(datetime.now().timestamp() * 1000),
        }
    }


# 兼容旧导入
BinanceConnector = BinanceRESTConnector
