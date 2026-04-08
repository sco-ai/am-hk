"""
Agent 7: PerformanceAnalyzer - 绩效分析器
交易结果分析与绩效报告生成
"""
import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import deque
import numpy as np

from core.kafka import MessageBus, AgentConsumer
from core.models import TradeDecision, Signal, ActionType
from core.utils import generate_msg_id, generate_timestamp, setup_logging

# 导入子模块
from agents.agent7_performance.modules.metrics_calculator import MetricsCalculator
from agents.agent7_performance.modules.attribution_analyzer import AttributionAnalyzer
from agents.agent7_performance.modules.risk_analyzer import RiskAnalyzer
from agents.agent7_performance.modules.report_generator import ReportGenerator
from agents.agent7_performance.modules.feishu_publisher import FeishuPublisher

logger = setup_logging("agent7_performance")


class PerformanceAnalyzer:
    """
    Agent 7: 绩效分析器
    
    职责：
    - 交易结果分析
    - 绩效指标计算（收益率、夏普比率、最大回撤等）
    - 策略归因分析（动量/价值/情绪/跨市场）
    - 风险分析（VaR/CVaR）
    - 报告生成（日报/周报/月报）
    - 飞书卡片推送
    
    输入：
    - Kafka: am-hk-trade-results (交易执行结果)
    - 包含：实际成交价格、盈亏、持仓时间、滑点等
    
    输出：
    - Kafka: am-hk-performance-reports (广播给所有Agent)
    """
    
    def __init__(self):
        self.agent_name = "agent7_performance"
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-trade-results", "am-hk-performance-requests"]
        )
        
        # 初始化各模块
        self.metrics_calculator = MetricsCalculator()
        self.attribution_analyzer = AttributionAnalyzer()
        self.risk_analyzer = RiskAnalyzer()
        self.report_generator = ReportGenerator()
        self.feishu_publisher = FeishuPublisher()
        
        # 交易历史缓存
        self.trade_history: deque = deque(maxlen=100000)
        self.min_samples_for_analysis = 10
        
        # 报告生成配置
        self.daily_report_time = "20:00"  # 每日20:00生成日报
        self.weekly_report_day = 5  # 周五
        self.monthly_report_day = 1  # 每月1号
        
        # 初始化资金（可配置）
        self.initial_capital = 1000000.0  # 初始资金100万
        self.risk_free_rate = 0.02  # 无风险利率2%
        
        self.running = False
        logger.info(f"{self.agent_name} initialized with all analysis modules")
    
    async def start(self):
        """启动绩效分析器"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 加载历史数据
        await self._load_trade_history()
        
        # 注册消息处理器
        self.consumer.register_handler("trade_result", self._on_trade_result)
        self.consumer.register_handler("report_request", self._on_report_request)
        
        # 发布状态
        self._publish_status("running")
        
        # 启动定时任务
        tasks = [
            asyncio.create_task(self._daily_report_loop()),
            asyncio.create_task(self._weekly_report_loop()),
            asyncio.create_task(self._monthly_report_loop()),
        ]
        
        try:
            self.consumer.start()
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
        finally:
            for task in tasks:
                task.cancel()
            await self.stop()
    
    async def stop(self):
        """停止绩效分析器"""
        logger.info(f"{self.agent_name} stopping...")
        self.running = False
        self.consumer.stop()
        
        # 保存历史数据
        await self._save_trade_history()
        
        self._publish_status("stopped")
        self.bus.flush()
        self.bus.close()
        
        logger.info(f"{self.agent_name} stopped")
    
    def _on_trade_result(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理交易结果"""
        try:
            payload = value.get("payload", {})
            
            trade_record = {
                "msg_id": value.get("msg_id"),
                "timestamp": payload.get("timestamp", generate_timestamp()),
                "symbol": payload.get("symbol"),
                "action": payload.get("action"),
                "strategy": payload.get("strategy", "unknown"),
                "entry_price": payload.get("entry_price"),
                "exit_price": payload.get("exit_price"),
                "quantity": payload.get("quantity"),
                "pnl": payload.get("pnl", 0.0),
                "pnl_pct": payload.get("pnl_pct", 0.0),
                "holding_time": payload.get("holding_time", 0),
                "transaction_cost": payload.get("transaction_cost", 0.0),
                "slippage": payload.get("slippage", 0.0),
                "factors": payload.get("factors", {}),
                "signal_confidence": payload.get("signal_confidence", 0.0),
                "predicted_return": payload.get("predicted_return", 0.0),
                "market_condition": payload.get("market_condition", {}),
            }
            
            self._add_trade_record(trade_record)
            
            logger.info(f"Recorded trade result: {trade_record['symbol']} "
                       f"Strategy={trade_record['strategy']} "
                       f"PNL={trade_record['pnl']:.2f}")
        
        except Exception as e:
            logger.error(f"Error processing trade result: {e}", exc_info=True)
    
    def _on_report_request(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理报告请求"""
        try:
            payload = value.get("payload", {})
            report_type = payload.get("report_type", "daily")
            
            logger.info(f"Received report request: {report_type}")
            
            # 生成报告
            asyncio.create_task(self._generate_and_publish_report(report_type))
            
        except Exception as e:
            logger.error(f"Error processing report request: {e}", exc_info=True)
    
    def _add_trade_record(self, record: Dict):
        """添加交易记录"""
        self.trade_history.append(record)
    
    async def _daily_report_loop(self):
        """日报生成循环"""
        while self.running:
            try:
                now = datetime.now()
                target_time = datetime.strptime(self.daily_report_time, "%H:%M").time()
                target_datetime = datetime.combine(now.date(), target_time)
                
                if now.time() > target_time:
                    target_datetime += timedelta(days=1)
                
                wait_seconds = (target_datetime - now).total_seconds()
                logger.info(f"Next daily report at {target_datetime}, waiting {wait_seconds:.0f}s")
                
                await asyncio.sleep(wait_seconds)
                
                if self.running:
                    await self._generate_and_publish_report("daily")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Daily report loop error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _weekly_report_loop(self):
        """周报生成循环"""
        while self.running:
            try:
                now = datetime.now()
                days_until_friday = (self.weekly_report_day - now.weekday()) % 7
                if days_until_friday == 0 and now.hour >= 20:
                    days_until_friday = 7
                
                target_date = now.date() + timedelta(days=days_until_friday)
                target_datetime = datetime.combine(target_date, datetime.strptime("20:00", "%H:%M").time())
                
                wait_seconds = (target_datetime - now).total_seconds()
                logger.info(f"Next weekly report at {target_datetime}, waiting {wait_seconds:.0f}s")
                
                await asyncio.sleep(wait_seconds)
                
                if self.running:
                    await self._generate_and_publish_report("weekly")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Weekly report loop error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _monthly_report_loop(self):
        """月报生成循环"""
        while self.running:
            try:
                now = datetime.now()
                
                if now.day >= self.monthly_report_day and now.hour >= 20:
                    # 下个月
                    if now.month == 12:
                        target_date = datetime(now.year + 1, 1, self.monthly_report_day)
                    else:
                        target_date = datetime(now.year, now.month + 1, self.monthly_report_day)
                else:
                    target_date = datetime(now.year, now.month, self.monthly_report_day)
                
                target_datetime = target_date.replace(hour=20, minute=0, second=0)
                
                wait_seconds = (target_datetime - now).total_seconds()
                logger.info(f"Next monthly report at {target_datetime}, waiting {wait_seconds:.0f}s")
                
                await asyncio.sleep(wait_seconds)
                
                if self.running:
                    await self._generate_and_publish_report("monthly")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monthly report loop error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _generate_and_publish_report(self, report_type: str):
        """生成并发布报告"""
        try:
            logger.info(f"Generating {report_type} report...")
            
            if len(self.trade_history) < self.min_samples_for_analysis:
                logger.warning(f"Not enough trades for analysis: {len(self.trade_history)}")
                return
            
            # 筛选报告周期内的交易
            trades = self._get_trades_for_period(report_type)
            
            # 计算绩效指标
            metrics = self.metrics_calculator.calculate(
                trades, 
                self.initial_capital,
                self.risk_free_rate
            )
            
            # 策略归因分析
            attribution = self.attribution_analyzer.analyze(trades)
            
            # 风险分析
            risk_metrics = self.risk_analyzer.analyze(trades)
            
            # 生成建议
            recommendations = self._generate_recommendations(metrics, attribution, risk_metrics)
            
            # 组装报告
            report = self.report_generator.generate(
                report_type=report_type,
                timestamp=generate_timestamp(),
                metrics=metrics,
                attribution=attribution,
                risk_metrics=risk_metrics,
                recommendations=recommendations,
                trade_count=len(trades)
            )
            
            # 发布到Kafka
            self._publish_report(report)
            
            # 推送到飞书
            await self.feishu_publisher.publish(report)
            
            logger.info(f"{report_type} report generated and published")
            
        except Exception as e:
            logger.error(f"Error generating report: {e}", exc_info=True)
    
    def _get_trades_for_period(self, report_type: str) -> List[Dict]:
        """获取指定周期内的交易"""
        now = datetime.now()
        
        if report_type == "daily":
            start_date = now - timedelta(days=1)
        elif report_type == "weekly":
            start_date = now - timedelta(days=7)
        elif report_type == "monthly":
            start_date = now - timedelta(days=30)
        else:
            start_date = now - timedelta(days=1)
        
        return [
            t for t in self.trade_history
            if isinstance(t.get("timestamp"), datetime) and t["timestamp"] >= start_date
        ]
    
    def _generate_recommendations(
        self, 
        metrics: Dict, 
        attribution: Dict, 
        risk_metrics: Dict
    ) -> List[str]:
        """生成策略优化建议"""
        recommendations = []
        
        # 基于策略贡献度
        strategy_contributions = attribution.get("strategy_contributions", {})
        if strategy_contributions:
            best_strategy = max(strategy_contributions.items(), key=lambda x: x[1].get("contribution", 0))
            worst_strategy = min(strategy_contributions.items(), key=lambda x: x[1].get("contribution", 0))
            
            if best_strategy[1].get("contribution", 0) > 0:
                recommendations.append(
                    f"增加{best_strategy[0]}策略权重(当前贡献最高: {best_strategy[1]['contribution']:.2%})"
                )
            
            if worst_strategy[1].get("contribution", 0) < 0:
                recommendations.append(
                    f"优化{worst_strategy[0]}策略参数(当前贡献为负: {worst_strategy[1]['contribution']:.2%})"
                )
        
        # 基于风险指标
        if risk_metrics.get("var_95", 0) < -0.05:
            recommendations.append("VaR风险偏高，建议降低整体仓位")
        
        if metrics.get("sharpe_ratio", 0) < 1.0:
            recommendations.append("夏普比率偏低，建议优化风险调整后收益")
        
        if metrics.get("max_drawdown", 0) < -0.15:
            recommendations.append("最大回撤过大，建议加强止损管理")
        
        # 基于胜率
        if metrics.get("win_rate", 0) < 0.5:
            recommendations.append("胜率低于50%，建议优化入场信号质量")
        
        return recommendations
    
    def _publish_report(self, report: Dict):
        """发布绩效报告到Kafka"""
        message = {
            "msg_id": generate_msg_id(),
            "msg_type": "performance_report",
            "source_agent": self.agent_name,
            "target_agent": None,
            "timestamp": generate_timestamp(),
            "payload": report,
            "priority": 3
        }
        
        self.bus.send("am-hk-performance-reports", "all", message)
        self.bus.flush()
        
        logger.info(f"Published performance report to am-hk-performance-reports")
    
    def _publish_status(self, state: str):
        """发布Agent状态"""
        status = {
            "state": state,
            "history_size": len(self.trade_history),
        }
        self.bus.publish_status(status)
    
    async def _load_trade_history(self):
        """加载历史交易数据"""
        try:
            logger.info("Loading trade history...")
            logger.info(f"Loaded {len(self.trade_history)} historical trades")
        except Exception as e:
            logger.error(f"Failed to load trade history: {e}")
    
    async def _save_trade_history(self):
        """保存交易历史"""
        try:
            logger.info(f"Saving {len(self.trade_history)} trade records")
        except Exception as e:
            logger.error(f"Failed to save trade history: {e}")


if __name__ == "__main__":
    analyzer = PerformanceAnalyzer()
    asyncio.run(analyzer.start())
