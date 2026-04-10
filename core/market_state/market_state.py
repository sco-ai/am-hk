"""
市场状态检测器 - Market State Detector
检测Bull/Bear/Range市场状态
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MarketState(Enum):
    """市场状态枚举"""
    BULL = "bull"           # 牛市
    BEAR = "bear"           # 熊市
    RANGE = "range"         # 震荡
    TRANSITION = "transition"  # 转换中
    UNKNOWN = "unknown"


@dataclass
class MarketStateResult:
    """市场状态结果"""
    state: MarketState
    confidence: float  # 状态置信度
    strength: float  # 趋势强度 (-1 到 1)
    duration: int  # 当前状态持续时间 (bars)
    
    # 细分指标
    trend_score: float
    momentum_score: float
    range_score: float
    
    # 元数据
    timestamp: datetime
    reasoning: str


class MarketStateEngine:
    """
    市场状态引擎
    
    基于多时间框架分析判断市场状态
    """
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self.price_history: Dict[str, List[float]] = {}
        self.state_history: Dict[str, List[MarketState]] = {}
        self.current_states: Dict[str, MarketStateResult] = {}
        
    def detect_market_state(
        self,
        symbol: str,
        prices: pd.Series,
        volumes: Optional[pd.Series] = None
    ) -> MarketStateResult:
        """
        检测市场状态
        
        Args:
            symbol: 交易对
            prices: 价格序列
            volumes: 成交量序列 (可选)
            
        Returns:
            MarketStateResult
        """
        # 保存历史
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        if len(prices) > 0:
            self.price_history[symbol].append(prices.iloc[-1])
            if len(self.price_history[symbol]) > self.history_size:
                self.price_history[symbol] = self.price_history[symbol][-self.history_size:]
        
        if len(prices) < 20:
            return MarketStateResult(
                state=MarketState.UNKNOWN,
                confidence=0.0,
                strength=0.0,
                duration=0,
                trend_score=0.0,
                momentum_score=0.0,
                range_score=0.0,
                timestamp=datetime.now(),
                reasoning="数据不足"
            )
        
        # 计算各类分数
        trend_score = self._calculate_trend_score(prices)
        momentum_score = self._calculate_momentum_score(prices)
        range_score = self._calculate_range_score(prices)
        
        # 确定状态
        state, confidence = self._determine_state(
            trend_score, momentum_score, range_score
        )
        
        # 计算强度
        strength = self._calculate_strength(trend_score, momentum_score, state)
        
        # 计算持续时间
        duration = self._calculate_duration(symbol, state)
        
        # 生成推理
        reasoning = self._generate_reasoning(
            state, trend_score, momentum_score, range_score
        )
        
        result = MarketStateResult(
            state=state,
            confidence=confidence,
            strength=strength,
            duration=duration,
            trend_score=trend_score,
            momentum_score=momentum_score,
            range_score=range_score,
            timestamp=datetime.now(),
            reasoning=reasoning
        )
        
        # 保存状态历史
        if symbol not in self.state_history:
            self.state_history[symbol] = []
        self.state_history[symbol].append(state)
        if len(self.state_history[symbol]) > self.history_size:
            self.state_history[symbol] = self.state_history[symbol][-self.history_size:]
        
        self.current_states[symbol] = result
        
        return result
    
    def _calculate_trend_score(self, prices: pd.Series) -> float:
        """计算趋势分数 (-1 到 1)"""
        if len(prices) < 20:
            return 0.0
        
        # 多均线趋势
        ma5 = prices.iloc[-5:].mean()
        ma10 = prices.iloc[-10:].mean()
        ma20 = prices.iloc[-20:].mean()
        
        current = prices.iloc[-1]
        
        # 均线排列分数
        score = 0
        if current > ma5:
            score += 0.2
        if ma5 > ma10:
            score += 0.2
        if ma10 > ma20:
            score += 0.2
        if current > ma20:
            score += 0.2
        
        # 斜率
        slope = (prices.iloc[-1] - prices.iloc[-10]) / prices.iloc[-10] if len(prices) >= 10 else 0
        score += np.tanh(slope * 10) * 0.2
        
        return max(-1, min(1, score))
    
    def _calculate_momentum_score(self, prices: pd.Series) -> float:
        """计算动量分数"""
        if len(prices) < 10:
            return 0.0
        
        returns = prices.pct_change().dropna()
        
        # 短期动量
        mom_5 = (prices.iloc[-1] - prices.iloc[-5]) / prices.iloc[-5] if len(prices) >= 5 else 0
        mom_10 = (prices.iloc[-1] - prices.iloc[-10]) / prices.iloc[-10] if len(prices) >= 10 else 0
        
        # 动量一致性
        score = np.tanh(mom_5 * 20) * 0.5 + np.tanh(mom_10 * 10) * 0.5
        
        return max(-1, min(1, score))
    
    def _calculate_range_score(self, prices: pd.Series) -> float:
        """计算震荡分数 (0-1, 越高越像震荡)"""
        if len(prices) < 20:
            return 0.5
        
        # 布林带宽度
        ma20 = prices.iloc[-20:].mean()
        std20 = prices.iloc[-20:].std()
        bb_width = (2 * std20) / ma20 if ma20 != 0 else 0
        
        # 价格在区间内的位置变化
        recent = prices.iloc[-20:]
        high, low = recent.max(), recent.min()
        range_pct = (high - low) / ((high + low) / 2) if high + low > 0 else 0
        
        # 趋势性检测 (ADX简化版)
        returns = prices.pct_change().dropna()
        directional_movement = abs(returns.iloc[-10:].sum()) / (returns.iloc[-10:].abs().sum() + 1e-8)
        
        # 震荡特征: 区间小 + 方向性弱
        range_score = (1 - min(directional_movement * 2, 1)) * 0.7
        range_score += min(bb_width * 10, 0.3)  # 带宽适中
        
        return max(0, min(1, range_score))
    
    def _determine_state(
        self,
        trend_score: float,
        momentum_score: float,
        range_score: float
    ) -> Tuple[MarketState, float]:
        """确定市场状态"""
        # 震荡优先
        if range_score > 0.6 and abs(trend_score) < 0.3:
            return MarketState.RANGE, range_score
        
        # 趋势状态
        combined_score = (trend_score + momentum_score) / 2
        
        if combined_score > 0.4:
            confidence = min(abs(combined_score) + (1 - range_score) * 0.3, 1.0)
            return MarketState.BULL, confidence
        elif combined_score < -0.4:
            confidence = min(abs(combined_score) + (1 - range_score) * 0.3, 1.0)
            return MarketState.BEAR, confidence
        
        # 转换中
        if abs(trend_score) > 0.2:
            return MarketState.TRANSITION, 0.5
        
        return MarketState.RANGE, 0.5
    
    def _calculate_strength(
        self,
        trend_score: float,
        momentum_score: float,
        state: MarketState
    ) -> float:
        """计算趋势强度"""
        if state == MarketState.BULL:
            return (trend_score + momentum_score) / 2
        elif state == MarketState.BEAR:
            return (trend_score + momentum_score) / 2
        else:
            return 0.0
    
    def _calculate_duration(self, symbol: str, current_state: MarketState) -> int:
        """计算状态持续时间"""
        if symbol not in self.state_history:
            return 0
        
        duration = 0
        for state in reversed(self.state_history[symbol]):
            if state == current_state:
                duration += 1
            else:
                break
        
        return duration
    
    def _generate_reasoning(
        self,
        state: MarketState,
        trend_score: float,
        momentum_score: float,
        range_score: float
    ) -> str:
        """生成推理说明"""
        reasons = []
        
        if state == MarketState.BULL:
            reasons.append(f"趋势向上({trend_score:+.2f})")
            if momentum_score > 0.3:
                reasons.append("动量强劲")
        elif state == MarketState.BEAR:
            reasons.append(f"趋势向下({trend_score:+.2f})")
            if momentum_score < -0.3:
                reasons.append("动量疲弱")
        elif state == MarketState.RANGE:
            reasons.append(f"区间震荡({range_score:.2f})")
        else:
            reasons.append("状态转换中")
        
        return "; ".join(reasons)
    
    def get_current_state(self, symbol: str) -> Optional[MarketStateResult]:
        """获取当前状态"""
        return self.current_states.get(symbol)
    
    def get_state_distribution(self, symbol: str, lookback: int = 20) -> Dict[str, float]:
        """获取状态分布"""
        if symbol not in self.state_history:
            return {}
        
        recent = self.state_history[symbol][-lookback:]
        if not recent:
            return {}
        
        distribution = {}
        for state in MarketState:
            count = recent.count(state)
            distribution[state.value] = count / len(recent)
        
        return distribution


# 全局实例
market_state_engine = MarketStateEngine()
