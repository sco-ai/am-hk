"""
绩效指标计算模块
计算各类绩效指标：收益率、夏普比率、最大回撤等
"""
import numpy as np
from typing import Dict, List
from datetime import datetime


class MetricsCalculator:
    """绩效指标计算器"""
    
    def __init__(self):
        pass
    
    def calculate(
        self, 
        trades: List[Dict], 
        initial_capital: float,
        risk_free_rate: float = 0.02
    ) -> Dict:
        """
        计算所有绩效指标
        
        Args:
            trades: 交易记录列表
            initial_capital: 初始资金
            risk_free_rate: 无风险利率（年化）
        
        Returns:
            绩效指标字典
        """
        if not trades:
            return self._empty_metrics()
        
        # 提取收益率序列
        returns = self._extract_returns(trades)
        pnl_list = [t.get("pnl", 0) for t in trades]
        
        # 基础统计
        total_trades = len(trades)
        winning_trades = [p for p in pnl_list if p > 0]
        losing_trades = [p for p in pnl_list if p < 0]
        
        # 计算各项指标
        metrics = {
            "total_return": self._calculate_total_return(pnl_list, initial_capital),
            "sharpe_ratio": self._calculate_sharpe_ratio(returns, risk_free_rate),
            "max_drawdown": self._calculate_max_drawdown(pnl_list, initial_capital),
            "win_rate": len(winning_trades) / total_trades if total_trades > 0 else 0,
            "profit_loss_ratio": self._calculate_pl_ratio(winning_trades, losing_trades),
            "sortino_ratio": self._calculate_sortino_ratio(returns, risk_free_rate),
            "calmar_ratio": self._calculate_calmar_ratio(returns, pnl_list, initial_capital),
            "alpha": 0.0,  # 需要基准数据
            "beta": 0.0,   # 需要基准数据
            "total_pnl": sum(pnl_list),
            "avg_pnl": np.mean(pnl_list) if pnl_list else 0,
            "avg_holding_time": self._calculate_avg_holding_time(trades),
            "total_slippage": sum(t.get("slippage", 0) for t in trades),
            "total_transaction_cost": sum(t.get("transaction_cost", 0) for t in trades),
        }
        
        return metrics
    
    def _empty_metrics(self) -> Dict:
        """返回空指标"""
        return {
            "total_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_loss_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "alpha": 0.0,
            "beta": 0.0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0,
            "avg_holding_time": 0.0,
            "total_slippage": 0.0,
            "total_transaction_cost": 0.0,
        }
    
    def _extract_returns(self, trades: List[Dict]) -> np.ndarray:
        """提取收益率序列"""
        returns = []
        for trade in trades:
            pnl_pct = trade.get("pnl_pct")
            if pnl_pct is not None:
                returns.append(pnl_pct)
            else:
                entry_price = trade.get("entry_price", 0)
                exit_price = trade.get("exit_price", 0)
                if entry_price and entry_price > 0:
                    returns.append((exit_price - entry_price) / entry_price)
        return np.array(returns) if returns else np.array([0.0])
    
    def _calculate_total_return(self, pnl_list: List[float], initial_capital: float) -> float:
        """计算总收益率"""
        total_pnl = sum(pnl_list)
        return total_pnl / initial_capital if initial_capital > 0 else 0.0
    
    def _calculate_sharpe_ratio(
        self, 
        returns: np.ndarray, 
        risk_free_rate: float
    ) -> float:
        """
        计算夏普比率
        Sharpe = (E[R] - Rf) / σ
        """
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        
        excess_return = np.mean(returns) - risk_free_rate / 252  # 日度无风险利率
        return excess_return / np.std(returns) * np.sqrt(252)  # 年化
    
    def _calculate_max_drawdown(
        self, 
        pnl_list: List[float], 
        initial_capital: float
    ) -> float:
        """
        计算最大回撤
        从峰值到谷底的最大跌幅
        """
        if not pnl_list or initial_capital <= 0:
            return 0.0
        
        # 累计权益曲线
        equity = [initial_capital]
        for pnl in pnl_list:
            equity.append(equity[-1] + pnl)
        
        equity = np.array(equity)
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        
        return float(np.min(drawdown))
    
    def _calculate_pl_ratio(
        self, 
        winning_trades: List[float], 
        losing_trades: List[float]
    ) -> float:
        """
        计算盈亏比
        平均盈利 / 平均亏损（绝对值）
        """
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = abs(np.mean(losing_trades)) if losing_trades else 1
        
        return avg_win / avg_loss if avg_loss > 0 else 0.0
    
    def _calculate_sortino_ratio(
        self, 
        returns: np.ndarray, 
        risk_free_rate: float
    ) -> float:
        """
        计算索提诺比率
        只考虑下行风险的夏普比率
        Sortino = (E[R] - Rf) / σd
        其中σd是下行标准差
        """
        if len(returns) == 0:
            return 0.0
        
        # 计算下行收益（负收益）
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf') if np.mean(returns) > risk_free_rate / 252 else 0.0
        
        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return 0.0
        
        excess_return = np.mean(returns) - risk_free_rate / 252
        return excess_return / downside_std * np.sqrt(252)
    
    def _calculate_calmar_ratio(
        self, 
        returns: np.ndarray,
        pnl_list: List[float],
        initial_capital: float
    ) -> float:
        """
        计算卡尔马比率
        年化收益 / 最大回撤
        """
        if len(returns) == 0 or initial_capital <= 0:
            return 0.0
        
        # 年化收益率（假设returns是日收益率）
        annual_return = np.mean(returns) * 252
        
        # 最大回撤
        max_dd = abs(self._calculate_max_drawdown(pnl_list, initial_capital))
        
        return annual_return / max_dd if max_dd > 0 else 0.0
    
    def calculate_alpha_beta(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray
    ) -> Dict[str, float]:
        """
        计算阿尔法和贝塔
        Alpha: 超额收益
        Beta: 系统性风险
        """
        if len(returns) == 0 or len(benchmark_returns) == 0:
            return {"alpha": 0.0, "beta": 0.0}
        
        # 确保长度一致
        min_len = min(len(returns), len(benchmark_returns))
        returns = returns[:min_len]
        benchmark_returns = benchmark_returns[:min_len]
        
        # 计算协方差和方差
        covariance = np.cov(returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns)
        
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 0
        alpha = np.mean(returns) - beta * np.mean(benchmark_returns)
        
        return {
            "alpha": alpha * 252,  # 年化
            "beta": beta
        }
    
    def _calculate_avg_holding_time(self, trades: List[Dict]) -> float:
        """计算平均持仓时间"""
        holding_times = [t.get("holding_time", 0) for t in trades if t.get("holding_time")]
        return np.mean(holding_times) if holding_times else 0.0
