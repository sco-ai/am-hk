#!/usr/bin/env python3
"""
Agent 3: AlphaScanner 主程序
订阅 processed-data，生成交易机会到 trading-opportunities
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

import asyncio
import json
from datetime import datetime

from agents.agent3_scanner.main import AlphaScanner, Opportunity, Direction, OpportunityPool
from core.kafka import MessageBus, AgentConsumer
from core.utils import setup_logging, generate_timestamp

logger = setup_logging("agent3_scanner_main")


class AlphaScannerAgent:
    """Agent3 完整实现 - 带 Kafka Consumer"""
    
    def __init__(self):
        self.agent_name = "agent3_scanner"
        self.scanner = AlphaScanner()
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-processed-data"]
        )
        self.processed_count = 0
        self.opportunity_count = 0
        
        logger.info(f"{self.agent_name} initialized")
    
    def _on_processed_data(self, key: str, value: dict, headers: dict):
        """处理 Agent2 的因子数据"""
        try:
            symbol = value.get("symbol", key)
            factors = value.get("factors", {})
            
            if not factors:
                return
            
            self.processed_count += 1
            
            # 简单评分逻辑（简化版）
            score = self._quick_score(factors)
            
            # 生成交易机会（阈值 > 0.7）
            if score > 0.7:
                opportunity = {
                    "symbol": symbol,
                    "market": value.get("market", "HK"),
                    "timestamp": generate_timestamp(),
                    "score": score,
                    "direction": "BUY" if score > 0.75 else "HOLD",
                    "confidence": score,
                    "factors": factors,
                    "source": "agent3_scanner"
                }
                
                self.bus.send(
                    topic="am-hk-trading-opportunities",
                    key=symbol,
                    value=opportunity
                )
                
                self.opportunity_count += 1
                logger.info(f"Generated opportunity: {symbol} score={score:.2f}")
            
            # 每 100 条输出统计
            if self.processed_count % 100 == 0:
                logger.info(f"Processed {self.processed_count}, opportunities {self.opportunity_count}")
                
        except Exception as e:
            logger.error(f"Error processing data: {e}")
    
    def _quick_score(self, factors: dict) -> float:
        """快速评分"""
        score = 0.5
        
        # 动量因子
        mom_5m = factors.get("price_momentum_5m", 0)
        if abs(mom_5m) > 1.0:
            score += 0.1 * (1 if mom_5m > 0 else -1)
        
        # RSI
        rsi = factors.get("rsi_14", 50)
        if rsi < 30:
            score += 0.15  # 超卖
        elif rsi > 70:
            score -= 0.15  # 超买
        
        # 资金流
        main_ratio = factors.get("main_force_ratio", 0)
        if main_ratio > 0.6:
            score += 0.1
        
        # 跨市场信号
        layer1 = factors.get("layer1_signal", 0)
        if layer1 > 0.5:
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    async def start(self):
        """启动 Agent3"""
        logger.info(f"{self.agent_name} starting...")
        
        # 注册消息处理器
        self.consumer.register_handler("processed_data", self._on_processed_data)
        # 兼容不同 data_type
        self.consumer.register_handler("kline", self._on_processed_data)
        self.consumer.register_handler("tick", self._on_processed_data)
        
        # 发布状态
        self.bus.publish_status({
            "state": "running",
            "scanner_type": "AlphaScanner",
            "threshold": 0.7
        })
        
        try:
            self.consumer.start()
        except Exception as e:
            logger.error(f"Consumer error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """停止 Agent3"""
        logger.info(f"{self.agent_name} stopping...")
        self.consumer.stop()
        self.bus.close()


if __name__ == "__main__":
    agent = AlphaScannerAgent()
    asyncio.run(agent.start())
