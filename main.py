"""
AM-HK v3.0 主入口
启动所有Agent和API服务
"""
import asyncio
import logging
import signal
import sys
from typing import List

from core.utils import setup_logging

logger = setup_logging("am-hk-main")


class AMHKSystem:
    """AM-HK交易系统主控"""
    
    def __init__(self):
        self.agents = {}
        self.tasks = []
        self.running = False
        
        # 信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理"""
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(self.shutdown())
    
    async def start(self):
        """启动系统"""
        logger.info("=" * 60)
        logger.info("AM-HK v3.0 Trading System Starting...")
        logger.info("=" * 60)
        
        self.running = True
        
        # 启动Agent
        await self._start_agents()
        
        # 启动API服务
        await self._start_api()
        
        logger.info("All services started successfully!")
        
        # 保持运行
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
    
    async def _start_agents(self):
        """启动所有Agent"""
        logger.info("Starting agents...")
        
        # Agent 1: 数据采集
        from agents.agent1_harvester.main import MarketHarvester
        agent1 = MarketHarvester()
        self.agents["harvester"] = agent1
        self.tasks.append(asyncio.create_task(agent1.start()))
        logger.info("✓ Agent1 MarketHarvester started")
        
        # Agent 2: 因子处理
        from agents.agent2_curator.main import DataCurator
        agent2 = DataCurator()
        self.agents["curator"] = agent2
        self.tasks.append(asyncio.create_task(agent2.start()))
        logger.info("✓ Agent2 DataCurator started")
        
        # Agent 3: 机会扫描
        from agents.agent3_scanner.main import AlphaScanner
        agent3 = AlphaScanner()
        self.agents["scanner"] = agent3
        self.tasks.append(asyncio.create_task(agent3.start()))
        logger.info("✓ Agent3 AlphaScanner started")
        
        # Agent 4: 核心决策
        from agents.agent4_oracle.main import TrendOracle
        agent4 = TrendOracle()
        self.agents["oracle"] = agent4
        self.tasks.append(asyncio.create_task(agent4.start()))
        logger.info("✓ Agent4 TrendOracle started")
        
        # Agent 5: 风控
        from agents.agent5_guardian.main import RiskGuardian
        agent5 = RiskGuardian()
        self.agents["guardian"] = agent5
        self.tasks.append(asyncio.create_task(agent5.start()))
        logger.info("✓ Agent5 RiskGuardian started")
        
        # Agent 6: 学习反馈
        from agents.agent6_learning.main import LearningFeedback
        agent6 = LearningFeedback()
        self.agents["learning"] = agent6
        self.tasks.append(asyncio.create_task(agent6.start()))
        logger.info("✓ Agent6 LearningFeedback started")
    
    async def _start_api(self):
        """启动API服务"""
        logger.info("Starting API service...")
        
        from api.main import start_api
        self.tasks.append(asyncio.create_task(start_api()))
        logger.info("✓ API service started on port 8020")
    
    async def shutdown(self):
        """优雅关闭"""
        logger.info("Shutting down AM-HK system...")
        self.running = False
        
        # 停止所有Agent
        for name, agent in self.agents.items():
            try:
                await agent.stop()
                logger.info(f"✓ Agent {name} stopped")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")
        
        # 取消所有任务
        for task in self.tasks:
            task.cancel()
        
        # 等待任务完成
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        logger.info("AM-HK system shutdown complete")


async def main():
    """主入口"""
    system = AMHKSystem()
    
    try:
        await system.start()
    except Exception as e:
        logger.error(f"System error: {e}", exc_info=True)
        await system.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
