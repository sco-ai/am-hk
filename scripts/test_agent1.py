"""
Agent1 单独数据采集测试
用于测试数据采集并展示在 Dashboard
"""
import asyncio
import json
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent1_harvester.main import MarketHarvester
from core.config import settings
from core.utils import setup_logging

logger = setup_logging("agent1_test")


async def main():
    """运行 Agent1 采集测试"""
    logger.info("=" * 60)
    logger.info("Agent1 MarketHarvester 数据采集测试")
    logger.info("=" * 60)
    logger.info(f"Binance API: {'已配置' if settings.BINANCE_API_KEY else '未配置'}")
    logger.info(f"NewsAPI: {'已配置' if settings.NEWSAPI_KEY else '未配置'}")
    logger.info("目标: BTCUSDT, ETHUSDT")
    logger.info("数据流: am-hk-raw-market-data (Redis)")
    logger.info("Dashboard: http://localhost:5020")
    logger.info("=" * 60)
    
    harvester = MarketHarvester()
    
    try:
        await harvester.start()
    except KeyboardInterrupt:
        logger.info("\n收到停止信号...")
        await harvester.stop()
    except Exception as e:
        logger.error(f"运行错误: {e}", exc_info=True)
        await harvester.stop()


if __name__ == "__main__":
    asyncio.run(main())
