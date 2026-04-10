"""
币安数据连接器 - 支持代理
WebSocket实时数据 + REST API历史数据
"""
import asyncio
import hmac
import hashlib
import json
import logging
import os
import time
from typing import Callable, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp
import websockets

from core.models import MarketType, DataType
from core.utils import setup_logging

# 导入REST模式作为默认
from .binance_rest import BinanceRESTConnector

logger = setup_logging("binance_connector")

# 使用REST连接器作为默认
BinanceConnector = BinanceRESTConnector

# 保持向后兼容
__all__ = ['BinanceConnector', 'BinanceRESTConnector']
import asyncio
import hmac
import hashlib
import json
import logging
import os
import time
from typing import Callable, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp
import websockets

from core.models import MarketType, DataType
from core.utils import setup_logging

logger = setup_logging("binance_connector")


class BinanceConnector:
    """
    币安数据连接器
    
    支持：
    - WebSocket实时数据（K线、逐笔成交、订单簿）
    - REST API历史数据
    - 自动重连
    - HTTP/HTTPS代理
    """
    
    WS_BASE = "wss://stream.binance.com:9443/ws"
    WS_STREAM_BASE = "wss://stream.binance.com:9443/stream?streams="
    API_BASE = "https://api.binance.com"
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False, proxy: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.proxy = proxy or os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        
        if testnet:
            self.WS_BASE = "wss://testnet.binance.vision/ws"
            self.API_BASE = "https://testnet.binance.vision"
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.subscriptions: Dict[str, Callable] = {}
        self.funding_callbacks: Dict[str, Callable] = {}  # 资金费率回调
        
        self.running = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 60
        
        logger.info(f"Binance connector initialized (testnet={testnet}, proxy={self.proxy is not None})")
    
    async def connect(self):
        """建立连接（带代理）"""
        # 配置aiohttp使用代理
        if self.proxy:
            connector = aiohttp.TCPConnector()
            self.session = aiohttp.ClientSession(
                connector=connector,
                trust_env=True,  # 使用环境变量中的代理设置
            )
            logger.info(f"Using proxy: {self.proxy}")
        else:
            self.session = aiohttp.ClientSession()
        
        self.running = True
        logger.info("Binance connector connected")
    
    async def disconnect(self):
        """断开连接"""
        self.running = False
        
        # 关闭所有WebSocket
        for symbol, ws in self.ws_connections.items():
            try:
                await ws.close()
                logger.info(f"WebSocket closed: {symbol}")
            except Exception as e:
                logger.error(f"Error closing WebSocket {symbol}: {e}")
        
        if self.session:
            await self.session.close()
        
        logger.info("Binance connector disconnected")
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            data = await self._rest_get("/api/v3/ping")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    # === WebSocket 订阅 ===
    
    async def subscribe_kline(self, symbol: str, interval: str, callback: Callable):
        """
        订阅K线数据
        
        Args:
            symbol: 交易对，如 "BTCUSDT"
            interval: K线周期，如 "1m", "5m", "15m", "1h"
            callback: 回调函数 (symbol, data) -> None
        """
        stream_name = f"{symbol.lower()}@kline_{interval}"
        await self._subscribe_stream(stream_name, callback)
        logger.info(f"Subscribed kline: {symbol} {interval}")
    
    async def subscribe_trade(self, symbol: str, callback: Callable):
        """
        订阅逐笔成交
        
        Args:
            symbol: 交易对
            callback: 回调函数
        """
        stream_name = f"{symbol.lower()}@trade"
        await self._subscribe_stream(stream_name, callback)
        logger.info(f"Subscribed trade: {symbol}")
    
    async def subscribe_orderbook(self, symbol: str, level: int, callback: Callable):
        """
        订阅订单簿
        
        Args:
            symbol: 交易对
            level: 深度，5, 10, 20
            callback: 回调函数
        """
        stream_name = f"{symbol.lower()}@depth{level}"
        await self._subscribe_stream(stream_name, callback)
        logger.info(f"Subscribed orderbook: {symbol} level={level}")
    
    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """
        订阅24小时 ticker
        
        Args:
            symbol: 交易对
            callback: 回调函数
        """
        stream_name = f"{symbol.lower()}@ticker"
        await self._subscribe_stream(stream_name, callback)
        logger.info(f"Subscribed ticker: {symbol}")
    
    async def subscribe_funding_rate(self, symbol: str, callback: Callable):
        """
        订阅资金费率 (通过轮询REST API)
        
        Args:
            symbol: 交易对
            callback: 回调函数
        """
        # 资金费率通过REST API轮询获取，WebSocket没有实时流
        self.funding_callbacks[symbol] = callback
        logger.info(f"Registered funding rate callback for: {symbol}")
    
    async def start_funding_polling(self, interval: int = 300):
        """
        启动资金费率轮询
        
        Args:
            interval: 轮询间隔(秒)，默认300秒(5分钟)
        """
        import asyncio
        from datetime import datetime
        
        logger.info(f"Starting funding rate polling (interval: {interval}s)")
        
        while True:
            try:
                for symbol in list(self.funding_callbacks.keys()):
                    try:
                        funding_data = await self.get_funding_rate(symbol)
                        if funding_data:
                            # 构造与WebSocket一致的回调格式
                            callback_data = {
                                "symbol": symbol,
                                "fundingRate": funding_data.get("fundingRate", "0"),
                                "fundingTime": funding_data.get("fundingTime", 0),
                                "nextFundingTime": funding_data.get("nextFundingTime", 0),
                                "markPrice": funding_data.get("markPrice", "0"),
                                "indexPrice": funding_data.get("indexPrice", "0"),
                                "estimatedSettlePrice": funding_data.get("estimatedSettlePrice", "0"),
                                "interestRate": funding_data.get("interestRate", "0"),
                                "time": funding_data.get("time", int(datetime.now().timestamp() * 1000))
                            }
                            
                            # 调用回调
                            stream_name = f"{symbol.lower()}@markPrice"
                            await self.funding_callbacks[symbol](stream_name, callback_data)
                            logger.debug(f"Polled funding rate for {symbol}: {funding_data.get('fundingRate')}")
                    except Exception as e:
                        logger.error(f"Error polling funding rate for {symbol}: {e}")
                
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Funding polling loop error: {e}")
                await asyncio.sleep(10)  # 出错后短暂等待
    
    async def get_funding_rate(self, symbol: str) -> Dict:
        """
        获取当前资金费率
        
        Args:
            symbol: 交易对
            
        Returns:
            资金费率数据
        """
        return await self._rest_get("/fapi/v1/premiumIndex", {"symbol": symbol})
        """订阅流"""
        self.subscriptions[stream_name] = callback
        
        # 启动WebSocket连接
        asyncio.create_task(self._ws_handler(stream_name, callback))
    
    async def _ws_handler(self, stream_name: str, callback: Callable):
        """WebSocket连接处理器（带自动重连）"""
        while self.running:
            try:
                ws_url = f"{self.WS_BASE}/{stream_name}"
                logger.debug(f"Connecting to {ws_url}")
                
                # WebSocket代理配置
                if self.proxy:
                    # 使用代理连接WebSocket
                    import urllib.parse
                    parsed = urllib.parse.urlparse(self.proxy)
                    proxy_host = parsed.hostname
                    proxy_port = parsed.port or 7890
                    
                    # 通过代理建立WebSocket连接
                    async with websockets.connect(
                        ws_url,
                        proxy=f"http://{proxy_host}:{proxy_port}"
                    ) as ws:
                        self.ws_connections[stream_name] = ws
                        self._reconnect_delay = 1
                        
                        logger.info(f"WebSocket connected via proxy: {stream_name}")
                        
                        async for message in ws:
                            try:
                                data = json.loads(message)
                                await callback(stream_name, data)
                            except Exception as e:
                                logger.error(f"Error processing message: {e}")
                else:
                    async with websockets.connect(ws_url) as ws:
                        self.ws_connections[stream_name] = ws
                        self._reconnect_delay = 1
                        
                        logger.info(f"WebSocket connected: {stream_name}")
                        
                        async for message in ws:
                            try:
                                data = json.loads(message)
                                await callback(stream_name, data)
                            except Exception as e:
                                logger.error(f"Error processing message: {e}")
            
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"WebSocket closed: {stream_name}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            # 自动重连
            if self.running:
                logger.info(f"Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self._max_reconnect_delay
                )
    
    # === REST API ===
    
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict]:
        """
        获取K线数据
        
        Returns:
            [
                {
                    "timestamp": int,
                    "open": float,
                    "high": float,
                    "low": float,
                    "close": float,
                    "volume": float,
                }
            ]
        """
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        data = await self._rest_get("/api/v3/klines", params)
        
        # 解析K线数据
        klines = []
        for item in data:
            klines.append({
                "timestamp": item[0],
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
            })
        
        return klines
    
    async def get_ticker(self, symbol: str) -> Dict:
        """
        获取24小时ticker
        
        Returns:
            {
                "symbol": str,
                "price": float,
                "change": float,
                "change_percent": float,
                "volume": float,
                "high": float,
                "low": float,
            }
        """
        params = {"symbol": symbol.upper()}
        data = await self._rest_get("/api/v3/ticker/24hr", params)
        
        return {
            "symbol": data["symbol"],
            "price": float(data["lastPrice"]),
            "change": float(data["priceChange"]),
            "change_percent": float(data["priceChangePercent"]),
            "volume": float(data["volume"]),
            "high": float(data["highPrice"]),
            "low": float(data["lowPrice"]),
        }
    
    async def get_orderbook(self, symbol: str, limit: int = 100) -> Dict:
        """
        获取订单簿
        
        Returns:
            {
                "bids": [[price, qty], ...],
                "asks": [[price, qty], ...],
            }
        """
        params = {
            "symbol": symbol.upper(),
            "limit": limit,
        }
        data = await self._rest_get("/api/v3/depth", params)
        
        return {
            "bids": [[float(p), float(q)] for p, q in data["bids"]],
            "asks": [[float(p), float(q)] for p, q in data["asks"]],
        }
    
    async def get_account(self) -> Dict:
        """
        获取账户信息（需要签名）
        
        Returns:
            {
                "balances": [
                    {"asset": "BTC", "free": 1.0, "locked": 0.0},
                    ...
                ]
            }
        """
        data = await self._rest_get_signed("/api/v3/account")
        
        balances = []
        for item in data.get("balances", []):
            free = float(item["free"])
            locked = float(item["locked"])
            if free > 0 or locked > 0:
                balances.append({
                    "asset": item["asset"],
                    "free": free,
                    "locked": locked,
                })
        
        return {"balances": balances}
    
    # === 内部方法 ===
    
    async def _rest_get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """发送GET请求（带代理支持）"""
        url = f"{self.API_BASE}{endpoint}"
        
        # 使用代理
        proxy = self.proxy if self.proxy else None
        
        async with self.session.get(url, params=params, proxy=proxy) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"API error: {response.status} - {text}")
            
            return await response.json()
    
    async def _rest_get_signed(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """发送带签名的GET请求（带代理支持）"""
        params = params or {}
        params["timestamp"] = int(time.time() * 1000)
        
        # 生成签名
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        
        url = f"{self.API_BASE}{endpoint}"
        headers = {"X-MBX-APIKEY": self.api_key}
        
        # 使用代理
        proxy = self.proxy if self.proxy else None
        
        async with self.session.get(url, params=params, headers=headers, proxy=proxy) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"API error: {response.status} - {text}")
            
            return await response.json()


# === 数据格式转换 ===

def convert_kline_to_standard(symbol: str, data: Dict) -> Dict:
    """
    将币安K线数据转换为标准格式
    
    Args:
        symbol: 交易对
        data: 币安原始数据
    
    Returns:
        标准格式数据
    """
    k = data.get("k", {})
    
    return {
        "symbol": symbol,
        "market": MarketType.BTC.value,
        "timestamp": data.get("E"),  # 事件时间
        "data_type": DataType.KLINE.value,
        "payload": {
            "open": float(k.get("o", 0)),
            "high": float(k.get("h", 0)),
            "low": float(k.get("l", 0)),
            "close": float(k.get("c", 0)),
            "volume": float(k.get("v", 0)),
            "interval": k.get("i"),
            "is_closed": k.get("x", False),
        },
    }


def convert_trade_to_standard(symbol: str, data: Dict) -> Dict:
    """将币安成交数据转换为标准格式"""
    return {
        "symbol": symbol,
        "market": MarketType.BTC.value,
        "timestamp": data.get("E"),
        "data_type": DataType.TICK.value,
        "payload": {
            "price": float(data.get("p", 0)),
            "quantity": float(data.get("q", 0)),
            "is_buyer_maker": data.get("m", False),
            "trade_id": data.get("t"),
        },
    }


def convert_orderbook_to_standard(symbol: str, data: Dict) -> Dict:
    """将币安订单簿数据转换为标准格式"""
    return {
        "symbol": symbol,
        "market": MarketType.BTC.value,
        "timestamp": data.get("E"),
        "data_type": DataType.ORDERBOOK.value,
        "payload": {
            "bids": [[float(p), float(q)] for p, q in data.get("b", [])],
            "asks": [[float(p), float(q)] for p, q in data.get("a", [])],
        },
    }
