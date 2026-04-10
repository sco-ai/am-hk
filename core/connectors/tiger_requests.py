"""
老虎证券数据连接器 - 使用 requests (同步版本，更好的代理支持)
港股/美股接入 - 模拟盘/实盘支持
"""
import json
import logging
import os
import time
from typing import Dict, List, Optional

import requests

from core.config import settings
from core.utils import setup_logging

logger = setup_logging("tiger_connector")


class TigerConnector:
    """
    老虎证券数据连接器 - requests 版本
    ...
    """
    
    # API端点
    BASE_URL_PAPER = "https://openapi-sandbox.itigerup.com/gateway"
    BASE_URL_LIVE = "https://openapi.itigerup.com/gateway"
    
    def __init__(self, account: str = None, private_key: str = None, proxy: str = None):
        self.account = account or settings.TIGER_ACCOUNT
        self.private_key = private_key or settings.TIGER_PRIVATE_KEY
        self.paper_trading = settings.TIGER_ENABLE_PAPER
        # 优先使用传入的proxy参数，其次从settings读取，最后尝试SOCKS5
        http_proxy = proxy or settings.HTTP_PROXY or settings.HTTPS_PROXY
        # 如果是 HTTP 代理，转换为 SOCKS5 (Clash HTTP CONNECT 有bug)
        if http_proxy and http_proxy.startswith("http://"):
            # Clash SOCKS5 端口通常是 7891
            self.proxy = "socks5://127.0.0.1:7891"
        elif http_proxy:
            self.proxy = http_proxy
        else:
            self.proxy = None
        
        if self.paper_trading:
            self.base_url = self.BASE_URL_PAPER
            logger.info("Tiger connector initialized [PAPER TRADING]")
        else:
            self.base_url = self.BASE_URL_LIVE
            logger.warning("Tiger connector initialized [LIVE TRADING] - USE WITH CAUTION")
        
        self.session = requests.Session()
        if self.proxy:
            self.session.proxies = {
                "http": self.proxy,
                "https": self.proxy,
            }
            logger.info(f"Using proxy: {self.proxy}")
        
    def connect(self):
        """建立连接"""
        logger.info("Tiger HTTP client connected")
    
    def disconnect(self):
        """断开连接"""
        self.session.close()
        logger.info("Tiger connector disconnected")
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            result = self.get_account()
            return result.get("account") is not None
        except Exception as e:
            logger.warning(f"Tiger health check failed: {e}")
            return False
    
    def get_quote(self, symbol: str, market: str = "US") -> Dict:
        """获取实时行情"""
        endpoint = "/quote"
        params = {"account": self.account, "symbol": symbol, "market": market}
        
        response = self._signed_request("GET", endpoint, params)
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
    
    def get_klines(self, symbol: str, market: str = "US", 
                   period: str = "day", limit: int = 100) -> List[Dict]:
        """获取K线数据"""
        endpoint = "/quote/kline"
        params = {
            "account": self.account,
            "symbol": symbol,
            "market": market,
            "period": period,
            "limit": limit,
        }
        
        response = self._signed_request("GET", endpoint, params)
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
    
    def get_orderbook(self, symbol: str, market: str = "US", limit: int = 10) -> Dict:
        """获取订单簿"""
        endpoint = "/quote/depth"
        params = {"account": self.account, "symbol": symbol, "market": market, "limit": limit}
        
        response = self._signed_request("GET", endpoint, params)
        data = response.get("data", {})
        
        bids = [[float(p), int(s)] for p, s in data.get("bids", [])]
        asks = [[float(p), int(s)] for p, s in data.get("asks", [])]
        
        return {"symbol": symbol, "bids": bids, "asks": asks}
    
    def get_account(self) -> Dict:
        """查询账户信息"""
        endpoint = "/account"
        params = {"account": self.account}
        
        response = self._signed_request("GET", endpoint, params)
        data = response.get("data", {})
        
        return {
            "account": self.account,
            "currency": data.get("currency"),
            "cash": float(data.get("cash", 0)),
            "net_liquidation": float(data.get("netLiquidation", 0)),
            "buying_power": float(data.get("buyingPower", 0)),
            "equity": float(data.get("equityWithLoanValue", 0)),
        }
    
    def _signed_request(self, method: str, endpoint: str, 
                        params: Optional[Dict] = None,
                        body: Optional[Dict] = None) -> Dict:
        """发送带签名的请求"""
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
        
        url = f"{self.base_url}{endpoint}"
        
        if method.upper() == "GET":
            resp = self.session.get(url, params=params, headers=headers, timeout=30)
        elif method.upper() == "POST":
            resp = self.session.post(url, json=body, headers=headers, timeout=30)
        elif method.upper() == "DELETE":
            resp = self.session.delete(url, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        resp.raise_for_status()
        return resp.json()
