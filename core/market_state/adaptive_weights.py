"""
自适应权重调整器 - Adaptive Weights
根据市场状态动态调整策略权重
"""
import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AdaptiveWeightsResult:
    """自适应权重结果"""
    strategy_weights: Dict[str, float]  # 各策略权重
    factor_weights: Dict[str, float]    # 各因子权重
    position_multiplier: float          # 仓位乘数
    
    # 调整原因
    market_regime: str
    volatility_regime: str
    reasoning: str
    
    timestamp: datetime


class AdaptiveWeightAdjuster:
    """
    自适应权重调整器
    
    根据市场状态动态调整策略和因子权重
    """
    
    # 策略基础权重
    BASE_STRATEGY_WEIGHTS = {
        "trend_following": 0.30,
        "mean_reversion": 0.20,
        "momentum": 0.25,
        "breakout": 0.15,
        "liquidity": 0.10,
    }
    
    # 因子基础权重
    BASE_FACTOR_WEIGHTS = {
        "trend": 0.25,
        "volatility": 0.20,
        "liquidity": 0.20,
        "crypto_specific": 0.25,
        "sentiment": 0.10,
    }
    
    def __init__(self):
        self.current_weights: Optional[AdaptiveWeightsResult] = None
        self.adjustment_history: List[AdaptiveWeightsResult] = []
        self.max_history = 100
    
    def adjust_weights(
        self,
        market_state: str,  # bull/bear/range/transition
        volatility_regime: str,  # very_low/low/normal/high/extreme
        trend_strength: float = 0.5,
        recent_performance: Optional[Dict[str, float]] = None
    ) -> AdaptiveWeightsResult:
        """
        调整权重
        
        Args:
            market_state: 市场状态
            volatility_regime: 波动率状态
            trend_strength: 趋势强度
            recent_performance: 各策略近期表现
            
        Returns:
            AdaptiveWeightsResult
        """
        timestamp = datetime.now()
        
        # 复制基础权重
        strategy_weights = self.BASE_STRATEGY_WEIGHTS.copy()
        factor_weights = self.BASE_FACTOR_WEIGHTS.copy()
        
        # 根据市场状态调整
        strategy_weights, factor_weights = self._adjust_for_market_state(
            strategy_weights, factor_weights, market_state, trend_strength
        )
        
        # 根据波动率调整
        strategy_weights, factor_weights, position_mult = self._adjust_for_volatility(
            strategy_weights, factor_weights, volatility_regime
        )
        
        # 根据表现调整
        if recent_performance:
            strategy_weights = self._adjust_for_performance(
                strategy_weights, recent_performance
            )
        
        # 归一化
        strategy_weights = self._normalize(strategy_weights)
        factor_weights = self._normalize(factor_weights)
        
        # 生成推理
        reasoning = self._generate_reasoning(
            market_state, volatility_regime, trend_strength
        )
        
        result = AdaptiveWeightsResult(
            strategy_weights=strategy_weights,
            factor_weights=factor_weights,
            position_multiplier=position_mult,
            market_regime=market_state,
            volatility_regime=volatility_regime,
            reasoning=reasoning,
            timestamp=timestamp
        )
        
        self.current_weights = result
        self.adjustment_history.append(result)
        
        if len(self.adjustment_history) > self.max_history:
            self.adjustment_history = self.adjustment_history[-self.max_history:]
        
        return result
    
    def _adjust_for_market_state(
        self,
        strategy_weights: Dict[str, float],
        factor_weights: Dict[str, float],
        market_state: str,
        trend_strength: float
    ) -> tuple:
        """根据市场状态调整"""
        if market_state == "bull":
            # 牛市: 加大趋势和动量权重
            strategy_weights["trend_following"] *= 1.3
            strategy_weights["momentum"] *= 1.2
            strategy_weights["mean_reversion"] *= 0.7
            
            factor_weights["trend"] *= 1.2
            factor_weights["crypto_specific"] *= 1.1
            
        elif market_state == "bear":
            # 熊市: 加大均值回归和流动性权重
            strategy_weights["mean_reversion"] *= 1.3
            strategy_weights["liquidity"] *= 1.2
            strategy_weights["trend_following"] *= 0.8
            
            factor_weights["volatility"] *= 1.2
            factor_weights["liquidity"] *= 1.2
            
        elif market_state == "range":
            # 震荡: 加大均值回归和突破权重
            strategy_weights["mean_reversion"] *= 1.4
            strategy_weights["breakout"] *= 1.2
            strategy_weights["momentum"] *= 0.7
            
            factor_weights["volatility"] *= 1.1
            factor_weights["sentiment"] *= 0.8
            
        elif market_state == "transition":
            # 转换期: 均衡配置,降低仓位
            for k in strategy_weights:
                strategy_weights[k] *= 0.9
            
            factor_weights["trend"] *= 1.1
            factor_weights["sentiment"] *= 1.2
        
        return strategy_weights, factor_weights
    
    def _adjust_for_volatility(
        self,
        strategy_weights: Dict[str, float],
        factor_weights: Dict[str, float],
        vol_regime: str
    ) -> tuple:
        """根据波动率调整"""
        position_mult = 1.0
        
        if vol_regime == "very_low":
            # 极低波动: 可以加杠杆,关注突破
            strategy_weights["breakout"] *= 1.2
            position_mult = 1.3
            
        elif vol_regime == "low":
            # 低波动: 正常交易
            position_mult = 1.1
            
        elif vol_regime == "normal":
            # 正常波动: 标准配置
            position_mult = 1.0
            
        elif vol_regime == "high":
            # 高波动: 降低趋势,增加均值回归
            strategy_weights["trend_following"] *= 0.8
            strategy_weights["mean_reversion"] *= 1.1
            strategy_weights["momentum"] *= 0.8
            
            factor_weights["volatility"] *= 1.3
            
            position_mult = 0.6
            
        elif vol_regime == "extreme":
            # 极端波动: 大幅降低仓位,关注流动性
            for k in strategy_weights:
                strategy_weights[k] *= 0.8
            
            strategy_weights["liquidity"] *= 1.3
            
            factor_weights["liquidity"] *= 1.4
            factor_weights["volatility"] *= 1.3
            
            position_mult = 0.3
        
        return strategy_weights, factor_weights, position_mult
    
    def _adjust_for_performance(
        self,
        strategy_weights: Dict[str, float],
        performance: Dict[str, float]
    ) -> Dict[str, float]:
        """根据表现调整"""
        # 基于夏普比率调整
        total_perf = sum(max(0, p) for p in performance.values())
        
        if total_perf > 0:
            for strategy in strategy_weights:
                if strategy in performance:
                    # 表现好的策略增加权重
                    adj_factor = 0.8 + 0.4 * (max(0, performance[strategy]) / total_perf)
                    strategy_weights[strategy] *= adj_factor
        
        return strategy_weights
    
    def _normalize(self, weights: Dict[str, float]) -> Dict[str, float]:
        """归一化权重"""
        total = sum(weights.values())
        if total > 0:
            return {k: round(v / total, 4) for k, v in weights.items()}
        return weights
    
    def _generate_reasoning(
        self,
        market_state: str,
        vol_regime: str,
        trend_strength: float
    ) -> str:
        """生成推理说明"""
        reasons = []
        
        state_names = {
            "bull": "牛市",
            "bear": "熊市",
            "range": "震荡",
            "transition": "转换期",
        }
        
        vol_names = {
            "very_low": "极低波动",
            "low": "低波动",
            "normal": "正常波动",
            "high": "高波动",
            "extreme": "极端波动",
        }
        
        reasons.append(f"市场状态:{state_names.get(market_state, market_state)}")
        reasons.append(f"波动环境:{vol_names.get(vol_regime, vol_regime)}")
        
        if abs(trend_strength) > 0.5:
            direction = "强" if trend_strength > 0 else "弱"
            reasons.append(f"趋势{direction}")
        
        return "; ".join(reasons)
    
    def get_current_weights(self) -> Optional[AdaptiveWeightsResult]:
        """获取当前权重"""
        return self.current_weights


# 全局实例
adaptive_weight_adjuster = AdaptiveWeightAdjuster()
