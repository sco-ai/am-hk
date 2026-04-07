"""
老虎证券数据连接器 - 支持代理
港股/美股接入 - 模拟盘/实盘支持
"""
import asyncio
import json
import logging
import os
import time
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
    - HTTP/HTTPS代理
    
    文档: https://www.itigerup.com/help/faq/133
    """
    
    # API端点
    BASE_URL_PAPER = "https://openapi-sandbox.itigerup.com/gateway"  # 模拟盘
    BASE_URL_LIVE = "https://openapi.itigerup.com/gateway"  # 实盘
    
    WS_URL_PAPER = "wss://openapi-sandbox.itigerup.com/websocket"
    WS_URL_LIVE = "wss://openapi.itigerup.com/websocket"
    
    def __init__(self, account: str = None, private_key: str = None, proxy: str = None):
        self.account = account or settings.TIGER_ACCOUNT
        self.private_key = private_key or settings.TIGER_PRIVATE_KEY
        self.paper_trading = settings.TIGER_ENABLE_PAPER
        self.proxy = proxy or os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        
        # 选择端点
        if self.paper_trading:
            self.base_url = self.BASE_URL_PAPER
            self.ws_url = self.WS_URL_PAPER
            logger.info("Tiger connector initialized [PAPER TRADING]")
        else:
            self.base_url = self.BASE_URL_LIVE
            self.ws_url = self.WS_URL_LIVE
            logger.warning("Tiger connector initialized [LIVE TRADING] - USE WITH CAUTION")
        
        # 配置HTTP客户端使用代理
        if self.proxy:
            self.http_client: Optional[httpx.AsyncClient] = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                proxies=self.proxy,
            )
            logger.info(f"Using proxy: {self.proxy}")
        else:
            self.http_client: Optional[httpx.AsyncClient] = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
            )
        
        self.ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        self.subscriptions: Dict[str, Callable] = {}
        self.running = False
    
    async def connect(self):
        """建立连接"""
        # HTTP客户端已在__init__中创建
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
    
    # === 美股专用数据接口 ===
    
    async def get_us_premarket_quote(self, symbol: str) -> Dict:
        """
        获取美股盘前/盘后数据
        
        Args:
            symbol: 美股代码，如 "NVDA", "TSLA"
        
        Returns:
            {
                "symbol": str,
                "market": "US",
                "session": "pre_market" | "after_hours" | "regular",
                "price": float,
                "change": float,
                "change_percent": float,
                "volume": int,
                "timestamp": int,
            }
        """
        endpoint = "/quote/extended"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": "US",
        }
        
        response = await self._signed_request("GET", endpoint, params)
        data = response.get("data", {})
        
        # 判断交易时段
        session = data.get("session", "regular")
        if session not in ["pre_market", "after_hours", "regular"]:
            session = "regular"
        
        return {
            "symbol": symbol,
            "market": "US",
            "session": session,
            "price": float(data.get("latestPrice", 0)),
            "change": float(data.get("change", 0)),
            "change_percent": float(data.get("changeRate", 0)),
            "volume": int(data.get("volume", 0)),
            "timestamp": data.get("timestamp", 0),
        }
    
    async def get_us_tick_data(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        获取美股逐笔成交数据 (Tick)
        
        Args:
            symbol: 美股代码
            limit: 返回条数
        
        Returns:
            [
                {
                    "timestamp": int,
                    "price": float,
                    "size": int,
                    "side": "buy" | "sell",
                    "exchange": str,
                }
            ]
        """
        endpoint = "/quote/ticks"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": "US",
            "limit": limit,
        }
        
        response = await self._signed_request("GET", endpoint, params)
        items = response.get("data", {}).get("items", [])
        
        ticks = []
        for item in items:
            ticks.append({
                "timestamp": item.get("time"),
                "price": float(item.get("price", 0)),
                "size": int(item.get("size", 0)),
                "side": "buy" if item.get("side") == "B" else "sell",
                "exchange": item.get("exchange", ""),
            })
        
        return ticks
    
    async def get_us_level2_orderbook(self, symbol: str, limit: int = 10) -> Dict:
        """
        获取美股Level2订单簿 (深度行情)
        
        Returns:
            {
                "symbol": str,
                "bids": [[price, size, exchange], ...],
                "asks": [[price, size, exchange], ...],
                "nbbo": {
                    "bid": float,
                    "bid_size": int,
                    "ask": float,
                    "ask_size": int,
                },
                "spread": float,
            }
        """
        endpoint = "/quote/level2"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": "US",
            "limit": limit,
        }
        
        response = await self._signed_request("GET", endpoint, params)
        data = response.get("data", {})
        
        # 解析Level2数据
        bids = []
        asks = []
        
        for bid in data.get("bids", []):
            bids.append([
                float(bid.get("price", 0)),
                int(bid.get("size", 0)),
                bid.get("exchange", "")
            ])
        
        for ask in data.get("asks", []):
            asks.append([
                float(ask.get("price", 0)),
                int(ask.get("size", 0)),
                ask.get("exchange", "")
            ])
        
        # NBBO (National Best Bid and Offer)
        nbbo = data.get("nbbo", {})
        best_bid = float(nbbo.get("bid", 0))
        best_ask = float(nbbo.get("ask", 0))
        spread = best_ask - best_bid if best_ask > best_bid else 0
        
        return {
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "nbbo": {
                "bid": best_bid,
                "bid_size": int(nbbo.get("bidSize", 0)),
                "ask": best_ask,
                "ask_size": int(nbbo.get("askSize", 0)),
            },
            "spread": spread,
        }
    
    async def get_us_dark_pool_data(self, symbol: str) -> Dict:
        """
        获取美股暗池(Dark Pool)交易数据
        
        Returns:
            {
                "symbol": str,
                "vwap": float,
                "institutional_percent": float,
                "dark_pool_volume": int,
                "total_volume": int,
                "blocks": [
                    {"price": float, "size": int, "timestamp": int}
                ],
            }
        """
        endpoint = "/quote/darkpool"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": "US",
        }
        
        response = await self._signed_request("GET", endpoint, params)
        data = response.get("data", {})
        
        blocks = []
        for block in data.get("blocks", []):
            blocks.append({
                "price": float(block.get("price", 0)),
                "size": int(block.get("size", 0)),
                "timestamp": block.get("time", 0),
            })
        
        total_vol = int(data.get("totalVolume", 1))
        dark_pool_vol = int(data.get("darkPoolVolume", 0))
        
        return {
            "symbol": symbol,
            "vwap": float(data.get("vwap", 0)),
            "institutional_percent": float(data.get("institutionalPercent", 0)),
            "dark_pool_volume": dark_pool_vol,
            "total_volume": total_vol,
            "dark_pool_ratio": dark_pool_vol / total_vol if total_vol > 0 else 0,
            "blocks": blocks,
        }
    
    async def get_us_etf_flow(self, etf_symbol: str) -> Dict:
        """
        获取ETF资金流向数据
        
        Args:
            etf_symbol: ETF代码，如 "QQQ", "SPY"
        
        Returns:
            {
                "symbol": str,
                "inflow": float,
                "outflow": float,
                "net_flow": float,
                "assets_under_management": float,
                "creation_units": int,
                "redemption_units": int,
            }
        """
        endpoint = "/quote/etfflow"
        
        params = {
            "account": self.account,
            "symbol": etf_symbol,
            "market": "US",
        }
        
        response = await self._signed_request("GET", endpoint, params)
        data = response.get("data", {})
        
        return {
            "symbol": etf_symbol,
            "inflow": float(data.get("inflow", 0)),
            "outflow": float(data.get("outflow", 0)),
            "net_flow": float(data.get("netFlow", 0)),
            "assets_under_management": float(data.get("aum", 0)),
            "creation_units": int(data.get("creationUnits", 0)),
            "redemption_units": int(data.get("redemptionUnits", 0)),
        }
    
    async def get_us_sector_flow(self, sector: str = "technology") -> Dict:
        """
        获取板块资金流向数据
        
        Args:
            sector: 板块名称，如 "technology", "healthcare", "finance"
        
        Returns:
            {
                "sector": str,
                "net_flow": float,
                "top_inflow_symbols": [{"symbol": str, "flow": float}],
                "top_outflow_symbols": [{"symbol": str, "flow": float}],
            }
        """
        endpoint = "/quote/sectorflow"
        
        params = {
            "account": self.account,
            "sector": sector,
            "market": "US",
        }
        
        response = await self._signed_request("GET", endpoint, params)
        data = response.get("data", {})
        
        return {
            "sector": sector,
            "net_flow": float(data.get("netFlow", 0)),
            "top_inflow_symbols": data.get("topInflow", []),
            "top_outflow_symbols": data.get("topOutflow", []),
        }
    
    async def get_us_option_data(self, symbol: str) -> Dict:
        """
        获取美股期权数据 (Put/Call Ratio)
        
        Returns:
            {
                "symbol": str,
                "put_call_ratio": float,
                "put_volume": int,
                "call_volume": int,
                "total_volume": int,
                "implied_volatility": float,
                "skew": float,
            }
        """
        endpoint = "/quote/options"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": "US",
        }
        
        response = await self._signed_request("GET", endpoint, params)
        data = response.get("data", {})
        
        put_vol = int(data.get("putVolume", 0))
        call_vol = int(data.get("callVolume", 0))
        total_vol = put_vol + call_vol
        
        return {
            "symbol": symbol,
            "put_call_ratio": put_vol / call_vol if call_vol > 0 else 0,
            "put_volume": put_vol,
            "call_volume": call_vol,
            "total_volume": total_vol,
            "implied_volatility": float(data.get("impliedVolatility", 0)),
            "skew": float(data.get("skew", 0)),
        }
    
    async def subscribe_us_ticks(self, symbols: List[str], callback: Callable):
        """订阅美股逐笔成交推送"""
        for symbol in symbols:
            key = f"US:{symbol}"
            self.subscriptions[key] = callback
        
        # 启动WebSocket连接（如未启动）
        if not self.ws_connection:
            asyncio.create_task(self._ws_handler())
    
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
                # WebSocket代理配置
                if self.proxy:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(self.proxy)
                    proxy_host = parsed.hostname
                    proxy_port = parsed.port or 7890
                    
                    async with websockets.connect(
                        self.ws_url,
                        proxy=f"http://{proxy_host}:{proxy_port}"
                    ) as ws:
                        self.ws_connection = ws
                        logger.info("Tiger WebSocket connected via proxy")
                        
                        # 发送订阅请求
                        subscribe_msg = {
                            "command": "subscribe",
                            "account": self.account,
                            "symbols": list(self.subscriptions.keys()),
                        }
                        await ws.send(json.dumps(subscribe_msg))
                        
                        async for message in ws:
                            await self._handle_ws_message(message)
                else:
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
        import time as time_module
        import hashlib
        import hmac
        
        timestamp = str(int(time_module.time() * 1000))
        
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


    async def get_us_level2_orderbook(self, symbol: str, limit: int = 10) -> Dict:
        """
        获取美股Level2订单簿(NBBO+深度)
        
        Returns:
            {
                "symbol": str,
                "bids": [[price, size], ...],
                "asks": [[price, size], ...],
                "nbbo": {"bid": price, "ask": price},
                "spread": float,
            }
        """
        # 获取基础订单簿
        orderbook = await self.get_orderbook(symbol, "US", limit)
        
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        
        # 计算NBBO和价差
        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        spread = best_ask - best_bid if best_ask and best_bid else 0
        
        return {
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "nbbo": {"bid": best_bid, "ask": best_ask},
            "spread": spread,
        }
    
    async def get_us_premarket_quote(self, symbol: str) -> Dict:
        """
        获取美股盘前盘后数据
        
        Returns:
            {
                "session": "pre_market" | "regular" | "after_hours",
                "price": float,
                "change": float,
                "change_percent": float,
                "volume": int,
            }
        """
        endpoint = "/quote/premarket"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": "US",
        }
        
        try:
            response = await self._signed_request("GET", endpoint, params)
            data = response.get("data", {})
            
            return {
                "symbol": symbol,
                "session": data.get("session", "regular"),
                "price": float(data.get("price", 0)),
                "change": float(data.get("change", 0)),
                "change_percent": float(data.get("changeRate", 0)),
                "volume": int(data.get("volume", 0)),
                "timestamp": int(asyncio.get_event_loop().time() * 1000),
            }
        except Exception as e:
            logger.warning(f"Premarket API not available for {symbol}: {e}")
            # 返回常规行情作为fallback
            quote = await self.get_quote(symbol, "US")
            return {
                "symbol": symbol,
                "session": "regular",
                "price": quote.get("price", 0),
                "change": quote.get("change", 0),
                "change_percent": quote.get("change_percent", 0),
                "volume": quote.get("volume", 0),
                "timestamp": int(asyncio.get_event_loop().time() * 1000),
            }
    
    async def get_us_dark_pool_data(self, symbol: str) -> Dict:
        """
        获取美股暗池数据(Dark Pool)
        
        Returns:
            {
                "vwap": float,
                "institutional_percent": float,
                "dark_pool_volume": int,
                "total_volume": int,
                "dark_pool_ratio": float,
                "blocks": [],
            }
        """
        endpoint = "/quote/darkpool"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": "US",
        }
        
        try:
            response = await self._signed_request("GET", endpoint, params)
            data = response.get("data", {})
            
            return {
                "symbol": symbol,
                "vwap": float(data.get("vwap", 0)),
                "institutional_percent": float(data.get("institutionalPercent", 0)),
                "dark_pool_volume": int(data.get("darkPoolVolume", 0)),
                "total_volume": int(data.get("totalVolume", 0)),
                "dark_pool_ratio": float(data.get("darkPoolRatio", 0)),
                "blocks": data.get("blocks", []),
            }
        except Exception as e:
            logger.warning(f"Dark pool API not available for {symbol}, using mock: {e}")
            return {
                "symbol": symbol,
                "vwap": 0.0,
                "institutional_percent": 0.0,
                "dark_pool_volume": 0,
                "total_volume": 0,
                "dark_pool_ratio": 0.0,
                "blocks": [],
            }
    
    async def get_us_etf_flow(self, symbol: str) -> Dict:
        """
        获取美股ETF资金流数据
        
        Returns:
            {
                "inflow": float,
                "outflow": float,
                "net_flow": float,
                "assets_under_management": float,
                "creation_units": int,
                "redemption_units": int,
            }
        """
        endpoint = "/quote/etf_flow"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": "US",
        }
        
        try:
            response = await self._signed_request("GET", endpoint, params)
            data = response.get("data", {})
            
            return {
                "symbol": symbol,
                "inflow": float(data.get("inflow", 0)),
                "outflow": float(data.get("outflow", 0)),
                "net_flow": float(data.get("netFlow", 0)),
                "assets_under_management": float(data.get("aum", 0)),
                "creation_units": int(data.get("creationUnits", 0)),
                "redemption_units": int(data.get("redemptionUnits", 0)),
            }
        except Exception as e:
            logger.warning(f"ETF flow API not available for {symbol}, using mock: {e}")
            return {
                "symbol": symbol,
                "inflow": 0.0,
                "outflow": 0.0,
                "net_flow": 0.0,
                "assets_under_management": 0.0,
                "creation_units": 0,
                "redemption_units": 0,
            }
    
    async def get_us_option_data(self, symbol: str) -> Dict:
        """
        获取美股期权数据(Put/Call Ratio等)
        
        Returns:
            {
                "put_call_ratio": float,
                "put_volume": int,
                "call_volume": int,
                "total_volume": int,
                "implied_volatility": float,
                "skew": float,
            }
        """
        endpoint = "/quote/option"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": "US",
        }
        
        try:
            response = await self._signed_request("GET", endpoint, params)
            data = response.get("data", {})
            
            put_vol = int(data.get("putVolume", 0))
            call_vol = int(data.get("callVolume", 0))
            total_vol = put_vol + call_vol
            put_call_ratio = put_vol / call_vol if call_vol > 0 else 1.0
            
            return {
                "symbol": symbol,
                "put_call_ratio": put_call_ratio,
                "put_volume": put_vol,
                "call_volume": call_vol,
                "total_volume": total_vol,
                "implied_volatility": float(data.get("impliedVolatility", 0)),
                "skew": float(data.get("skew", 0)),
            }
        except Exception as e:
            logger.warning(f"Option API not available for {symbol}, using mock: {e}")
            return {
                "symbol": symbol,
                "put_call_ratio": 1.0,
                "put_volume": 0,
                "call_volume": 0,
                "total_volume": 0,
                "implied_volatility": 0.0,
                "skew": 0.0,
            }

    async def get_hk_capital_flow(self, symbol: str) -> Dict:
        """
        获取港股资金流数据(港股通/北水)
        
        Returns:
            {
                "northbound_net_inflow": float,  # 北向净流入
                "northbound_net_outflow": float, # 北向净流出
                "main_force_inflow": float,      # 主力资金流入
                "main_force_outflow": float,     # 主力资金流出
                "large_order_net": float,        # 大单净流入
                "retail_net": float,             # 散户净流入
            }
        """
        endpoint = "/quote/capital_flow"
        
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": "HK",
        }
        
        try:
            response = await self._signed_request("GET", endpoint, params)
            data = response.get("data", {})
            
            return {
                "symbol": symbol,
                "northbound_net_inflow": float(data.get("northboundInflow", 0)),
                "northbound_net_outflow": float(data.get("northboundOutflow", 0)),
                "main_force_inflow": float(data.get("mainForceInflow", 0)),
                "main_force_outflow": float(data.get("mainForceOutflow", 0)),
                "large_order_net": float(data.get("largeOrderNet", 0)),
                "retail_net": float(data.get("retailNet", 0)),
                "timestamp": int(asyncio.get_event_loop().time() * 1000),
            }
        except Exception as e:
            logger.warning(f"Capital flow API not available for {symbol}, using mock data: {e}")
            # 返回模拟数据用于测试
            return {
                "symbol": symbol,
                "northbound_net_inflow": 0.0,
                "northbound_net_outflow": 0.0,
                "main_force_inflow": 0.0,
                "main_force_outflow": 0.0,
                "large_order_net": 0.0,
                "retail_net": 0.0,
                "timestamp": int(asyncio.get_event_loop().time() * 1000),
            }

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


# === 美股专用数据转换函数 ===

def convert_us_kline_to_standard(symbol: str, kline: Dict) -> Dict:
    """将老虎美股K线转换为标准格式"""
    import time
    return {
        "symbol": symbol,
        "market": "US",
        "timestamp": int(time.time() * 1000),
        "data_type": "kline",
        "payload": {
            "timestamp": kline.get("timestamp"),
            "open": kline.get("open"),
            "high": kline.get("high"),
            "low": kline.get("low"),
            "close": kline.get("close"),
            "volume": kline.get("volume"),
            "interval": kline.get("interval", "1d"),
        },
    }


def convert_us_orderbook_to_standard(symbol: str, orderbook: Dict) -> Dict:
    """将老虎美股Level2订单簿转换为标准格式"""
    import time
    return {
        "symbol": symbol,
        "market": "US",
        "timestamp": int(time.time() * 1000),
        "data_type": "orderbook",
        "payload": {
            "bids": orderbook.get("bids", []),
            "asks": orderbook.get("asks", []),
            "nbbo": orderbook.get("nbbo", {}),
            "spread": orderbook.get("spread", 0),
            "level": 2,
        },
    }


def convert_us_premarket_to_standard(symbol: str, data: Dict) -> Dict:
    """将老虎盘前盘后数据转换为标准格式"""
    return {
        "symbol": symbol,
        "market": "US",
        "timestamp": data.get("timestamp", 0),
        "data_type": "premarket",
        "payload": {
            "session": data.get("session", "regular"),
            "price": data.get("price"),
            "change": data.get("change"),
            "change_percent": data.get("change_percent"),
            "volume": data.get("volume"),
        },
    }


def convert_us_darkpool_to_standard(symbol: str, data: Dict) -> Dict:
    """将老虎暗池数据转换为标准格式"""
    import time
    return {
        "symbol": symbol,
        "market": "US",
        "timestamp": int(time.time() * 1000),
        "data_type": "darkpool",
        "payload": {
            "vwap": data.get("vwap"),
            "institutional_percent": data.get("institutional_percent"),
            "dark_pool_volume": data.get("dark_pool_volume"),
            "total_volume": data.get("total_volume"),
            "dark_pool_ratio": data.get("dark_pool_ratio"),
            "blocks": data.get("blocks", []),
        },
    }


def convert_us_etf_flow_to_standard(symbol: str, data: Dict) -> Dict:
    """将老虎ETF资金流转换为标准格式"""
    import time
    return {
        "symbol": symbol,
        "market": "US",
        "timestamp": int(time.time() * 1000),
        "data_type": "etf_flow",
        "payload": {
            "inflow": data.get("inflow"),
            "outflow": data.get("outflow"),
            "net_flow": data.get("net_flow"),
            "assets_under_management": data.get("assets_under_management"),
            "creation_units": data.get("creation_units"),
            "redemption_units": data.get("redemption_units"),
        },
    }


def convert_us_option_to_standard(symbol: str, data: Dict) -> Dict:
    """将老虎期权数据转换为标准格式"""
    import time
    return {
        "symbol": symbol,
        "market": "US",
        "timestamp": int(time.time() * 1000),
        "data_type": "option",
        "payload": {
            "put_call_ratio": data.get("put_call_ratio"),
            "put_volume": data.get("put_volume"),
            "call_volume": data.get("call_volume"),
            "total_volume": data.get("total_volume"),
            "implied_volatility": data.get("implied_volatility"),
            "skew": data.get("skew"),
        },
    }


def convert_us_tick_to_standard(symbol: str, tick: Dict) -> Dict:
    """将老虎逐笔成交转换为标准格式"""
    return {
        "symbol": symbol,
        "market": "US",
        "timestamp": tick.get("timestamp", 0),
        "data_type": "tick",
        "payload": {
            "price": tick.get("price"),
            "size": tick.get("size"),
            "side": tick.get("side"),
            "exchange": tick.get("exchange"),
        },
    }
