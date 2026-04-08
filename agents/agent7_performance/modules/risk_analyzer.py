"""
风险分析模块
计算VaR、CVaR、波动率、尾部风险等
"""
import numpy as np
from typing import Dict, List, Tuple
from scipy import stats


class RiskAnalyzer:
    """风险分析器"""
    
    def __init__(self):
        self.confidence_levels = [0.90, 0.95, 0.99]
    
    def analyze(self, trades: List[Dict]) -> Dict:
        """
        执行风险分析
        
        Args:
            trades: 交易记录列表
        
        Returns:
            风险指标字典
        """
        if not trades:
            return self._empty_risk_metrics()
        
        # 提取收益率序列
        returns = self._extract_returns(trades)
        pnls = np.array([t.get("pnl", 0) for t in trades])
        
        return {
            "var": self._calculate_var(returns),
            "cvar": self._calculate_cvar(returns),
            "volatility": self._calculate_volatility(returns),
            "tail_risk": self._analyze_tail_risk(returns),
            "concentration_risk": self._analyze_concentration_risk(trades),
            "drawdown_analysis": self._analyze_drawdowns(pnls),
        }
    
    def _empty_risk_metrics(self) -> Dict:
        """返回空风险指标"""
        return {
            "var": {},
            "cvar": {},
            "volatility": 0.0,
            "tail_risk": {},
            "concentration_risk": {},
            "drawdown_analysis": {},
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
    
    def _calculate_var(self, returns: np.ndarray) -> Dict[str, float]:
        """
        计算VaR (Value at Risk)
        在特定置信水平下的最大预期损失
        
        方法：
        1. 历史模拟法
        2. 参数法（正态分布）
        """
        if len(returns) == 0:
            return {}
        
        var_results = {}
        
        for confidence in self.confidence_levels:
            alpha = 1 - confidence
            
            # 历史模拟法
            historical_var = np.percentile(returns, alpha * 100)
            
            # 参数法（假设正态分布）
            mean = np.mean(returns)
            std = np.std(returns)
            parametric_var = stats.norm.ppf(alpha, mean, std)
            
            var_results[f"var_{int(confidence*100)}_historical"] = float(historical_var)
            var_results[f"var_{int(confidence*100)}_parametric"] = float(parametric_var)
        
        return var_results
    
    def _calculate_cvar(self, returns: np.ndarray) -> Dict[str, float]:
        """
        计算CVaR/ES (Conditional Value at Risk / Expected Shortfall)
        超过VaR阈值时的平均损失
        """
        if len(returns) == 0:
            return {}
        
        cvar_results = {}
        
        for confidence in self.confidence_levels:
            alpha = 1 - confidence
            
            # 历史模拟法
            var_threshold = np.percentile(returns, alpha * 100)
            tail_losses = returns[returns <= var_threshold]
            historical_cvar = np.mean(tail_losses) if len(tail_losses) > 0 else var_threshold
            
            # 参数法
            mean = np.mean(returns)
            std = np.std(returns)
            # ES = μ - σ * φ(Φ^-1(α)) / α
            z_score = stats.norm.ppf(alpha)
            parametric_cvar = mean - std * stats.norm.pdf(z_score) / alpha
            
            cvar_results[f"cvar_{int(confidence*100)}_historical"] = float(historical_cvar)
            cvar_results[f"cvar_{int(confidence*100)}_parametric"] = float(parametric_cvar)
        
        return cvar_results
    
    def _calculate_volatility(self, returns: np.ndarray) -> float:
        """
        计算波动率（标准差）
        """
        if len(returns) == 0:
            return 0.0
        
        return float(np.std(returns) * np.sqrt(252))  # 年化波动率
    
    def _analyze_tail_risk(self, returns: np.ndarray) -> Dict:
        """
        尾部风险分析
        """
        if len(returns) < 10:
            return {}
        
        # 偏度（Skewness）
        skewness = stats.skew(returns)
        
        # 峰度（Kurtosis）
        kurtosis = stats.kurtosis(returns)
        
        # 极值分析
        sorted_returns = np.sort(returns)
        n = len(sorted_returns)
        
        # 最差5%的平均损失
        worst_5pct = sorted_returns[:int(n * 0.05)]
        avg_worst_5pct = np.mean(worst_5pct) if len(worst_5pct) > 0 else 0
        
        # 最好5%的平均收益
        best_5pct = sorted_returns[int(n * 0.95):]
        avg_best_5pct = np.mean(best_5pct) if len(best_5pct) > 0 else 0
        
        # 极值比率
        extreme_ratio = abs(avg_worst_5pct) / abs(avg_best_5pct) if avg_best_5pct != 0 else float('inf')
        
        return {
            "skewness": float(skewness),
            "kurtosis": float(kurtosis),
            "is_heavy_tailed": kurtosis > 3,  # 厚尾分布
            "is_negative_skewed": skewness < 0,  # 负偏（左偏，损失风险更大）
            "avg_worst_5pct": float(avg_worst_5pct),
            "avg_best_5pct": float(avg_best_5pct),
            "extreme_loss_ratio": float(extreme_ratio),
            "max_loss": float(np.min(returns)),
            "max_gain": float(np.max(returns)),
        }
    
    def _analyze_concentration_risk(self, trades: List[Dict]) -> Dict:
        """
        集中度风险分析
        """
        if not trades:
            return {}
        
        # 按标的分析
        symbol_pnls = {}
        for trade in trades:
            symbol = trade.get("symbol", "unknown")
            pnl = trade.get("pnl", 0)
            symbol_pnls[symbol] = symbol_pnls.get(symbol, 0) + pnl
        
        total_pnl = sum(symbol_pnls.values())
        
        # 计算赫芬达尔指数（HHI）
        if total_pnl != 0 and len(symbol_pnls) > 0:
            shares = [abs(pnl / total_pnl) for pnl in symbol_pnls.values()]
            hhi = sum(s ** 2 for s in shares)
        else:
            hhi = 0
        
        # 最大单一标的风险
        max_symbol = max(symbol_pnls.items(), key=lambda x: abs(x[1])) if symbol_pnls else (None, 0)
        
        return {
            "symbol_concentration_hhi": float(hhi),
            "concentration_level": "high" if hhi > 0.25 else "medium" if hhi > 0.15 else "low",
            "max_single_symbol": max_symbol[0] if max_symbol[0] else None,
            "max_single_symbol_pnl": max_symbol[1] if max_symbol[0] else 0,
            "unique_symbols": len(symbol_pnls),
        }
    
    def _analyze_drawdowns(self, pnls: np.ndarray) -> Dict:
        """
        回撤分析
        """
        if len(pnls) == 0:
            return {}
        
        # 累计收益曲线
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / (running_max + 1e-10)
        
        # 识别回撤期
        is_in_drawdown = drawdowns < -0.001  # 小于-0.1%认为在回撤中
        
        # 找出所有回撤期
        drawdown_periods = []
        in_dd = False
        start_idx = 0
        
        for i, is_dd in enumerate(is_in_drawdown):
            if is_dd and not in_dd:
                in_dd = True
                start_idx = i
            elif not is_dd and in_dd:
                in_dd = False
                end_idx = i
                max_dd = np.min(drawdowns[start_idx:end_idx])
                drawdown_periods.append({
                    "start": start_idx,
                    "end": end_idx,
                    "duration": end_idx - start_idx,
                    "max_drawdown": float(max_dd),
                })
        
        # 当前状态
        current_drawdown = float(drawdowns[-1]) if len(drawdowns) > 0 else 0
        
        # 回撤统计
        if drawdown_periods:
            avg_duration = np.mean([d["duration"] for d in drawdown_periods])
            max_dd_ever = min([d["max_drawdown"] for d in drawdown_periods])
        else:
            avg_duration = 0
            max_dd_ever = 0
        
        return {
            "current_drawdown": current_drawdown,
            "max_drawdown_ever": float(max_dd_ever),
            "avg_drawdown_duration": float(avg_duration),
            "drawdown_count": len(drawdown_periods),
            "in_drawdown": current_drawdown < -0.001,
            "recovery_status": "recovered" if current_drawdown >= -0.001 else "in_drawdown",
        }
    
    def calculate_stress_test(
        self, 
        returns: np.ndarray,
        scenarios: List[Dict]
    ) -> Dict[str, float]:
        """
        压力测试
        
        Args:
            returns: 历史收益率
            scenarios: 压力情景列表
        
        Returns:
            各情景下的预期损失
        """
        results = {}
        
        for scenario in scenarios:
            name = scenario.get("name", "unnamed")
            shock = scenario.get("shock", 0)
            
            # 应用冲击
            stressed_returns = returns * (1 + shock)
            
            # 计算压力下的VaR
            var_95 = np.percentile(stressed_returns, 5)
            
            results[name] = {
                "var_95": float(var_95),
                "expected_loss": float(np.mean(stressed_returns[stressed_returns < 0])),
            }
        
        return results
