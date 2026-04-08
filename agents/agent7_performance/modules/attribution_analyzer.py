"""
策略归因分析模块
分析各策略贡献度、因子暴露度等
"""
import numpy as np
from typing import Dict, List
from collections import defaultdict
from datetime import datetime


class AttributionAnalyzer:
    """策略归因分析器"""
    
    def __init__(self):
        self.strategies = ["momentum", "value", "sentiment", "cross_market"]
    
    def analyze(self, trades: List[Dict]) -> Dict:
        """
        执行策略归因分析
        
        Args:
            trades: 交易记录列表
        
        Returns:
            归因分析结果
        """
        if not trades:
            return self._empty_attribution()
        
        return {
            "strategy_contributions": self._analyze_strategy_contributions(trades),
            "factor_exposures": self._analyze_factor_exposures(trades),
            "time_analysis": self._analyze_time_dimension(trades),
            "market_condition_analysis": self._analyze_market_conditions(trades),
        }
    
    def _empty_attribution(self) -> Dict:
        """返回空归因结果"""
        return {
            "strategy_contributions": {},
            "factor_exposures": {},
            "time_analysis": {},
            "market_condition_analysis": {},
        }
    
    def _analyze_strategy_contributions(self, trades: List[Dict]) -> Dict[str, Dict]:
        """
        分析各策略贡献度
        """
        # 按策略分组
        strategy_trades = defaultdict(list)
        for trade in trades:
            strategy = trade.get("strategy", "unknown")
            strategy_trades[strategy].append(trade)
        
        contributions = {}
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        
        for strategy, strategy_trade_list in strategy_trades.items():
            pnls = [t.get("pnl", 0) for t in strategy_trade_list]
            winning = [p for p in pnls if p > 0]
            
            contribution = sum(pnls)
            contribution_pct = contribution / total_pnl if total_pnl != 0 else 0
            
            contributions[strategy] = {
                "contribution": contribution,
                "contribution_pct": contribution_pct,
                "trade_count": len(strategy_trade_list),
                "win_rate": len(winning) / len(pnls) if pnls else 0,
                "avg_pnl": np.mean(pnls) if pnls else 0,
                "total_pnl": contribution,
            }
        
        # 确保所有策略都有记录
        for strategy in self.strategies:
            if strategy not in contributions:
                contributions[strategy] = {
                    "contribution": 0.0,
                    "contribution_pct": 0.0,
                    "trade_count": 0,
                    "win_rate": 0.0,
                    "avg_pnl": 0.0,
                    "total_pnl": 0.0,
                }
        
        return contributions
    
    def _analyze_factor_exposures(self, trades: List[Dict]) -> Dict[str, Dict]:
        """
        分析因子暴露度
        """
        factor_stats = defaultdict(lambda: {"values": [], "pnls": []})
        
        for trade in trades:
            factors = trade.get("factors", {})
            pnl = trade.get("pnl", 0)
            
            for factor_name, factor_value in factors.items():
                factor_stats[factor_name]["values"].append(factor_value)
                factor_stats[factor_name]["pnls"].append(pnl)
        
        exposures = {}
        for factor_name, stats in factor_stats.items():
            values = stats["values"]
            pnls = stats["pnls"]
            
            if len(values) > 1:
                # 计算因子与收益的相关性
                correlation = np.corrcoef(values, pnls)[0, 1] if np.std(values) > 0 else 0
                
                exposures[factor_name] = {
                    "mean_exposure": np.mean(values),
                    "std_exposure": np.std(values),
                    "pnl_correlation": correlation,
                    "contribution": np.mean(pnls),
                }
        
        return exposures
    
    def _analyze_time_dimension(self, trades: List[Dict]) -> Dict:
        """
        时间维度分析（日/周/月）
        """
        # 按日期分组
        daily_pnl = defaultdict(float)
        hourly_pnl = defaultdict(float)
        weekday_pnl = defaultdict(float)
        
        for trade in trades:
            timestamp = trade.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    continue
            
            if not isinstance(timestamp, datetime):
                continue
            
            pnl = trade.get("pnl", 0)
            date_key = timestamp.strftime("%Y-%m-%d")
            hour_key = timestamp.hour
            weekday_key = timestamp.strftime("%A")
            
            daily_pnl[date_key] += pnl
            hourly_pnl[hour_key] += pnl
            weekday_pnl[weekday_key] += pnl
        
        return {
            "daily_pnl": dict(daily_pnl),
            "hourly_performance": {
                str(h): {"total_pnl": pnl, "trade_count": 0} 
                for h, pnl in hourly_pnl.items()
            },
            "weekday_performance": {
                d: {"total_pnl": pnl, "trade_count": 0} 
                for d, pnl in weekday_pnl.items()
            },
            "best_day": max(daily_pnl.items(), key=lambda x: x[1]) if daily_pnl else None,
            "worst_day": min(daily_pnl.items(), key=lambda x: x[1]) if daily_pnl else None,
        }
    
    def _analyze_market_conditions(self, trades: List[Dict]) -> Dict:
        """
        市场环境适应性分析
        """
        condition_stats = defaultdict(lambda: {"pnls": [], "count": 0})
        
        for trade in trades:
            market_condition = trade.get("market_condition", {})
            pnl = trade.get("pnl", 0)
            
            # 基于市场条件分类
            volatility = market_condition.get("volatility", "medium")
            trend = market_condition.get("trend", "neutral")
            
            key = f"{trend}_{volatility}"
            condition_stats[key]["pnls"].append(pnl)
            condition_stats[key]["count"] += 1
        
        analysis = {}
        for condition, stats in condition_stats.items():
            pnls = stats["pnls"]
            analysis[condition] = {
                "total_pnl": sum(pnls),
                "avg_pnl": np.mean(pnls) if pnls else 0,
                "win_rate": len([p for p in pnls if p > 0]) / len(pnls) if pnls else 0,
                "trade_count": stats["count"],
            }
        
        return analysis
    
    def get_strategy_recommendations(self, attribution: Dict) -> List[str]:
        """
        基于归因分析生成策略建议
        """
        recommendations = []
        
        contributions = attribution.get("strategy_contributions", {})
        
        # 找出表现最好和最差的策略
        sorted_strategies = sorted(
            contributions.items(),
            key=lambda x: x[1].get("contribution", 0),
            reverse=True
        )
        
        if sorted_strategies:
            best = sorted_strategies[0]
            worst = sorted_strategies[-1]
            
            if best[1].get("contribution", 0) > 0:
                recommendations.append(
                    f"{best[0]}策略表现优异，建议增加权重"
                )
            
            if worst[1].get("contribution", 0) < 0:
                recommendations.append(
                    f"{worst[0]}策略表现不佳，建议检查或暂停"
                )
        
        # 基于时间维度分析
        time_analysis = attribution.get("time_analysis", {})
        hourly_perf = time_analysis.get("hourly_performance", {})
        
        if hourly_perf:
            # 找出最佳交易时段
            best_hour = max(hourly_perf.items(), key=lambda x: x[1].get("total_pnl", 0))
            worst_hour = min(hourly_perf.items(), key=lambda x: x[1].get("total_pnl", 0))
            
            recommendations.append(
                f"{best_hour[0]}时交易表现最佳，建议重点关注"
            )
        
        return recommendations
