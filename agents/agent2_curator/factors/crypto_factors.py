"""
加密货币专属因子模块 - Crypto Factors
包含: 持仓量、多空比、资金费率趋势、链上指标接口
"""
import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum


class FundingTrend(Enum):
    """资金费率趋势"""
    STRONGLY_POSITIVE = "strongly_positive"  # 多头付费强烈
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    STRONGLY_NEGATIVE = "strongly_negative"  # 空头付费强烈


class OpenInterestTrend(Enum):
    """持仓量趋势"""
    RISING_FAST = "rising_fast"
    RISING = "rising"
    STABLE = "stable"
    FALLING = "falling"
    FALLING_FAST = "falling_fast"


@dataclass
class LongShortRatioResult:
    """多空比结果"""
    long_short_ratio: float  # 多空比 >1 表示多头占优
    long_account_pct: float  # 多头账户百分比
    short_account_pct: float
    taker_buy_ratio: float  # 主动买入比率
    signal: str  # "long_dominant", "short_dominant", "neutral"


@dataclass
class OpenInterestResult:
    """持仓量结果"""
    oi_value: float  # 持仓量 (合约数量)
    oi_usd: float  # 持仓量 (USD)
    oi_change_1h: float  # 1小时变化
    oi_change_24h: float  # 24小时变化
    trend: OpenInterestTrend
    price_oi_divergence: float  # 价格与持仓量背离


@dataclass
class FundingMomentumResult:
    """资金费率动量"""
    current: float
    slope_3p: float  # 3期斜率
    slope_9p: float  # 9期斜率
    acceleration: float
    trend: FundingTrend
    extreme_signal: str  # "potential_reversal", "continuation", "none"


class CryptoFactors:
    """加密货币专属因子计算器"""
    
    def __init__(self):
        self.oi_history: Dict[str, List[Dict]] = {}
        self.funding_history: Dict[str, List[float]] = {}
        self.ls_ratio_history: Dict[str, List[float]] = {}
        self.price_history: Dict[str, List[float]] = {}
        self.max_history = 100
    
    def calculate_open_interest_features(
        self,
        symbol: str,
        oi_value: float,
        oi_usd: float,
        price: float
    ) -> OpenInterestResult:
        """
        计算持仓量特征
        """
        if symbol not in self.oi_history:
            self.oi_history[symbol] = []
        
        self.oi_history[symbol].append({
            "oi_value": oi_value,
            "oi_usd": oi_usd,
            "price": price,
            "timestamp": pd.Timestamp.now()
        })
        
        if len(self.oi_history[symbol]) > self.max_history:
            self.oi_history[symbol] = self.oi_history[symbol][-self.max_history:]
        
        history = self.oi_history[symbol]
        
        oi_change_1h = 0
        oi_change_24h = 0
        
        if len(history) >= 2:
            oi_change_1h = (oi_value - history[-2]["oi_value"]) / history[-2]["oi_value"] * 100
        
        if len(history) >= 24:
            oi_change_24h = (oi_value - history[-24]["oi_value"]) / history[-24]["oi_value"] * 100
        
        if len(history) >= 3:
            recent_changes = [(history[i]["oi_value"] - history[i-1]["oi_value"]) / history[i-1]["oi_value"] 
                            for i in range(-3, 0) if i < 0]
            avg_change = np.mean(recent_changes) * 100
            
            if avg_change > 2:
                trend = OpenInterestTrend.RISING_FAST
            elif avg_change > 0.5:
                trend = OpenInterestTrend.RISING
            elif avg_change < -2:
                trend = OpenInterestTrend.FALLING_FAST
            elif avg_change < -0.5:
                trend = OpenInterestTrend.FALLING
            else:
                trend = OpenInterestTrend.STABLE
        else:
            trend = OpenInterestTrend.STABLE
        
        price_oi_divergence = 0
        if len(history) >= 6:
            price_change = (price - history[-6]["price"]) / history[-6]["price"] * 100
            oi_change = (oi_value - history[-6]["oi_value"]) / history[-6]["oi_value"] * 100
            
            if price_change > 1 and oi_change < -1:
                price_oi_divergence = -1
            elif price_change < -1 and oi_change > 1:
                price_oi_divergence = 1
            else:
                price_oi_divergence = 0
        
        return OpenInterestResult(
            oi_value=oi_value,
            oi_usd=oi_usd,
            oi_change_1h=oi_change_1h,
            oi_change_24h=oi_change_24h,
            trend=trend,
            price_oi_divergence=price_oi_divergence
        )
    
    def calculate_long_short_ratio(
        self,
        symbol: str,
        long_short_ratio: float,
        long_account_pct: Optional[float] = None,
        taker_buy_ratio: Optional[float] = None
    ) -> LongShortRatioResult:
        """计算多空比特征"""
        if symbol not in self.ls_ratio_history:
            self.ls_ratio_history[symbol] = []
        
        self.ls_ratio_history[symbol].append(long_short_ratio)
        if len(self.ls_ratio_history[symbol]) > self.max_history:
            self.ls_ratio_history[symbol] = self.ls_ratio_history[symbol][-self.max_history:]
        
        if long_account_pct is None:
            long_account_pct = long_short_ratio / (1 + long_short_ratio) * 100
        
        short_account_pct = 100 - long_account_pct
        
        if long_short_ratio > 2.0:
            signal = "long_dominant"
        elif long_short_ratio < 0.5:
            signal = "short_dominant"
        else:
            signal = "neutral"
        
        if taker_buy_ratio is None:
            taker_buy_ratio = long_account_pct / 100
        
        return LongShortRatioResult(
            long_short_ratio=long_short_ratio,
            long_account_pct=long_account_pct,
            short_account_pct=short_account_pct,
            taker_buy_ratio=taker_buy_ratio,
            signal=signal
        )
    
    def calculate_funding_momentum(
        self,
        symbol: str,
        current_funding: float
    ) -> FundingMomentumResult:
        """计算资金费率动量和趋势"""
        if symbol not in self.funding_history:
            self.funding_history[symbol] = []
        
        self.funding_history[symbol].append(current_funding)
        if len(self.funding_history[symbol]) > self.max_history:
            self.funding_history[symbol] = self.funding_history[symbol][-self.max_history:]
        
        history = self.funding_history[symbol]
        
        slope_3p = 0
        slope_9p = 0
        
        if len(history) >= 3:
            slope_3p = (history[-1] - history[-3]) / 2
        
        if len(history) >= 9:
            slope_9p = (history[-1] - history[-9]) / 8
        
        acceleration = slope_3p - (history[-2] - history[-3]) if len(history) >= 4 else 0
        
        if current_funding > 0.001:
            if slope_3p > 0.0001:
                trend = FundingTrend.STRONGLY_POSITIVE
            else:
                trend = FundingTrend.POSITIVE
        elif current_funding < -0.001:
            if slope_3p < -0.0001:
                trend = FundingTrend.STRONGLY_NEGATIVE
            else:
                trend = FundingTrend.NEGATIVE
        else:
            trend = FundingTrend.NEUTRAL
        
        extreme_signal = "none"
        if abs(current_funding) > 0.001:
            if acceleration * current_funding < 0:
                extreme_signal = "potential_reversal"
            else:
                extreme_signal = "continuation"
        
        return FundingMomentumResult(
            current=current_funding,
            slope_3p=slope_3p,
            slope_9p=slope_9p,
            acceleration=acceleration,
            trend=trend,
            extreme_signal=extreme_signal
        )
    
    def detect_liquidation_risk(
        self,
        symbol: str,
        oi_result: OpenInterestResult,
        funding_result: FundingMomentumResult,
        price: float,
        price_change_24h: float
    ) -> Dict[str, any]:
        """检测爆仓风险"""
        risk_score = 0.0
        
        if oi_result.oi_usd > 1_000_000_000:
            risk_score += 0.3
        elif oi_result.oi_usd > 100_000_000:
            risk_score += 0.2
        
        if abs(funding_result.current) > 0.001:
            risk_score += 0.3
        
        if abs(price_change_24h) > 10:
            risk_score += 0.3
        elif abs(price_change_24h) > 5:
            risk_score += 0.2
        
        if oi_result.trend in [OpenInterestTrend.RISING_FAST] and abs(price_change_24h) > 5:
            risk_score += 0.1
        
        risk_level = "low"
        if risk_score > 0.8:
            risk_level = "extreme"
        elif risk_score > 0.6:
            risk_level = "high"
        elif risk_score > 0.4:
            risk_level = "medium"
        
        liq_direction = "none"
        if funding_result.current > 0.0005 and price_change_24h > 5:
            liq_direction = "short_liquidation"
        elif funding_result.current < -0.0005 and price_change_24h < -5:
            liq_direction = "long_liquidation"
        
        return {
            "liquidation_risk_score": risk_score,
            "liquidation_risk_level": risk_level,
            "potential_liquidation_direction": liq_direction,
            "cascade_risk": risk_score > 0.7 and oi_result.trend == OpenInterestTrend.RISING_FAST
        }
    
    def calculate_market_sentiment_composite(
        self,
        ls_result: LongShortRatioResult,
        funding_result: FundingMomentumResult,
        oi_result: OpenInterestResult
    ) -> Dict[str, any]:
        """计算综合市场情绪"""
        ls_score = (ls_result.long_short_ratio - 1) / (ls_result.long_short_ratio + 1)
        
        funding_score = -funding_result.current / 0.001
        funding_score = max(-1, min(1, funding_score))
        
        if oi_result.trend == OpenInterestTrend.RISING_FAST:
            oi_score = 0.5
        elif oi_result.trend == OpenInterestTrend.FALLING_FAST:
            oi_score = -0.5
        else:
            oi_score = 0
        
        composite = ls_score * 0.4 + funding_score * 0.4 + oi_score * 0.2
        
        if composite > 0.6:
            sentiment = "extreme_greed"
        elif composite > 0.3:
            sentiment = "greed"
        elif composite > 0.1:
            sentiment = "optimistic"
        elif composite < -0.6:
            sentiment = "extreme_fear"
        elif composite < -0.3:
            sentiment = "fear"
        elif composite < -0.1:
            sentiment = "pessimistic"
        else:
            sentiment = "neutral"
        
        contrarian_signal = abs(composite) > 0.7
        
        return {
            "sentiment_composite": composite,
            "sentiment_label": sentiment,
            "sentiment_long_short": ls_score,
            "sentiment_funding": funding_score,
            "sentiment_oi": oi_score,
            "contrarian_signal": contrarian_signal,
        }
    
    def calculate_all(
        self,
        symbol: str,
        oi_value: float,
        oi_usd: float,
        price: float,
        long_short_ratio: float,
        funding_rate: float,
        long_account_pct: Optional[float] = None,
        taker_buy_ratio: Optional[float] = None,
        price_change_24h: float = 0
    ) -> Dict[str, any]:
        """计算所有加密货币专属因子"""
        oi_result = self.calculate_open_interest_features(symbol, oi_value, oi_usd, price)
        ls_result = self.calculate_long_short_ratio(symbol, long_short_ratio, long_account_pct, taker_buy_ratio)
        funding_result = self.calculate_funding_momentum(symbol, funding_rate)
        liq_risk = self.detect_liquidation_risk(symbol, oi_result, funding_result, price, price_change_24h)
        sentiment = self.calculate_market_sentiment_composite(ls_result, funding_result, oi_result)
        
        return {
            "open_interest": oi_result.oi_value,
            "open_interest_usd": oi_result.oi_usd,
            "oi_change_1h": oi_result.oi_change_1h,
            "oi_change_24h": oi_result.oi_change_24h,
            "oi_trend": oi_result.trend.value,
            "price_oi_divergence": oi_result.price_oi_divergence,
            "long_short_ratio": ls_result.long_short_ratio,
            "long_account_pct": ls_result.long_account_pct,
            "short_account_pct": ls_result.short_account_pct,
            "taker_buy_ratio": ls_result.taker_buy_ratio,
            "ls_signal": ls_result.signal,
            "funding_rate": funding_result.current,
            "funding_slope_3p": funding_result.slope_3p,
            "funding_slope_9p": funding_result.slope_9p,
            "funding_acceleration": funding_result.acceleration,
            "funding_trend": funding_result.trend.value,
            "funding_extreme_signal": funding_result.extreme_signal,
            "liquidation_risk_score": liq_risk["liquidation_risk_score"],
            "liquidation_risk_level": liq_risk["liquidation_risk_level"],
            "potential_liquidation_direction": liq_risk["potential_liquidation_direction"],
            "cascade_risk": liq_risk["cascade_risk"],
            "sentiment_composite": sentiment["sentiment_composite"],
            "sentiment_label": sentiment["sentiment_label"],
            "sentiment_ls": sentiment["sentiment_long_short"],
            "sentiment_funding": sentiment["sentiment_funding"],
            "sentiment_oi": sentiment["sentiment_oi"],
            "contrarian_signal": sentiment["contrarian_signal"],
        }


# 全局实例
crypto_factors = CryptoFactors()
