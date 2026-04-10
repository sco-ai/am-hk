"""
币安 WebSocket 连接器 - 实时数据流
用于获取实时成交、订单簿等数据
"""
import asyncio
import json
import logging
from typing import Callable, Dict, Optional
from datetime import datetime

import websockets
from websockets.exceptions import ConnectionClosed

from core.config import settings
from core.utils import setup_logging

logger = setup_logging("binance_ws_connector")


class BinanceWebSocketConnector:
    """
    币安 WebSocket 连接器
    
    提供实时数据流：
    - 逐笔成交 (trade)
    - 订单簿 (depth)
    - K线 (kline)
    - Ticker (ticker)
    """
    
    WS_BASE = "wss://stream.binance.com:9443/ws"
    
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = None):
        self.api_key = api_key or settings.BINANCE_API_KEY
        self.api_secret = api_secret or settings.BINANCE_SECRET
        self.running = False
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.reconnect_interval = 5  # 重连间隔(秒)
        
        # 订阅配置
        self.subscriptions = {}
        self.callbacks: Dict[str, Callable] = {}
        
        # 连接状态
        self.connected = False
        self.last_ping = 0
        
    async def connect(self):
        """建立 WebSocket 连接"""
        try:
            logger.info("Connecting to Binance WebSocket...")
            
            # 构建订阅流
            streams = self._build_streams()
            if not streams:
                logger.warning("No streams to subscribe")
                return
            
            uri = f"{self.WS_BASE}/{streams}"
            self.ws = await websockets.connect(uri)
            self.connected = True
            self.running = True
            
            logger.info(f"Binance WebSocket connected, subscribed: {list(self.subscriptions.keys())}")
            
            # 启动消息处理循环
            asyncio.create_task(self._message_loop())
            
        except Exception as e:
            logger.error(f"Failed to connect Binance WebSocket: {e}")
            self.connected = False
    
    def _build_streams(self) -> str:
        """构建订阅流字符串"""
        streams = []
        for symbol in self.subscriptions:
            symbol_lower = symbol.lower()
            config = self.subscriptions[symbol]
            
            if config.get("trade"):
                streams.append(f"{symbol_lower}@trade")
            if config.get("orderbook"):
                level = config.get("orderbook_level", 5)
                streams.append(f"{symbol_lower}@depth{level}")
            if config.get("kline"):
                for interval in config.get("kline_intervals", ["1m"]):
                    streams.append(f"{symbol_lower}@kline_{interval}")
            if config.get("ticker"):
                streams.append(f"{symbol_lower}@ticker")
        
        return "/".join(streams) if streams else ""
    
    async def disconnect(self):
        """断开 WebSocket 连接"""
        self.running = False
        self.connected = False
        if self.ws:
            await self.ws.close()
            logger.info("Binance WebSocket disconnected")
    
    async def subscribe_trade(self, symbol: str, callback: Callable):
        """订阅成交数据"""
        if symbol not in self.subscriptions:
            self.subscriptions[symbol] = {}
        self.subscriptions[symbol]["trade"] = True
        self.callbacks[f"{symbol.lower()}@trade"] = callback
        logger.info(f"Subscribed trade stream: {symbol}")
    
    async def subscribe_orderbook(self, symbol: str, level: int, callback: Callable):
        """订阅订单簿"""
        if symbol not in self.subscriptions:
            self.subscriptions[symbol] = {}
        self.subscriptions[symbol]["orderbook"] = True
        self.subscriptions[symbol]["orderbook_level"] = level
        self.callbacks[f"{symbol.lower()}@depth{level}"] = callback
        logger.info(f"Subscribed orderbook stream: {symbol} level={level}")
    
    async def subscribe_kline(self, symbol: str, interval: str, callback: Callable):
        """订阅K线"""
        if symbol not in self.subscriptions:
            self.subscriptions[symbol] = {}
        if "kline" not in self.subscriptions[symbol]:
            self.subscriptions[symbol]["kline"] = True
            self.subscriptions[symbol]["kline_intervals"] = []
        self.subscriptions[symbol]["kline_intervals"].append(interval)
        self.callbacks[f"{symbol.lower()}@kline_{interval}"] = callback
        logger.info(f"Subscribed kline stream: {symbol} {interval}")
    
    async def _message_loop(self):
        """消息处理循环"""
        while self.running and self.connected:
            try:
                message = await asyncio.wait_for(self.ws.recv(), timeout=30)
                await self._handle_message(message)
            except asyncio.TimeoutError:
                # 发送 ping 保持连接
                try:
                    await self.ws.ping()
                except:
                    logger.warning("WebSocket ping failed, reconnecting...")
                    await self._reconnect()
            except ConnectionClosed:
                logger.warning("WebSocket connection closed, reconnecting...")
                await self._reconnect()
            except Exception as e:
                logger.error(f"Message loop error: {e}")
                await asyncio.sleep(1)
    
    async def _handle_message(self, message: str):
        """处理收到的消息"""
        try:
            data = json.loads(message)
            
            # 获取流名称
            stream = data.get("stream", "")
            payload = data.get("data", data)
            
            # 调用对应的回调
            callback = self.callbacks.get(stream)
            if callback:
                await callback(stream, payload)
            else:
                # 尝试从 payload 中解析
                event_type = payload.get("e", "")
                if event_type:
                    # 动态匹配回调
                    for key, cb in self.callbacks.items():
                        if event_type in key or key in stream:
                            await cb(stream, payload)
                            break
                            
        except json.JSONDecodeError:
            logger.error(f"Failed to parse message: {message[:100]}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _reconnect(self):
        """重新连接"""
        self.connected = False
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
        
        logger.info(f"Reconnecting in {self.reconnect_interval}s...")
        await asyncio.sleep(self.reconnect_interval)
        
        try:
            await self.connect()
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            # 指数退避
            self.reconnect_interval = min(self.reconnect_interval * 2, 60)
    
    async def health_check(self) -> bool:
        """健康检查"""
        return self.connected and self.ws and self.ws.open


# 数据转换函数
def convert_ws_trade_to_standard(symbol: str, data: dict) -> dict:
    """将 WebSocket 成交数据转换为标准格式"""
    return {
        "symbol": symbol,
        "market": "CRYPTO",
        "timestamp": data.get("T", int(datetime.now().timestamp() * 1000)),
        "data_type": "trade",
        "payload": {
            "price": float(data.get("p", 0)),
            "amount": float(data.get("q", 0)),
            "side": "buy" if data.get("m") == False else "sell",
            "trade_id": str(data.get("t", "")),
        }
    }


def convert_ws_orderbook_to_standard(symbol: str, data: dict) -> dict:
    """将 WebSocket 订单簿数据转换为标准格式"""
    bids = [[float(b[0]), float(b[1])] for b in data.get("b", [])]
    asks = [[float(a[0]), float(a[1])] for a in data.get("a", [])]
    
    return {
        "symbol": symbol,
        "market": "CRYPTO",
        "timestamp": data.get("E", int(datetime.now().timestamp() * 1000)),
        "data_type": "orderbook",
        "payload": {
            "bids": bids,
            "asks": asks,
            "best_bid": bids[0] if bids else [0, 0],
            "best_ask": asks[0] if asks else [0, 0],
        }
    }
