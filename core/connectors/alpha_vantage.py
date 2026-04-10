"""
Alpha Vantage 美股数据连接器
免费版: 5次/分钟, 500次/天
支持：K线、实时报价、技术指标
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable

import aiohttp

from core.config import settings
from core.utils import setup_logging

logger = setup_logging("alphavantage_connector")


class AlphaVantageConnector:
    """
    Alpha Vantage 美股数据连接器
    
    注册: https://www.alphavantage.co/support/#api-key
    免费限制: 5 calls/minute, 500 calls/day
    """
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.ALPHAVANTAGE_API_KEY
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self.last_request_time = 0
        self.min_interval = 12  # 秒 (60/5=12s per request)
        
    async def connect(self):
        """建立连接"""
        self.session = aiohttp.ClientSession()
        self.running = True
        logger.info("Alpha Vantage connector connected")
        
    async def disconnect(self):
        """断开连接"""
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("Alpha Vantage connector disconnected")
        
    async def _rate_limit(self):
        """请求频率限制"""
        import time
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()
        
    async def get_daily_klines(self, symbol: str) -> List[Dict]:
        """
        获取日线数据 (免费版)
        
        Args:
            symbol: 股票代码 (如 "AAPL")
        """
        if not self.api_key:
            logger.error("Alpha Vantage API key not configured")
            return []
            
        await self._rate_limit()
        
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "apikey": self.api_key,
            "outputsize": "compact",  # compact = last 100 days
        }
        
        try:
            async with self.session.get(self.BASE_URL, params=params) as response:
                data = await response.json()
                
                time_series_key = "Time Series (Daily)"
                if time_series_key not in data:
                    logger.error(f"No daily data for {symbol}: {data.get('Information', 'Unknown error')}")
                    return []
                
                time_series = data[time_series_key]
                klines = []
                
                for date_str, values in time_series.items():
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    klines.append({
                        "timestamp": int(dt.timestamp()),
                        "open": float(values["1. open"]),
                        "high": float(values["2. high"]),
                        "low": float(values["3. low"]),
                        "close": float(values["4. close"]),
                        "volume": int(values["5. volume"]),
                        "symbol": symbol,
                    })
                
                klines.sort(key=lambda x: x["timestamp"])
                return klines
                
        except Exception as e:
            logger.error(f"Error fetching daily klines for {symbol}: {e}")
            return []
    
    async def get_quote(self, symbol: str) -> Dict:
        """获取实时报价"""
        if not self.api_key:
            logger.error("Alpha Vantage API key not configured")
            return {}
            
        await self._rate_limit()
        
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self.api_key,
        }
        
        try:
            async with self.session.get(self.BASE_URL, params=params) as response:
                data = await response.json()
                
                quote = data.get("Global Quote", {})
                if not quote:
                    return {}
                
                return {
                    "symbol": symbol,
                    "price": float(quote.get("05. price", 0)),
                    "change": float(quote.get("09. change", 0)),
                    "change_percent": quote.get("10. change percent", "0%").replace("%", ""),
                    "volume": int(quote.get("06. volume", 0)),
                    "timestamp": int(datetime.now().timestamp()),
                }
                
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return {}
    
    async def start_polling(self, symbols: List[str], 
                           callback: Callable,
                           intervals: List[str] = None):
        """启动数据轮询（日线数据，免费版）"""
        logger.info(f"Starting Alpha Vantage polling for {len(symbols)} symbols (Daily data)")
        logger.warning(f"Rate limit: 5 requests/min. Using daily data (free tier)")
        
        while self.running:
            try:
                for symbol in symbols:
                    # 获取日线数据
                    klines = await self.get_daily_klines(symbol)
                    if klines:
                        for kline in klines[-3:]:  # 最近3天
                            data = {
                                "symbol": symbol,
                                "market": "US",
                                "timestamp": kline["timestamp"] * 1000,
                                "data_type": "kline",
                                "payload": {
                                    "timestamp": kline["timestamp"],
                                    "open": kline["open"],
                                    "high": kline["high"],
                                    "low": kline["low"],
                                    "close": kline["close"],
                                    "volume": kline["volume"],
                                    "interval": "1d",  # 日线
                                },
                            }
                            await callback(symbol, data)
                    
                    # 获取实时报价
                    quote = await self.get_quote(symbol)
                    if quote:
                        data = {
                            "symbol": symbol,
                            "market": "US",
                            "timestamp": int(datetime.now().timestamp() * 1000),
                            "data_type": "quote",
                            "payload": quote,
                        }
                        await callback(symbol, data)
                
                # 轮询间隔: 每小时更新一次日线数据
                logger.info(f"Daily data updated for {len(symbols)} symbols. Waiting 1 hour...")
                await asyncio.sleep(3600)  # 1小时
                
            except Exception as e:
                    logger.error(f"Error in polling loop: {e}")
                    await asyncio.sleep(300)
