"""
波动率状态检测器 - Volatility Regime
检测当前波动率环境
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class VolRegime(Enum):
    """波动率状态"""
    VERY_LOW = "very_low"      # < 5%
    LOW = "low"                # 5-15%
    NORMAL = "normal"          # 15-35%
    HIGH = "high"              # 35-60%
    EXTREME = "extreme"        # > 60%


@dataclass
class VolatilityStateResult:
    """波动率状态结果"""
    regime: VolRegime
    current_vol: float  # 当前波动率 (%)
    historical_vol: float  # 历史平均波动率 (%)
    vol_ratio: float  # 当前/历史比率
    
    # 预测
    forecast_vol: float
    forecast_confidence: float
    
    # 统计
    percentile: float  # 历史百分位
    zscore: float  # Z分数
    
    # 建议
    position_adjustment: float  # 仓位调整建议
    reasoning: str
    timestamp: datetime


class VolatilityRegimeDetector:
    """
    波动率状态检测器
    
    检测当前波动率环境并给出交易建议
    """
    
    # 波动率阈值 (年化, %)
    VOL_THRESHOLDS = {
        "very_low": 5,
        "low": 15,
        "normal": 35,
        "high": 60,
    }
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self.vol_history: Dict[str, List[float]] = {}
        self.current_states: Dict[str, VolatilityStateResult] = {}
    
    def detect(
        self,
        symbol: str,
        returns: pd.Series,
        window: int = 24  # 默认24个周期 (假设1小时数据)
    ) -> VolatilityStateResult:
        """
        检测波动率状态
        
        Args:
            symbol: 交易对
            returns: 收益率序列
            window: 计算窗口
            
        Returns:
            VolatilityStateResult
        """
        if len(returns) < window:
            return VolatilityStateResult(
                regime=VolRegime.NORMAL,
                current_vol=0.0,
                historical_vol=0.0,
                vol_ratio=1.0,
                forecast_vol=0.0,
                forecast_confidence=0.0,
                percentile=0.5,
                zscore=0.0,
                position_adjustment=1.0,
                reasoning="数据不足",
                timestamp=datetime.now()
            )
        
        # 计算当前波动率 (年化)
        current_vol = returns.iloc[-window:].std() * np.sqrt(365 * 24) * 100
        
        # 保存历史
        if symbol not in self.vol_history:
            self.vol_history[symbol] = []
        
        self.vol_history[symbol].append(current_vol)
        if len(self.vol_history[symbol]) > self.history_size:
            self.vol_history[symbol] = self.vol_history[symbol][-self.history_size:]
        
        history = self.vol_history[symbol]
        
        # 历史波动率
        historical_vol = np.mean(history[:-1]) if len(history) > 1 else current_vol
        
        # 波动率比率
        vol_ratio = current_vol / historical_vol if historical_vol > 0 else 1.0
        
        # 确定状态
        regime = self._determine_regime(current_vol)
        
        # 计算百分位和Z分数
        percentile, zscore = self._calculate_stats(current_vol, history)
        
        # 预测
        forecast_vol, forecast_conf = self._forecast_volatility(history)
        
        # 仓位调整建议
        position_adj = self._calculate_position_adjustment(regime, vol_ratio)
        
        # 推理
        reasoning = self._generate_reasoning(regime, current_vol, vol_ratio)
        
        result = VolatilityStateResult(
            regime=regime,
            current_vol=current_vol,
            historical_vol=historical_vol,
            vol_ratio=vol_ratio,
            forecast_vol=forecast_vol,
            forecast_confidence=forecast_conf,
            percentile=percentile,
            zscore=zscore,
            position_adjustment=position_adj,
            reasoning=reasoning,
            timestamp=datetime.now()
        )
        
        self.current_states[symbol] = result
        
        return result
    
    def _determine_regime(self, vol: float) -> VolRegime:
        """确定波动率状态"""
        if vol < self.VOL_THRESHOLDS["very_low"]:
            return VolRegime.VERY_LOW
        elif vol < self.VOL_THRESHOLDS["low"]:
            return VolRegime.LOW
        elif vol < self.VOL_THRESHOLDS["normal"]:
            return VolRegime.NORMAL
        elif vol < self.VOL_THRESHOLDS["high"]:
            return VolRegime.HIGH
        else:
            return VolRegime.EXTREME
    
    def _calculate_stats(
        self,
        current: float,
        history: List[float]
    ) -> Tuple[float, float]:
        """计算统计指标"""
        if len(history) < 2:
            return 0.5, 0.0
        
        # 百分位
        sorted_hist = sorted(history[:-1])  # 排除当前值
        percentile = sum(1 for v in sorted_hist if v < current) / len(sorted_hist)
        
        # Z分数
        mean = np.mean(history[:-1])
        std = np.std(history[:-1])
        zscore = (current - mean) / std if std > 0 else 0
        
        return percentile, zscore
    
    def _forecast_volatility(
        self,
        history: List[float]
    ) -> Tuple[float, float]:
        """简单波动率预测"""
        if len(history) < 5:
            return history[-1] if history else 0.0, 0.0
        
        # EWMA预测
        lambda_param = 0.94
        forecast = history[-1]
        
        for vol in reversed(history[-5:-1]):
            forecast = lambda_param * forecast + (1 - lambda_param) * vol
        
        # 均值回归调整
        mean_vol = np.mean(history)
        forecast = 0.7 * forecast + 0.3 * mean_vol
        
        # 置信度基于历史稳定性
        std_vol = np.std(history)
        confidence = max(0, 1 - std_vol / mean_vol) if mean_vol > 0 else 0.5
        
        return forecast, confidence
    
    def _calculate_position_adjustment(
        self,
        regime: VolRegime,
        vol_ratio: float
    ) -> float:
        """计算仓位调整建议"""
        # 基础调整
        adjustments = {
            VolRegime.VERY_LOW: 1.2,   # 低波动可以加大仓位
            VolRegime.LOW: 1.1,
            VolRegime.NORMAL: 1.0,
            VolRegime.HIGH: 0.6,       # 高波动降低仓位
            VolRegime.EXTREME: 0.3,    # 极端波动大幅降低
        }
        
        base_adj = adjustments.get(regime, 1.0)
        
        # 基于比率微调
        if vol_ratio > 1.5:  # 波动率快速上升
            base_adj *= 0.8
        elif vol_ratio < 0.7:  # 波动率快速下降
            base_adj *= 1.1
        
        return round(max(0.1, min(1.5, base_adj)), 2)
    
    def _generate_reasoning(
        self,
        regime: VolRegime,
        current_vol: float,
        vol_ratio: float
    ) -> str:
        """生成推理说明"""
        reasons = []
        
        regime_names = {
            VolRegime.VERY_LOW: "极低波动",
            VolRegime.LOW: "低波动",
            VolRegime.NORMAL: "正常波动",
            VolRegime.HIGH: "高波动",
            VolRegime.EXTREME: "极端波动",
        }
        
        reasons.append(f"当前{regime_names.get(regime, '未知')}")
        reasons.append(f"波动率{current_vol:.1f}%")
        
        if vol_ratio > 1.5:
            reasons.append("波动率快速上升")
        elif vol_ratio < 0.7:
            reasons.append("波动率快速下降")
        
        return "; ".join(reasons)
    
    def get_current_state(self, symbol: str) -> Optional[VolatilityStateResult]:
        """获取当前状态"""
        return self.current_states.get(symbol)


# 全局实例
volatility_regime_detector = VolatilityRegimeDetector()
