"""
老虎证券数据连接器
港股/美股接入 - 模拟盘/实盘支持
"""
import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional

import httpx
import websockets

from core.config import settings
from core.models import MarketType, DataType
from core.utils import setup_logging

logger = setup_logging("tiger_connector")


class TigerConnector:
    """
    老虎证券数据连接器
    
    支持：
    - 港股/美股实时行情
    - 订单簿数据
    - 交易执行（模拟盘/实盘）
    - WebSocket推送
    
    文档: https://www.itigerup.com/help/faq/133
    """
    
    # API端点
    BASE_URL_PAPER = "https://openapi-sandbox.itigerup.com/gateway"  # 模拟盘
    BASE_URL_LIVE = "https://openapi.itigerup.com/gateway"  # 实盘
    
    WS_URL_PAPER = "wss://openapi-sandbox.itigerup.com/websocket"
    WS_URL_LIVE = "wss://openapi.itigerup.com/websocket"
    
    def __init__(self, account: str = None, private_key: str = None):
        self.account = account or settings.TIGER_ACCOUNT
        self.private_key = private_key or settings.TIGER_PRIVATE_KEY
        self.paper_trading = settings.TIGER_ENABLE_PAPER
        
        # 选择端点
        if self.paper_trading:
            self.base_url = self.BASE_URL_PAPER
            self.ws_url = self.WS_URL_PAPER
            logger.info("Tiger connector initialized [PAPER TRADING]")
        else:
            self.base_url = self.BASE_URL_LIVE
            self.ws_url = self.WS_URL_LIVE
            logger.warning("Tiger connector initialized [LIVE TRADING] - USE WITH CAUTION")
        
        self.http_client: Optional[httpx.AsyncClient] = None
        self.ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        self.subscriptions: Dict[str, Callable] = {}
        self.running = False
    
    async def connect(self):
        """建立连接"""
        self.http_client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
        )
        self.running = True
        logger.info("Tiger HTTP client connected")
    
    async def disconnect(self):
        """断开连接"""
        self.running = False
        
        if self.ws_connection:
            await self.ws_connection.close()
        
        if self.http_client:
            await self.http_client.aclose()
        
        logger.info("Tiger connector disconnected")
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 查询账户信息作为健康检查
            result = await self.get_account()
            return result is not None
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    # === 行情数据 ===
    
    async def get_quote(self, symbol: str, market: str = "US") -> Dict:
        """
        获取实时行情
        
        Args:
            symbol: 股票代码，如 "AAPL", "00700"
            market: 市场 "US"(美股) 或 "HK"(港股)
        
        Returns:
            {
                "symbol": str,
                "market": str,
                "price": float,
                "open": float,
                "high": float,
                "low": float,
                "close": float,
                "volume": int,
                "change": float,
                "change_percent": float,
            }
        """
        endpoint = "/quote" if self.paper_trading else "/quote"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": market,
        }
        
        response = await self._signed_request("GET", endpoint, params)
        data = response.get("data", {})
        
        return {
            "symbol": symbol,
            "market": market,
            "price": float(data.get("latestPrice", 0)),
            "open": float(data.get("open", 0)),
            "high": float(data.get("high", 0)),
            "low": float(data.get("low", 0)),
            "close": float(data.get("preClose", 0)),
            "volume": int(data.get("volume", 0)),
            "change": float(data.get("change", 0)),
            "change_percent": float(data.get("changeRate", 0)),
        }
    
    async def get_quotes(self, symbols: List[str], market: str = "US") -> List[Dict]:
        """批量获取行情"""
        results = []
        for symbol in symbols:
            try:
                quote = await self.get_quote(symbol, market)
                results.append(quote)
            except Exception as e:
                logger.error(f"Failed to get quote for {symbol}: {e}")
        return results
    
    async def get_orderbook(self, symbol: str, market: str = "US", limit: int = 10) -> Dict:
        """
        获取订单簿
        
        Returns:
            {
                "symbol": str,
                "bids": [[price, size], ...],
                "asks": [[price, size], ...],
            }
        """
        endpoint = "/quote/depth"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": market,
            "limit": limit,
        }
        
        response = await self._signed_request("GET", endpoint, params)
        data = response.get("data", {})
        
        bids = [[float(p), int(s)] for p, s in data.get("bids", [])]
        asks = [[float(p), int(s)] for p, s in data.get("asks", [])]
        
        return {
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
        }
    
    async def get_klines(self, symbol: str, market: str = "US", 
                         period: str = "day", limit: int = 100) -> List[Dict]:
        """
        获取K线数据
        
        Args:
            period: 周期 "min1", "min5", "min15", "min30", "min60", "day", "week", "month"
        
        Returns:
            [
                {
                    "timestamp": int,
                    "open": float,
                    "high": float,
                    "low": float,
                    "close": float,
                    "volume": int,
                }
            ]
        """
        endpoint = "/quote/kline"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": market,
            "period": period,
            "limit": limit,
        }
        
        response = await self._signed_request("GET", endpoint, params)
        items = response.get("data", {}).get("items", [])
        
        klines = []
        for item in items:
            klines.append({
                "timestamp": item.get("time"),
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "volume": int(item.get("volume", 0)),
            })
        
        return klines
    
    # === 交易接口 ===
    
    async def place_order(self, symbol: str, market: str, action: str, 
                          quantity: int, order_type: str = "MKT",
                          price: Optional[float] = None) -> Dict:
        """
        下单
        
        Args:
            symbol: 股票代码
            market: "US" 或 "HK"
            action: "BUY" 或 "SELL"
            quantity: 数量
            order_type: "MKT"(市价), "LMT"(限价)
            price: 限价单价格
        
        Returns:
            {
                "order_id": str,
                "status": str,
            }
        """
        endpoint = "/order"
        
        body = {
            "account": self.account,
            "symbol": symbol,
            "market": market,
            "action": action,
            "quantity": quantity,
            "orderType": order_type,
        }
        
        if order_type == "LMT" and price:
            body["price"] = price
        
        logger.info(f"Placing order: {action} {quantity} {symbol} @ {market}")
        
        response = await self._signed_request("POST", endpoint, body=body)
        
        return {
            "order_id": response.get("data", {}).get("orderId"),
            "status": response.get("data", {}).get("status"),
        }
    
    async def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        endpoint = f"/order/{order_id}"
        
        try:
            await self._signed_request("DELETE", endpoint)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def get_orders(self, status: str = "all") -> List[Dict]:
        """查询订单"""
        endpoint = "/orders"
        
        params = {
            "account": self.account,
            "status": status,
        }
        
        response = await self._signed_request("GET", endpoint, params)
        return response.get("data", {}).get("orders", [])
    
    async def get_positions(self) -> List[Dict]:
        """查询持仓"""
        endpoint = "/positions"
        
        params = {"account": self.account}
        
        response = await self._signed_request("GET", endpoint, params)
        items = response.get("data", {}).get("positions", [])
        
        positions = []
        for item in items:
            positions.append({
                "symbol": item.get("symbol"),
                "market": item.get("market"),
                "quantity": int(item.get("quantity", 0)),
                "avg_price": float(item.get("averageCost", 0)),
                "current_price": float(item.get("marketPrice", 0)),
                "pnl": float(item.get("unrealizedPnl", 0)),
            })
        
        return positions
    
    async def get_account(self) -> Dict:
        """查询账户信息"""
        endpoint = "/account"
        
        params = {"account": self.account}
        
        response = await self._signed_request("GET", endpoint, params)
        data = response.get("data", {})
        
        return {
            "account": self.account,
            "currency": data.get("currency"),
            "cash": float(data.get("cash", 0)),
            "net_liquidation": float(data.get("netLiquidation", 0)),
            "buying_power": float(data.get("buyingPower", 0)),
            "equity": float(data.get("equityWithLoanValue", 0)),
        }
    
    # === WebSocket实时行情 ===
    
    async def subscribe_quote(self, symbols: List[str], callback: Callable):
        """订阅实时行情推送"""
        for symbol in symbols:
            self.subscriptions[symbol] = callback
        
        # 启动WebSocket连接
        asyncio.create_task(self._ws_handler())
    
    async def _ws_handler(self):
        """WebSocket连接处理器"""
        while self.running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    self.ws_connection = ws
                    logger.info("Tiger WebSocket connected")
                    
                    # 发送订阅请求
                    subscribe_msg = {
                        "command": "subscribe",
                        "account": self.account,
                        "symbols": list(self.subscriptions.keys()),
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    
                    async for message in ws:
                        await self._handle_ws_message(message)
            
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)
    
    async def _handle_ws_message(self, message: str):
        """处理WebSocket消息"""
        try:
            data = json.loads(message)
            symbol = data.get("symbol")
            
            if symbol and symbol in self.subscriptions:
                callback = self.subscriptions[symbol]
                await callback(data)
        
        except Exception as e:
            logger.error(f"Error handling WS message: {e}")
    
    # === 内部方法 ===
    
    async def _signed_request(self, method: str, endpoint: str, 
                              params: Optional[Dict] = None,
                              body: Optional[Dict] = None) -> Dict:
        """发送带签名的请求"""
        import time
        import hashlib
        import hmac
        
        timestamp = str(int(time.time() * 1000))
        
        # 构建签名字符串
        sign_str = f"{timestamp}{method.upper()}{endpoint}"
        if params:
            sign_str += json.dumps(params, sort_keys=True)
        if body:
            sign_str += json.dumps(body, sort_keys=True)
        
        # HMAC-SHA256签名
        signature = hmac.new(
            self.private_key.encode(),
            sign_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "X-Tiger-Account": self.account,
            "X-Tiger-Timestamp": timestamp,
            "X-Tiger-Signature": signature,
            "Content-Type": "application/json",
        }
        
        if method.upper() == "GET":
            response = await self.http_client.get(endpoint, params=params, headers=headers)
        elif method.upper() == "POST":
            response = await self.http_client.post(endpoint, json=body, headers=headers)
        elif method.upper() == "DELETE":
            response = await self.http_client.delete(endpoint, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()


# === 数据格式转换 ===

def convert_tiger_to_standard(symbol: str, data: Dict, market_type: MarketType) -> Dict:
    """将老虎数据转换为标准格式"""
    return {
        "symbol": symbol,
        "market": market_type.value,
        "timestamp": data.get("timestamp", 0),
        "data_type": DataType.TICK.value,
        "payload": {
            "price": data.get("price", 0),
            "open": data.get("open", 0),
            "high": data.get("high", 0),
            "low": data.get("low", 0),
            "close": data.get("close", 0),
            "volume": data.get("volume", 0),
            "change": data.get("change", 0),
            "change_percent": data.get("change_percent", 0),
        },
    }
