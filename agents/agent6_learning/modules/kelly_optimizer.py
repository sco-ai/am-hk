"""
凯利公式仓位优化模块
计算最优仓位和风险管理参数
"""
import json
import logging
from typing import Dict, List, Optional, Tuple
from collections import deque
import numpy as np

from core.utils import setup_logging

logger = setup_logging("kelly_optimizer")


class KellyOptimizer:
    """
    凯利公式仓位优化器
    
    公式：f* = (p×b - q) / b
    其中:
        p = 胜率
        q = 败率 (1-p)
        b = 盈亏比 (平均盈利/平均亏损)
    
    功能：
    - 计算最优仓位比例
    - 计算半凯利、四分之一凯利仓位
    - 提供动态调整建议
    """
    
    def __init__(self):
        self.min_samples = 30  # 最小样本数
        self.max_position = 0.25  # 最大仓位限制
        self.min_position = 0.02  # 最小仓位
        self.kelly_fraction = 0.5  # 使用半凯利作为默认
        
        # 历史统计缓存
        self.symbol_stats: Dict[str, Dict] = {}
        
        logger.info("Kelly optimizer initialized")
    
    def optimize(self, trade_history: List[Dict], 
                 window_size: int = 100,
                 symbol: Optional[str] = None) -> Dict:
        """
        执行凯利公式优化
        
        Args:
            trade_history: 交易历史
            window_size: 统计窗口大小
            symbol: 特定标的（None则使用全部数据）
        
        Returns:
            {
                "optimal_position": float,  # 最优仓位
                "half_kelly": float,        # 半凯利仓位
                "quarter_kelly": float,     # 四分之一凯利
                "win_rate": float,          # 胜率
                "profit_loss_ratio": float, # 盈亏比
                "confidence": float,        # 置信度
                "risk_adjusted": bool,      # 是否经过风险调整
            }
        """
        try:
            # 筛选数据
            if symbol:
                trades = [t for t in trade_history if t.get("symbol") == symbol]
            else:
                trades = trade_history
            
            # 使用最近window_size条记录
            recent_trades = trades[-window_size:] if len(trades) > window_size else trades
            
            if len(recent_trades) < self.min_samples:
                logger.warning(f"Not enough trades for Kelly optimization: {len(recent_trades)}/{self.min_samples}")
                return self._default_result()
            
            # 计算基础统计
            pnls = [t.get("pnl", 0) for t in recent_trades if t.get("pnl") is not None]
            
            if len(pnls) < self.min_samples:
                return self._default_result()
            
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p <= 0]
            
            # 胜率
            win_rate = len(wins) / len(pnls) if pnls else 0.5
            
            # 盈亏比
            avg_profit = np.mean(wins) if wins else 0
            avg_loss = abs(np.mean(losses)) if losses else 1
            profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 1
            
            # 凯利公式计算
            q = 1 - win_rate  # 败率
            
            if profit_loss_ratio > 0:
                kelly_f = (win_rate * profit_loss_ratio - q) / profit_loss_ratio
            else:
                kelly_f = 0
            
            # 边界处理
            kelly_f = max(0, min(kelly_f, 1))
            
            # 应用限制
            half_kelly = kelly_f * 0.5
            quarter_kelly = kelly_f * 0.25
            
            # 应用最大最小限制
            optimal_position = max(self.min_position, 
                                 min(half_kelly * self.kelly_fraction, self.max_position))
            
            # 计算置信度（基于样本数量）
            confidence = min(1.0, len(pnls) / (self.min_samples * 3))
            
            # 风险调整标志
            risk_adjusted = optimal_position < kelly_f
            
            result = {
                "optimal_position": round(optimal_position, 4),
                "full_kelly": round(kelly_f, 4),
                "half_kelly": round(half_kelly, 4),
                "quarter_kelly": round(quarter_kelly, 4),
                "win_rate": round(win_rate, 4),
                "profit_loss_ratio": round(profit_loss_ratio, 4),
                "avg_profit": round(avg_profit, 4),
                "avg_loss": round(avg_loss, 4),
                "total_trades": len(pnls),
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "confidence": round(confidence, 4),
                "risk_adjusted": risk_adjusted,
                "symbol": symbol,
            }
            
            # 缓存统计
            if symbol:
                self.symbol_stats[symbol] = result
            
            logger.info(f"Kelly optimization: position={optimal_position:.2%}, "
                       f"win_rate={win_rate:.2%}, pl_ratio={profit_loss_ratio:.2f}")
            
            return result
        
        except Exception as e:
            logger.error(f"Kelly optimization error: {e}", exc_info=True)
            return self._default_result()
    
    def optimize_by_symbol(self, trade_history: List[Dict], 
                          window_size: int = 100) -> Dict[str, Dict]:
        """
        按标的分别优化
        """
        # 获取所有标的
        symbols = set(t.get("symbol") for t in trade_history if t.get("symbol"))
        
        results = {}
        for symbol in symbols:
            results[symbol] = self.optimize(trade_history, window_size, symbol)
        
        # 计算全局优化（所有标的）
        results["_global"] = self.optimize(trade_history, window_size, None)
        
        return results
    
    def calculate_expected_growth(self, kelly_result: Dict) -> float:
        """
        计算预期资金增长率
        
        G(f) = p*ln(1+bf) + q*ln(1-f)
        """
        p = kelly_result.get("win_rate", 0.5)
        q = 1 - p
        b = kelly_result.get("profit_loss_ratio", 1)
        f = kelly_result.get("optimal_position", 0)
        
        if f <= 0 or b <= 0:
            return 0
        
        expected_growth = p * np.log(1 + b * f) + q * np.log(1 - f)
        
        return expected_growth
    
    def calculate_drawdown_risk(self, kelly_result: Dict) -> Dict:
        """
        计算回撤风险
        
        基于凯利公式的回撤概率估计
        """
        f = kelly_result.get("optimal_position", 0)
        kelly_f = kelly_result.get("full_kelly", 0)
        
        # 简化的回撤估计
        if kelly_f > 0:
            overbet_ratio = f / kelly_f if kelly_f > 0 else 1
        else:
            overbet_ratio = 1
        
        # 回撤概率随仓位增加而增加
        drawdown_prob = min(0.5, overbet_ratio * 0.1)
        
        # 预期最大回撤
        expected_max_dd = f * 2  # 简化估计
        
        return {
            "drawdown_probability": round(drawdown_prob, 4),
            "expected_max_drawdown": round(expected_max_dd, 4),
            "overbet_ratio": round(overbet_ratio, 4),
            "risk_level": "high" if overbet_ratio > 1 else "medium" if overbet_ratio > 0.5 else "low",
        }
    
    def get_position_suggestion(self, symbol: str, 
                                current_position: float = 0) -> Dict:
        """
        获取仓位调整建议
        """
        stats = self.symbol_stats.get(symbol)
        
        if not stats:
            return {
                "suggested_position": 0.05,
                "action": "hold",
                "reason": "no_data",
            }
        
        optimal = stats.get("optimal_position", 0.05)
        confidence = stats.get("confidence", 0)
        
        # 根据当前仓位给出建议
        diff = optimal - current_position
        
        if abs(diff) < 0.01:
            action = "hold"
        elif diff > 0:
            action = "increase"
        else:
            action = "decrease"
        
        # 根据置信度调整建议强度
        if confidence < 0.3:
            action = "hold"
            reason = "low_confidence"
        elif stats.get("win_rate", 0) < 0.4:
            action = "decrease"
            reason = "low_win_rate"
        else:
            reason = "kelly_optimized"
        
        return {
            "suggested_position": round(optimal, 4),
            "current_position": round(current_position, 4),
            "action": action,
            "adjustment": round(diff, 4),
            "confidence": round(confidence, 4),
            "reason": reason,
        }
    
    def _default_result(self) -> Dict:
        """默认结果（样本不足时使用）"""
        return {
            "optimal_position": 0.05,
            "full_kelly": 0.1,
            "half_kelly": 0.05,
            "quarter_kelly": 0.025,
            "win_rate": 0.5,
            "profit_loss_ratio": 1.0,
            "avg_profit": 0,
            "avg_loss": 0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "confidence": 0,
            "risk_adjusted": True,
            "symbol": None,
        }


class DynamicPositionSizer:
    """
    动态仓位管理器
    
    结合凯利公式和市场状态动态调整仓位
    """
    
    def __init__(self, kelly_optimizer: KellyOptimizer):
        self.kelly = kelly_optimizer
        self.base_kelly_fraction = 0.5
        
        # 市场状态调整系数
        self.regime_multipliers = {
            "trending": 1.2,      # 趋势市场增加仓位
            "ranging": 0.8,       # 震荡市场减少仓位
            "volatile": 0.6,      # 高波动减少仓位
            "low_liquidity": 0.5, # 低流动性减少仓位
        }
    
    def calculate_position(self, 
                          symbol: str,
                          market_regime: str = "trending",
                          volatility_percentile: float = 0.5) -> Dict:
        """
        计算动态仓位
        """
        # 获取凯利优化结果
        kelly_result = self.kelly.symbol_stats.get(symbol)
        
        if not kelly_result:
            return {
                "position_size": 0.05,
                "method": "default",
            }
        
        base_position = kelly_result.get("optimal_position", 0.05)
        
        # 应用市场状态调整
        regime_mult = self.regime_multipliers.get(market_regime, 1.0)
        
        # 波动率调整
        if volatility_percentile > 0.8:
            vol_mult = 0.7
        elif volatility_percentile < 0.2:
            vol_mult = 1.1
        else:
            vol_mult = 1.0
        
        # 最终仓位
        final_position = base_position * regime_mult * vol_mult
        
        # 限制在合理范围内
        final_position = max(0.02, min(final_position, 0.25))
        
        return {
            "position_size": round(final_position, 4),
            "base_position": round(base_position, 4),
            "regime_multiplier": regime_mult,
            "volatility_multiplier": vol_mult,
            "method": "dynamic_kelly",
            "market_regime": market_regime,
        }