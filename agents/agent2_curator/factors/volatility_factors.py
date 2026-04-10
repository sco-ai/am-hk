"""
波动率因子模块 - Volatility Factors
包含: ATR、布林带宽度、波动率状态检测
"""
import numpy as np
import pandas as pd
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class VolatilityRegime(Enum):
    """波动率状态"""
    VERY_LOW = "very_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class ATRResult:
    """ATR计算结果"""
    atr: float
    atr_pct: float  # ATR占价格百分比
    normalized_atr: float  # 归一化ATR (0-1)
    trend: str  # "expanding", "contracting", "stable"


@dataclass
class BollingerBandsResult:
    """布林带结果"""
    upper: float
    middle: float
    lower: float
    bandwidth: float  # 带宽 (%)
    position: float  # 价格在带中的位置 (0-1)
    squeeze: bool  # 是否挤压
    breakout: Optional[str]  # "upper", "lower", None


@dataclass
class VolatilityResult:
    """综合波动率结果"""
    current_vol: float
    historical_vol: float
    vol_ratio: float  # 当前/历史波动率
    regime: VolatilityRegime
    forecast: float  # 简单预测


class VolatilityFactors:
    """波动率因子计算器"""
    
    def __init__(self):
        self.vol_history: Dict[str, list] = {}
        self.max_history = 100
    
    def calculate_atr(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> ATRResult:
        """
        计算平均真实波幅 (ATR)
        
        Args:
            high: 最高价序列
            low: 最低价序列
            close: 收盘价序列
            period: 计算周期
            
        Returns:
            ATRResult
        """
        if len(close) < period + 1:
            return ATRResult(
                atr=0.0,
                atr_pct=0.0,
                normalized_atr=0.5,
                trend="stable"
            )
        
        # 计算真实波幅
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR
        atr = tr.iloc[-period:].mean()
        
        # ATR百分比
        current_price = close.iloc[-1]
        atr_pct = (atr / current_price) * 100 if current_price != 0 else 0
        
        # 归一化ATR (基于历史)
        if len(tr) >= period * 2:
            historical_atr = tr.iloc[-period*2:-period].mean()
            normalized_atr = min(atr / historical_atr, 2.0) / 2.0 if historical_atr > 0 else 0.5
        else:
            normalized_atr = 0.5
        
        # ATR趋势
        if len(tr) >= period + 5:
            atr_short = tr.iloc[-5:].mean()
            atr_long = tr.iloc[-period-5:-5].mean()
            
            if atr_short > atr_long * 1.1:
                trend = "expanding"
            elif atr_short < atr_long * 0.9:
                trend = "contracting"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return ATRResult(
            atr=atr,
            atr_pct=atr_pct,
            normalized_atr=normalized_atr,
            trend=trend
        )
    
    def calculate_bollinger_bands(
        self,
        prices: pd.Series,
        period: int = 20,
        std_dev: float = 2.0
    ) -> BollingerBandsResult:
        """
        计算布林带
        
        Args:
            prices: 价格序列
            period: 计算周期
            std_dev: 标准差倍数
            
        Returns:
            BollingerBandsResult
        """
        if len(prices) < period:
            current_price = prices.iloc[-1] if len(prices) > 0 else 0
            return BollingerBandsResult(
                upper=current_price,
                middle=current_price,
                lower=current_price,
                bandwidth=0.0,
                position=0.5,
                squeeze=False,
                breakout=None
            )
        
        # 中轨 (SMA)
        middle = prices.iloc[-period:].mean()
        
        # 标准差
        std = prices.iloc[-period:].std()
        
        # 上下轨
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        
        # 带宽
        bandwidth = ((upper - lower) / middle) * 100 if middle != 0 else 0
        
        # 价格位置
        current_price = prices.iloc[-1]
        if upper != lower:
            position = (current_price - lower) / (upper - lower)
            position = max(0, min(1, position))
        else:
            position = 0.5
        
        # 挤压检测 (带宽收窄)
        if len(prices) >= period * 2:
            prev_bandwidth = ((upper - lower) / middle) * 100  # 简化计算
            squeeze = bandwidth < prev_bandwidth * 0.8
        else:
            squeeze = False
        
        # 突破检测
        breakout = None
        if current_price > upper:
            breakout = "upper"
        elif current_price < lower:
            breakout = "lower"
        
        return BollingerBandsResult(
            upper=upper,
            middle=middle,
            lower=lower,
            bandwidth=bandwidth,
            position=position,
            squeeze=squeeze,
            breakout=breakout
        )
    
    def calculate_volatility_regime(
        self,
        returns: pd.Series,
        lookback: int = 30
    ) -> VolatilityResult:
        """
        计算波动率状态
        
        Args:
            returns: 收益率序列
            lookback: 回望周期
            
        Returns:
            VolatilityResult
        """
        if len(returns) < lookback:
            return VolatilityResult(
                current_vol=0.0,
                historical_vol=0.0,
                vol_ratio=1.0,
                regime=VolatilityRegime.NORMAL,
                forecast=0.0
            )
        
        # 当前波动率 (年化)
        current_vol = returns.iloc[-lookback:].std() * np.sqrt(365 * 24 * 12) * 100
        
        # 历史波动率
        if len(returns) >= lookback * 2:
            historical_vol = returns.iloc[-lookback*2:-lookback].std() * np.sqrt(365 * 24 * 12) * 100
        else:
            historical_vol = current_vol
        
        # 波动率比率
        vol_ratio = current_vol / historical_vol if historical_vol > 0 else 1.0
        
        # 状态判断
        if vol_ratio < 0.5:
            regime = VolatilityRegime.VERY_LOW
        elif vol_ratio < 0.8:
            regime = VolatilityRegime.LOW
        elif vol_ratio < 1.2:
            regime = VolatilityRegime.NORMAL
        elif vol_ratio < 1.8:
            regime = VolatilityRegime.HIGH
        else:
            regime = VolatilityRegime.EXTREME
        
        # 简单预测 (均值回归)
        if vol_ratio > 1.5:
            forecast = historical_vol * 1.2
        elif vol_ratio < 0.7:
            forecast = historical_vol * 0.9
        else:
            forecast = current_vol
        
        return VolatilityResult(
            current_vol=current_vol,
            historical_vol=historical_vol,
            vol_ratio=vol_ratio,
            regime=regime,
            forecast=forecast
        )
    
    def calculate_parkinson_volatility(
        self,
        high: pd.Series,
        low: pd.Series,
        period: int = 20
    ) -> float:
        """
        Parkinson波动率 (基于高低价)
        
        比收盘价波动率更精确，利用了日内信息
        """
        if len(high) < period or len(low) < period:
            return 0.0
        
        # Parkinson估计
        hl_ratio = np.log(high / low)
        parkinson_var = (hl_ratio ** 2).mean() / (4 * np.log(2))
        
        # 年化
        parkinson_vol = np.sqrt(parkinson_var) * np.sqrt(365 * 24 * 12) * 100
        
        return parkinson_vol
    
    def calculate_garman_klass_volatility(
        self,
        open_p: pd.Series,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 20
    ) -> float:
        """
        Garman-Klass波动率 (基于OHLC)
        
        更高效的波动率估计
        """
        if len(open_p) < period:
            return 0.0
        
        # Garman-Klass估计
        log_hl = np.log(high / low) ** 2
        log_co = np.log(close / open_p) ** 2
        
        gk_var = 0.5 * log_hl - (2 * np.log(2) - 1) * log_co
        gk_vol = np.sqrt(gk_var.mean()) * np.sqrt(365 * 24 * 12) * 100
        
        return gk_vol
    
    def detect_volatility_clustering(
        self,
        returns: pd.Series,
        period: int = 10
    ) -> Dict[str, any]:
        """
        检测波动率聚集 (GARCH效应)
        
        Returns:
            聚集特征字典
        """
        if len(returns) < period * 2:
            return {"clustering": False, "persistence": 0.0}
        
        # 绝对收益率自相关
        abs_returns = returns.abs()
        
        # 简单检测: 高波动是否跟随高波动
        high_vol_periods = abs_returns.iloc[-period:].mean()
        prev_vol_periods = abs_returns.iloc[-period*2:-period].mean()
        
        persistence = min(high_vol_periods / prev_vol_periods if prev_vol_periods > 0 else 0, 2.0) / 2.0
        
        clustering = persistence > 0.6
        
        return {
            "clustering": clustering,
            "persistence": persistence,
            "current_abs_return": abs_returns.iloc[-1],
            "avg_abs_return": abs_returns.iloc[-period:].mean()
        }
    
    def calculate_all(
        self,
        prices: pd.Series,
        high: Optional[pd.Series] = None,
        low: Optional[pd.Series] = None,
        open_p: Optional[pd.Series] = None
    ) -> Dict[str, any]:
        """
        计算所有波动率因子
        
        Args:
            prices: 收盘价序列
            high: 最高价序列 (可选)
            low: 最低价序列 (可选)
            open_p: 开盘价序列 (可选)
            
        Returns:
            所有波动率因子字典
        """
        returns = prices.pct_change().dropna()
        
        # 基础ATR (使用收盘价模拟)
        if high is None:
            high = prices
        if low is None:
            low = prices
        
        atr = self.calculate_atr(high, low, prices)
        
        # 布林带
        bb = self.calculate_bollinger_bands(prices)
        
        # 波动率状态
        vol_regime = self.calculate_volatility_regime(returns)
        
        # 波动率聚集
        clustering = self.detect_volatility_clustering(returns)
        
        result = {
            # ATR
            "atr": atr.atr,
            "atr_pct": atr.atr_pct,
            "atr_normalized": atr.normalized_atr,
            "atr_trend": atr.trend,
            
            # 布林带
            "bb_upper": bb.upper,
            "bb_lower": bb.lower,
            "bb_bandwidth": bb.bandwidth,
            "bb_position": bb.position,
            "bb_squeeze": bb.squeeze,
            "bb_breakout": bb.breakout,
            
            # 波动率状态
            "volatility_current": vol_regime.current_vol,
            "volatility_historical": vol_regime.historical_vol,
            "volatility_ratio": vol_regime.vol_ratio,
            "volatility_regime": vol_regime.regime.value,
            "volatility_forecast": vol_regime.forecast,
            
            # 聚集特征
            "vol_clustering": clustering["clustering"],
            "vol_persistence": clustering["persistence"],
        }
        
        # 如果提供了OHLC,计算更精确的波动率
        if high is not None and low is not None and open_p is not None:
            parkinson = self.calculate_parkinson_volatility(high, low)
            gk_vol = self.calculate_garman_klass_volatility(open_p, high, low, prices)
            
            result["volatility_parkinson"] = parkinson
            result["volatility_garman_klass"] = gk_vol
        
        return result


# 全局实例
volatility_factors = VolatilityFactors()
