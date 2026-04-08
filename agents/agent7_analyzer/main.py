"""
Agent 7: PerformanceAnalyzer（绩效分析器）

职责：
- 交易结果分析
- 绩效报告生成
- 策略归因分析
- 风险分析
- 向Agent6提供反馈数据
"""
import asyncio
import json
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict

from core.kafka import MessageBus, AgentConsumer
from core.models import TradeResult, PerformanceReport
from core.utils import setup_logging, generate_timestamp

logger = setup_logging("agent7_analyzer")


@dataclass
class PerformanceMetrics:
    """绩效指标"""
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    profit_loss_ratio: float = 0.0
    volatility: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    alpha: float = 0.0
    beta: float = 1.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class StrategyAttribution:
    """策略归因"""
    strategy_name: str
    contribution: float
    win_rate: float
    trade_count: int
    avg_return: float
    
    def to_dict(self) -> Dict:
        return asdict(self)


class PerformanceCalculator:
    """绩效计算引擎"""
    
    @staticmethod
    def calculate_returns(trades: List[Dict]) -> Tuple[float, float]:
        """计算总收益率和年化收益率"""
        if not trades:
            return 0.0, 0.0
        
        returns = [t.get("return_pct", 0) for t in trades]
        total_return = np.prod([1 + r for r in returns]) - 1
        
        # 假设交易日为252天
        days = max((max(t.get("exit_time", 0) for t in trades) - 
                   min(t.get("entry_time", 0) for t in trades)) / (24 * 3600 * 1000), 1)
        annualized_return = (1 + total_return) ** (252 / max(days, 1)) - 1
        
        return total_return, annualized_return
    
    @staticmethod
    def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
        """计算夏普比率"""
        if len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        excess_returns = returns_array - risk_free_rate / 252  # 日度无风险利率
        
        if np.std(excess_returns) == 0:
            return 0.0
        
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
    
    @staticmethod
    def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
        """计算索提诺比率（只考虑下行风险）"""
        if len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        excess_returns = returns_array - risk_free_rate / 252
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0 or np.std(downside_returns) == 0:
            return 0.0
        
        return np.mean(excess_returns) / np.std(downside_returns) * np.sqrt(252)
    
    @staticmethod
    def calculate_max_drawdown(equity_curve: List[float]) -> float:
        """计算最大回撤"""
        if len(equity_curve) < 2:
            return 0.0
        
        peak = equity_curve[0]
        max_dd = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    @staticmethod
    def calculate_win_rate(trades: List[Dict]) -> float:
        """计算胜率"""
        if not trades:
            return 0.0
        
        winning_trades = sum(1 for t in trades if t.get("pnl", 0) > 0)
        return winning_trades / len(trades)
    
    @staticmethod
    def calculate_profit_loss_ratio(trades: List[Dict]) -> float:
        """计算盈亏比"""
        winning_returns = [t.get("return_pct", 0) for t in trades if t.get("pnl", 0) > 0]
        losing_returns = [abs(t.get("return_pct", 0)) for t in trades if t.get("pnl", 0) < 0]
        
        if not losing_returns:
            return float('inf') if winning_returns else 0.0
        
        avg_profit = np.mean(winning_returns) if winning_returns else 0
        avg_loss = np.mean(losing_returns) if losing_returns else 0.001
        
        return avg_profit / avg_loss
    
    @staticmethod
    def calculate_var_cvar(returns: List[float], confidence: float = 0.95) -> Tuple[float, float]:
        """计算VaR和CVaR"""
        if len(returns) < 10:
            return 0.0, 0.0
        
        returns_array = np.array(returns)
        var = np.percentile(returns_array, (1 - confidence) * 100)
        
        # CVaR是超过VaR阈值的平均损失
        cvar = returns_array[returns_array <= var].mean() if var < 0 else var
        
        return var, cvar
    
    @staticmethod
    def calculate_beta_alpha(returns: List[float], benchmark_returns: List[float]) -> Tuple[float, float]:
        """计算Beta和Alpha"""
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 1.0, 0.0
        
        returns_array = np.array(returns)
        benchmark_array = np.array(benchmark_returns[:len(returns)])
        
        # 计算协方差和方差
        covariance = np.cov(returns_array, benchmark_array)[0][1]
        benchmark_variance = np.var(benchmark_array)
        
        if benchmark_variance == 0:
            beta = 1.0
        else:
            beta = covariance / benchmark_variance
        
        # Alpha = 实际收益 - Beta * 基准收益
        alpha = np.mean(returns_array) - beta * np.mean(benchmark_array)
        
        return beta, alpha


class StrategyAttributionAnalyzer:
    """策略归因分析器"""
    
    def analyze(self, trades: List[Dict]) -> Dict[str, StrategyAttribution]:
        """分析各策略的贡献度"""
        strategy_stats = defaultdict(lambda: {
            "returns": [],
            "pnl_list": [],
            "trades": []
        })
        
        # 按策略分组统计
        for trade in trades:
            strategy = trade.get("strategy", "unknown")
            strategy_stats[strategy]["returns"].append(trade.get("return_pct", 0))
            strategy_stats[strategy]["pnl_list"].append(trade.get("pnl", 0))
            strategy_stats[strategy]["trades"].append(trade)
        
        # 计算各策略的归因指标
        attributions = {}
        total_pnl = sum(t.get("pnl", 0) for t in trades) or 0.001
        
        for strategy, stats in strategy_stats.items():
            returns = stats["returns"]
            pnls = stats["pnl_list"]
            trade_list = stats["trades"]
            
            contribution = sum(pnls) / total_pnl if total_pnl != 0 else 0
            win_rate = sum(1 for p in pnls if p > 0) / len(pnls) if pnls else 0
            avg_return = np.mean(returns) if returns else 0
            
            attributions[strategy] = StrategyAttribution(
                strategy_name=strategy,
                contribution=round(contribution, 4),
                win_rate=round(win_rate, 4),
                trade_count=len(trade_list),
                avg_return=round(avg_return, 4)
            )
        
        return attributions


class PerformanceAnalyzer:
    """
    Agent 7: 绩效分析器
    
    核心功能：
    1. 绩效指标计算（夏普比率、最大回撤、胜率等）
    2. 策略归因分析
    3. 风险分析（VaR/CVaR）
    4. 报告生成和推送
    """
    
    def __init__(self):
        self.agent_name = "agent7_analyzer"
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-trade-results"]
        )
        
        # 组件
        self.calculator = PerformanceCalculator()
        self.attribution_analyzer = StrategyAttributionAnalyzer()
        
        # 数据存储
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = [1.0]  # 从1.0开始
        self.daily_returns: List[float] = []
        
        # 配置
        self.report_interval = 86400  # 日报：24小时
        self.last_report_time = 0
        self.running = False
        
        logger.info(f"{self.agent_name} initialized")
    
    async def start(self):
        """启动Agent7"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 注册消息处理器
        self.consumer.register_handler("trade_result", self._on_trade_result)
        
        # 启动定时报告任务
        report_task = asyncio.create_task(self._report_loop())
        
        try:
            self.consumer.start()
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
        finally:
            report_task.cancel()
            await self.stop()
    
    async def stop(self):
        """停止Agent7"""
        logger.info(f"{self.agent_name} stopping...")
        self.running = False
        self.consumer.stop()
        self.bus.close()
        logger.info(f"{self.agent_name} stopped")
    
    def _on_trade_result(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理交易结果"""
        try:
            # 存储交易数据
            self.trades.append(value)
            
            # 更新权益曲线
            pnl = value.get("pnl", 0)
            current_equity = self.equity_curve[-1] * (1 + pnl)
            self.equity_curve.append(current_equity)
            
            # 记录日收益
            self.daily_returns.append(pnl)
            
            logger.debug(f"Recorded trade: {value.get('symbol')} PnL={pnl:.4f}")
            
        except Exception as e:
            logger.error(f"Error processing trade result: {e}")
    
    async def _report_loop(self):
        """定期生成报告"""
        while self.running:
            try:
                current_time = int(datetime.now().timestamp())
                
                if current_time - self.last_report_time >= self.report_interval:
                    await self._generate_and_publish_report("daily")
                    self.last_report_time = current_time
                
                await asyncio.sleep(3600)  # 每小时检查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Report loop error: {e}")
                await asyncio.sleep(60)
    
    async def _generate_and_publish_report(self, report_type: str = "daily"):
        """生成并发布绩效报告"""
        if len(self.trades) < 1:
            logger.info("No trades to analyze yet")
            return
        
        try:
            # 计算绩效指标
            metrics = self._calculate_metrics()
            
            # 策略归因分析
            attributions = self.attribution_analyzer.analyze(self.trades)
            
            # 生成建议
            recommendations = self._generate_recommendations(metrics, attributions)
            
            # 构建报告
            report = {
                "report_type": report_type,
                "timestamp": generate_timestamp(),
                "period": {
                    "start": min(t.get("entry_time", 0) for t in self.trades),
                    "end": max(t.get("exit_time", 0) for t in self.trades),
                    "trade_count": len(self.trades)
                },
                "summary": metrics.to_dict(),
                "strategy_attribution": {
                    k: v.to_dict() for k, v in attributions.items()
                },
                "risk_metrics": {
                    "var_95": metrics.var_95,
                    "cvar_95": metrics.cvar_95,
                    "volatility": metrics.volatility
                },
                "recommendations": recommendations,
                "equity_curve_sample": self.equity_curve[-30:] if len(self.equity_curve) > 30 else self.equity_curve
            }
            
            # 发布报告
            self.bus.send(
                topic="am-hk-performance-reports",
                key=f"report_{report_type}",
                value=report
            )
            self.bus.flush()
            
            logger.info(f"Published {report_type} performance report: "
                       f"Return={metrics.total_return:.2%}, "
                       f"Sharpe={metrics.sharpe_ratio:.2f}, "
                       f"MaxDD={metrics.max_drawdown:.2%}")
            
        except Exception as e:
            logger.error(f"Error generating report: {e}", exc_info=True)
    
    def _calculate_metrics(self) -> PerformanceMetrics:
        """计算所有绩效指标"""
        returns = [t.get("return_pct", 0) for t in self.trades]
        
        total_return, annualized_return = self.calculator.calculate_returns(self.trades)
        sharpe = self.calculator.calculate_sharpe_ratio(returns)
        sortino = self.calculator.calculate_sortino_ratio(returns)
        max_dd = self.calculator.calculate_max_drawdown(self.equity_curve)
        win_rate = self.calculator.calculate_win_rate(self.trades)
        pl_ratio = self.calculator.calculate_profit_loss_ratio(self.trades)
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0
        var_95, cvar_95 = self.calculator.calculate_var_cvar(returns)
        
        # Calmar比率 = 年化收益 / 最大回撤
        calmar = annualized_return / abs(max_dd) if max_dd != 0 else 0
        
        return PerformanceMetrics(
            total_return=round(total_return, 4),
            annualized_return=round(annualized_return, 4),
            sharpe_ratio=round(sharpe, 4),
            sortino_ratio=round(sortino, 4),
            max_drawdown=round(max_dd, 4),
            calmar_ratio=round(calmar, 4),
            win_rate=round(win_rate, 4),
            profit_loss_ratio=round(pl_ratio, 4),
            volatility=round(volatility, 4),
            var_95=round(var_95, 4),
            cvar_95=round(cvar_95, 4),
            alpha=0.0,  # 需要基准数据
            beta=1.0
        )
    
    def _generate_recommendations(self, metrics: PerformanceMetrics, 
                                  attributions: Dict[str, StrategyAttribution]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 基于夏普比率的建议
        if metrics.sharpe_ratio < 1.0:
            recommendations.append(f"夏普比率偏低({metrics.sharpe_ratio:.2f})，建议优化风险控制")
        elif metrics.sharpe_ratio > 2.0:
            recommendations.append(f"夏普比率优秀({metrics.sharpe_ratio:.2f})，可适当增加仓位")
        
        # 基于最大回撤的建议
        if metrics.max_drawdown < -0.15:
            recommendations.append(f"最大回撤较大({metrics.max_drawdown:.1%})，建议收紧止损")
        
        # 基于胜率的建议
        if metrics.win_rate < 0.5:
            recommendations.append(f"胜率偏低({metrics.win_rate:.1%})，建议优化入场信号")
        
        # 基于策略归因的建议
        if attributions:
            best_strategy = max(attributions.items(), key=lambda x: x[1].contribution)
            worst_strategy = min(attributions.items(), key=lambda x: x[1].contribution)
            
            if best_strategy[1].contribution > 0.3:
                recommendations.append(f"{best_strategy[0]}策略贡献突出，建议适当增加权重")
            
            if worst_strategy[1].contribution < 0.05 and worst_strategy[1].win_rate < 0.5:
                recommendations.append(f"{worst_strategy[0]}策略表现较弱，建议优化或降低权重")
        
        # 基于VaR的建议
        if abs(metrics.var_95) > 0.03:
            recommendations.append(f"VaR较高({metrics.var_95:.2%})，注意尾部风险")
        
        return recommendations if recommendations else ["当前策略运行平稳，继续保持"]


if __name__ == "__main__":
    analyzer = PerformanceAnalyzer()
    asyncio.run(analyzer.start())
