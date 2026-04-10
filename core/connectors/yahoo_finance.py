"""
Yahoo Finance 美股数据连接器
免费数据源，15分钟延迟
支持：K线、实时报价、订单簿
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable

import aiohttp
import yfinance as yf

from core.config import settings
from core.models import MarketType, DataType
from core.utils import setup_logging

logger = setup_logging("yahoo_connector")


class YahooFinanceConnector:
    """
    Yahoo Finance 美股数据连接器
    
    数据源特性：
    - 免费，无需API Key
    - 15分钟延迟（实盘可用）
    - 支持美股全市场
    - 历史数据可回溯多年
    """
    
    BASE_URL = "https://query1.finance.yahoo.com"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.subscriptions: Dict[str, Dict] = {}
        self.running = False
        self.poll_interval = 60  # 秒
        
    async def connect(self):
        """建立连接"""
        self.session = aiohttp.ClientSession()
        self.running = True
        logger.info("Yahoo Finance connector connected")
        
    async def disconnect(self):
        """断开连接"""
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("Yahoo Finance connector disconnected")
        
    async def get_klines(self, symbol: str, interval: str = "1m", 
                         period: str = "1d") -> List[Dict]:
        """
        获取K线数据
        
        Args:
            symbol: 股票代码 (如 "AAPL", "TSLA")
            interval: 1m, 2m, 5m, 15m, 30m, 60m, 1d, 1wk, 1mo
            period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        """
        try:
            # yfinance 是同步库，在线程池中运行
            loop = asyncio.get_event_loop()
            ticker = yf.Ticker(symbol)
            
            # 使用线程池执行同步操作
            hist = await loop.run_in_executor(
                None, 
                lambda: ticker.history(period=period, interval=interval)
            )
            
            klines = []
            for index, row in hist.iterrows():
                klines.append({
                    "timestamp": int(index.timestamp()),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                    "symbol": symbol,
                })
            
            return klines
            
        except Exception as e:
            logger.error(f"Error fetching klines for {symbol}: {e}")
            return []
    
    async def get_quote(self, symbol: str) -> Dict:
        """获取实时报价"""
        try:
            loop = asyncio.get_event_loop()
            ticker = yf.Ticker(symbol)
            
            info = await loop.run_in_executor(None, lambda: ticker.info)
            
            return {
                "symbol": symbol,
                "price": info.get("regularMarketPrice", 0),
                "change": info.get("regularMarketChange", 0),
                "change_percent": info.get("regularMarketChangePercent", 0),
                "volume": info.get("regularMarketVolume", 0),
                "market_cap": info.get("marketCap", 0),
                "timestamp": int(datetime.now().timestamp()),
            }
            
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return {}
    
    async def start_polling(self, symbols: List[str], 
                           callback: Callable,
                           intervals: List[str] = None):
        """
        启动数据轮询
        
        Args:
            symbols: 股票代码列表
            callback: 数据回调函数
            intervals: 时间间隔列表 ["1m", "5m", "1d"]
        """
        if not intervals:
            intervals = ["1m", "5m", "1d"]
            
        logger.info(f"Starting Yahoo polling for {len(symbols)} symbols: {symbols}")
        
        while self.running:
            try:
                for symbol in symbols:
                    for interval in intervals:
                        # 获取K线
                        klines = await self.get_klines(symbol, interval, period="1d")
                        if klines:
                            for kline in klines[-5:]:  # 最近5条
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
                                        "interval": interval,
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
                        
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(5)


def convert_us_kline_to_standard(symbol: str, kline: Dict) -> Dict:
    """转换美股K线为统一格式"""
    return {
        "symbol": symbol,
        "market": "US",
        "timestamp": kline.get("timestamp", 0) * 1000,
        "data_type": "kline",
        "payload": {
            "timestamp": kline.get("timestamp"),
            "open": kline.get("open"),
            "high": kline.get("high"),
            "low": kline.get("low"),
            "close": kline.get("close"),
            "volume": kline.get("volume"),
            "interval": kline.get("interval", "1m"),
        },
    }
