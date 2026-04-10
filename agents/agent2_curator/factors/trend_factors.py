"""
趋势因子模块 - Trend Factors
包含: MA交叉、MACD、动量指标
"""
import numpy as np
import pandas as pd
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass
from enum import Enum


class TrendDirection(Enum):
    """趋势方向"""
    STRONG_UP = "strong_up"
    UP = "up"
    NEUTRAL = "neutral"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


@dataclass
class MACDResult:
    """MACD计算结果"""
    macd: float
    signal: float
    histogram: float
    trend: str
    divergence: float  # 背离程度


@dataclass
class MACrossResult:
    """均线交叉结果"""
    fast_ma: float
    slow_ma: float
    cross_type: Optional[str]  # "golden", "death", None
    cross_strength: float  # 交叉强度 0-1
    distance_pct: float  # 均线间距百分比


@dataclass
class MomentumResult:
    """动量计算结果"""
    momentum: float
    acceleration: float
    momentum_roc: float  # 动量变化率
    strength: float  # 动量强度 0-1


class TrendFactors:
    """趋势因子计算器"""
    
    def __init__(self):
        self.price_history: Dict[str, List[float]] = {}
        self.macd_history: Dict[str, List[float]] = {}
        self.max_history = 200
    
    def calculate_ma_cross(
        self, 
        prices: pd.Series, 
        fast_period: int = 5, 
        slow_period: int = 20
    ) -> MACrossResult:
        """
        计算均线交叉信号
        
        Args:
            prices: 价格序列
            fast_period: 快线周期
            slow_period: 慢线周期
            
        Returns:
            MACrossResult
        """
        if len(prices) < slow_period:
            return MACrossResult(
                fast_ma=prices.iloc[-1] if len(prices) > 0 else 0,
                slow_ma=prices.iloc[-1] if len(prices) > 0 else 0,
                cross_type=None,
                cross_strength=0.0,
                distance_pct=0.0
            )
        
        fast_ma = prices.iloc[-fast_period:].mean()
        slow_ma = prices.iloc[-slow_period:].mean()
        
        # 计算均线间距百分比
        distance_pct = (fast_ma - slow_ma) / slow_ma * 100 if slow_ma != 0 else 0
        
        # 检测交叉
        cross_type = None
        cross_strength = 0.0
        
        if len(prices) >= slow_period + 1:
            prev_fast = prices.iloc[-fast_period-1:-1].mean()
            prev_slow = prices.iloc[-slow_period-1:-1].mean()
            
            # 金叉检测
            if prev_fast <= prev_slow and fast_ma > slow_ma:
                cross_type = "golden"
                cross_strength = min(abs(distance_pct) / 2, 1.0)
            # 死叉检测
            elif prev_fast >= prev_slow and fast_ma < slow_ma:
                cross_type = "death"
                cross_strength = min(abs(distance_pct) / 2, 1.0)
            else:
                # 无交叉，但计算趋势强度
                cross_strength = min(abs(distance_pct) / 3, 0.5)
        
        return MACrossResult(
            fast_ma=fast_ma,
            slow_ma=slow_ma,
            cross_type=cross_type,
            cross_strength=cross_strength,
            distance_pct=distance_pct
        )
    
    def calculate_macd(
        self, 
        prices: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> MACDResult:
        """
        计算MACD指标
        
        Args:
            prices: 价格序列
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期
            
        Returns:
            MACDResult
        """
        if len(prices) < slow:
            return MACDResult(
                macd=0.0,
                signal=0.0,
                histogram=0.0,
                trend="neutral",
                divergence=0.0
            )
        
        # 计算EMA
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        
        # MACD线
        macd_line = ema_fast - ema_slow
        
        # 信号线
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        
        # 柱状图
        histogram = macd_line - signal_line
        
        # 当前值
        macd_val = macd_line.iloc[-1]
        signal_val = signal_line.iloc[-1]
        hist_val = histogram.iloc[-1]
        
        # 判断趋势
        if macd_val > signal_val and hist_val > 0:
            trend = "bullish"
        elif macd_val < signal_val and hist_val < 0:
            trend = "bearish"
        else:
            trend = "neutral"
        
        # 计算背离
        divergence = self._calculate_divergence(prices, macd_line)
        
        return MACDResult(
            macd=macd_val,
            signal=signal_val,
            histogram=hist_val,
            trend=trend,
            divergence=divergence
        )
    
    def calculate_momentum(
        self, 
        prices: pd.Series,
        period: int = 10
    ) -> MomentumResult:
        """
        计算价格动量
        
        Args:
            prices: 价格序列
            period: 动量计算周期
            
        Returns:
            MomentumResult
        """
        if len(prices) < period + 2:
            return MomentumResult(
                momentum=0.0,
                acceleration=0.0,
                momentum_roc=0.0,
                strength=0.0
            )
        
        # 当前动量
        current_momentum = (prices.iloc[-1] - prices.iloc[-period]) / prices.iloc[-period] * 100
        
        # 上期动量
        prev_momentum = (prices.iloc[-2] - prices.iloc[-period-1]) / prices.iloc[-period-1] * 100
        
        # 动量加速度
        acceleration = current_momentum - prev_momentum
        
        # 动量变化率
        momentum_roc = acceleration / abs(prev_momentum) * 100 if prev_momentum != 0 else 0
        
        # 动量强度 (0-1)
        strength = min(abs(current_momentum) / 10, 1.0)
        
        return MomentumResult(
            momentum=current_momentum,
            acceleration=acceleration,
            momentum_roc=momentum_roc,
            strength=strength
        )
    
    def calculate_multi_timeframe_momentum(
        self,
        prices: pd.Series
    ) -> Dict[str, MomentumResult]:
        """
        计算多时间框架动量
        
        Args:
            prices: 价格序列
            
        Returns:
            各时间框架动量结果
        """
        return {
            "5m": self.calculate_momentum(prices, 5),
            "15m": self.calculate_momentum(prices, 15),
            "1h": self.calculate_momentum(prices, 60),
            "4h": self.calculate_momentum(prices, 240),
            "1d": self.calculate_momentum(prices, 1440),
        }
    
    def detect_trend_direction(
        self,
        prices: pd.Series,
        ma_periods: List[int] = [5, 10, 20, 60]
    ) -> TrendDirection:
        """
        检测趋势方向
        
        Args:
            prices: 价格序列
            ma_periods: 均线周期列表
            
        Returns:
            TrendDirection
        """
        if len(prices) < max(ma_periods):
            return TrendDirection.NEUTRAL
        
        # 计算多条均线
        mas = [prices.iloc[-p:].mean() for p in ma_periods]
        current_price = prices.iloc[-1]
        
        # 计算趋势得分
        score = 0
        for i, ma in enumerate(mas):
            weight = len(ma_periods) - i
            if current_price > ma:
                score += weight
            else:
                score -= weight
        
        max_score = sum(range(1, len(ma_periods) + 1))
        normalized_score = score / max_score
        
        if normalized_score > 0.8:
            return TrendDirection.STRONG_UP
        elif normalized_score > 0.3:
            return TrendDirection.UP
        elif normalized_score < -0.8:
            return TrendDirection.STRONG_DOWN
        elif normalized_score < -0.3:
            return TrendDirection.DOWN
        else:
            return TrendDirection.NEUTRAL
    
    def _calculate_divergence(
        self,
        prices: pd.Series,
        indicator: pd.Series,
        lookback: int = 20
    ) -> float:
        """
        计算价格和指标的背离程度
        
        Returns:
            背离程度 (-1 到 1), 正值表示底背离, 负值表示顶背离
        """
        if len(prices) < lookback * 2:
            return 0.0
        
        # 找局部极值
        recent_prices = prices.iloc[-lookback:]
        recent_indicator = indicator.iloc[-lookback:]
        
        prev_prices = prices.iloc[-lookback*2:-lookback]
        prev_indicator = indicator.iloc[-lookback*2:-lookback]
        
        # 价格新高/新低
        price_high_recent = recent_prices.max()
        price_high_prev = prev_prices.max()
        price_low_recent = recent_prices.min()
        price_low_prev = prev_prices.min()
        
        # 指标新高/新低
        ind_high_recent = recent_indicator.max()
        ind_high_prev = prev_indicator.max()
        ind_low_recent = recent_indicator.min()
        ind_low_prev = prev_indicator.min()
        
        # 顶背离: 价格新高但指标未新高
        if price_high_recent > price_high_prev and ind_high_recent < ind_high_prev:
            return -min(abs(ind_high_recent - ind_high_prev) / abs(ind_high_prev), 1.0)
        
        # 底背离: 价格新低但指标未新低
        if price_low_recent < price_low_prev and ind_low_recent > ind_low_prev:
            return min(abs(ind_low_recent - ind_low_prev) / abs(ind_low_prev), 1.0)
        
        return 0.0
    
    def calculate_all(
        self,
        symbol: str,
        prices: pd.Series
    ) -> Dict[str, any]:
        """
        计算所有趋势因子
        
        Args:
            symbol: 交易对
            prices: 价格序列
            
        Returns:
            所有趋势因子字典
        """
        # MA交叉
        ma_cross_5_20 = self.calculate_ma_cross(prices, 5, 20)
        ma_cross_10_30 = self.calculate_ma_cross(prices, 10, 30)
        
        # MACD
        macd = self.calculate_macd(prices)
        
        # 多时间框架动量
        momentums = self.calculate_multi_timeframe_momentum(prices)
        
        # 趋势方向
        trend_dir = self.detect_trend_direction(prices)
        
        return {
            # MA交叉
            "ma_cross_5_20_type": ma_cross_5_20.cross_type,
            "ma_cross_5_20_strength": ma_cross_5_20.cross_strength,
            "ma_cross_5_20_distance": ma_cross_5_20.distance_pct,
            "ma_cross_10_30_type": ma_cross_10_30.cross_type,
            "ma_cross_10_30_strength": ma_cross_10_30.cross_strength,
            
            # MACD
            "macd": macd.macd,
            "macd_signal": macd.signal,
            "macd_histogram": macd.histogram,
            "macd_trend": macd.trend,
            "macd_divergence": macd.divergence,
            
            # 动量
            "momentum_5m": momentums["5m"].momentum,
            "momentum_15m": momentums["15m"].momentum,
            "momentum_1h": momentums["1h"].momentum,
            "momentum_accel": momentums["5m"].acceleration,
            "momentum_strength": momentums["5m"].strength,
            
            # 趋势
            "trend_direction": trend_dir.value,
            "trend_score": self._trend_score(trend_dir),
        }
    
    def _trend_score(self, direction: TrendDirection) -> float:
        """趋势方向转分数"""
        scores = {
            TrendDirection.STRONG_UP: 1.0,
            TrendDirection.UP: 0.5,
            TrendDirection.NEUTRAL: 0.0,
            TrendDirection.DOWN: -0.5,
            TrendDirection.STRONG_DOWN: -1.0,
        }
        return scores.get(direction, 0.0)


# 全局实例
trend_factors = TrendFactors()
