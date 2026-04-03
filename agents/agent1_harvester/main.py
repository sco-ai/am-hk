"""
Agent 1: MarketHarvester
多市场数据采集器 - 币安实时数据版
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
        }
        
        # 连接器
        self.binance: BinanceConnector = None
        
        logger.info(f"{self.agent_name} initialized")
    
    async def start(self):
        """启动采集器"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 启动币安连接器
        await self._start_binance()
        
        # 发布状态
        self.bus.publish_status({
            "state": "running",
            "markets": [m.value for m in self.subscriptions.keys()],
            "symbols": {
                "btc": self.subscriptions[MarketType.BTC]["symbols"],
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
        except Exception as e:
            logger.error(f"Health check error: {e}")


if __name__ == "__main__":
    harvester = MarketHarvester()
    asyncio.run(harvester.start())
