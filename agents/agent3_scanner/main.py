"""
Agent 3: AlphaScanner (机会筛选器) - v3.0 Enhanced
多策略扫描、LightGBM因子评分、GPT-4.1策略优化、Top机会分层

职责：
- 接收 Agent2 的因子数据（Kafka: am-hk-processed-data）
- 多策略并行扫描（动量/价值/情绪/跨市场传导）
- LightGBM模型实时评分
- GPT-4.1动态阈值优化和策略权重调整
- Top机会排序和分层（Top10/Top20交易池生成）
- 输出交易机会到 Kafka: am-hk-trading-opportunities
"""
import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.kafka import MessageBus, AgentConsumer
from core.models import MarketType, ActionType
from core.ai_models import ModelFactory, LLMTradingAnalyzer
from core.utils import generate_msg_id, generate_timestamp, setup_logging
from core.config import settings

logger = setup_logging("agent3_scanner")


class StrategyType(str, Enum):
    """策略类型"""
    MOMENTUM = "momentum"           # 动量策略
    VALUE = "value"                 # 价值策略
    SENTIMENT = "sentiment"         # 情绪策略
    CROSS_MARKET = "cross_market"   # 跨市场传导策略


class OpportunityPool(str, Enum):
    """交易池分层"""
    TOP5_CORE = "top5"              # Top 5 核心仓
    TOP6_10_OPPORTUNITY = "top10"   # Top 6-10 机会仓
    TOP11_20_OBSERVATION = "top20"  # Top 11-20 观察池
    REJECTED = "rejected"           # 未入选


class Direction(str, Enum):
    """交易方向"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class StrategyScore:
    """策略评分结果"""
    strategy_type: StrategyType
    raw_score: float                # 原始评分
    normalized_score: float         # 归一化评分(0-1)
    direction: Direction
    confidence: float               # 策略置信度
    factors_used: List[str]         # 使用的因子
    reasoning: str                  # 策略推理


@dataclass
class Opportunity:
    """交易机会"""
    symbol: str
    market: str
    timestamp: int
    rank: int
    pool: OpportunityPool
    direction: Direction
    confidence: float               # 综合置信度
    score: float                    # LightGBM综合评分
    
    # 策略分解
    strategy_scores: Dict[str, StrategyScore] = field(default_factory=dict)
    strategy_weights: Dict[str, float] = field(default_factory=dict)
    
    # 因子数据
    factors: Dict[str, float] = field(default_factory=dict)
    cross_market_signals: List[Dict] = field(default_factory=list)
    
    # 推理和阈值
    reasoning: str = ""
    thresholds: Dict[str, float] = field(default_factory=dict)
    
    # 元数据
    processing_time_ms: float = 0.0
    model_version: str = "v3.0"

    def to_dict(self) -> Dict:
        """转换为输出格式"""
        return {
            "symbol": self.symbol,
            "market": self.market,
            "timestamp": self.timestamp,
            "rank": self.rank,
            "pool": self.pool.value,
            "direction": self.direction.value,
            "confidence": round(self.confidence, 4),
            "score": round(self.score, 4),
            "factors": self.factors,
            "reasoning": self.reasoning,
            "strategy_weights": self.strategy_weights,
            "thresholds": self.thresholds,
            "strategy_breakdown": {
                k: {
                    "raw_score": round(v.raw_score, 4),
                    "normalized_score": round(v.normalized_score, 4),
                    "direction": v.direction.value,
                    "confidence": round(v.confidence, 4),
                    "reasoning": v.reasoning,
                }
                for k, v in self.strategy_scores.items()
            },
            "cross_market_signals": self.cross_market_signals[:3],  # 只取前3个
            "metadata": {
                "processing_time_ms": round(self.processing_time_ms, 2),
                "model_version": self.model_version,
            }
        }


@dataclass
class MarketContext:
    """市场环境上下文"""
    timestamp: int
    volatility_regime: str          # high/medium/low
    trend_strength: float           # 趋势强度
    market_sentiment: float         # 市场情绪(-1到1)
    capital_flow_direction: str     # inflow/outflow/neutral
    btc_momentum: float             # BTC动量
    us_market_state: str            # 美股状态
    
    def to_prompt_context(self) -> str:
        """转换为LLM prompt上下文"""
        return f"""当前市场环境:
- 波动率状态: {self.volatility_regime}
- 趋势强度: {self.trend_strength:.2f}
- 市场情绪: {self.market_sentiment:+.2f}
- 资金流向: {self.capital_flow_direction}
- BTC动量: {self.btc_momentum:+.2f}%
- 美股状态: {self.us_market_state}
"""


class LightGBMFactorScorer:
    """
    LightGBM因子评分器
    
    当前使用规则模拟，后续接入云训练模型
    """
    
    def __init__(self):
        self.feature_names = [
            # 量价因子
            "price_momentum_5m", "price_momentum_15m", "price_momentum_1h",
            "volume_momentum", "volatility_5m", "volatility_20",
            "liquidity_score", "turnover_rate", "price_acceleration",
            "volume_price_trend",
            # 技术指标
            "ma_5", "ma_20", "rsi_14", "macd", "macd_signal",
            "bb_upper", "bb_lower", "atr_14",
            # 盘口因子
            "bid_ask_spread", "orderbook_imbalance", "depth_imbalance",
            "depth_change_rate", "bid_pressure", "ask_pressure",
            # 资金流因子
            "net_inflow_speed", "main_force_ratio", "retail_ratio",
            "main_retail_ratio", "northbound_strength", "large_order_net",
            # 跨市场因子
            "crypto_correlation", "us_lead_lag", "cross_market_momentum",
            "layer1_signal", "layer2_confirm",
        ]
        self.model_version = "v3.0-cloud"
        
    def score(self, factors: Dict[str, float], market_context: MarketContext) -> float:
        """
        计算综合评分
        
        Returns:
            score: 0-1之间的综合评分
        """
        if not factors:
            return 0.0
        
        scores = []
        weights = []
        
        # 1. 短期动量评分 (权重: 0.20)
        mom_score = self._calc_momentum_score(factors)
        scores.append(mom_score)
        weights.append(0.20)
        
        # 2. 趋势评分 (权重: 0.15)
        trend_score = self._calc_trend_score(factors)
        scores.append(trend_score)
        weights.append(0.15)
        
        # 3. 情绪/RSI评分 (权重: 0.15)
        sentiment_score = self._calc_sentiment_score(factors)
        scores.append(sentiment_score)
        weights.append(0.15)
        
        # 4. 资金流评分 (权重: 0.20)
        flow_score = self._calc_capital_flow_score(factors)
        scores.append(flow_score)
        weights.append(0.20)
        
        # 5. 盘口结构评分 (权重: 0.15)
        orderbook_score = self._calc_orderbook_score(factors)
        scores.append(orderbook_score)
        weights.append(0.15)
        
        # 6. 跨市场传导评分 (权重: 0.15)
        cross_market_score = self._calc_cross_market_score(factors, market_context)
        scores.append(cross_market_score)
        weights.append(0.15)
        
        # 加权平均
        weighted_score = sum(s * w for s, w in zip(scores, weights))
        
        # 根据市场环境调整
        adjusted_score = self._adjust_for_market_regime(weighted_score, market_context)
        
        return max(0.0, min(1.0, adjusted_score))
    
    def _calc_momentum_score(self, factors: Dict) -> float:
        """计算动量评分"""
        score = 0.5  # 中性基准
        
        # 5分钟动量
        mom_5m = factors.get("price_momentum_5m", 0)
        if abs(mom_5m) > 2.0:
            score += np.sign(mom_5m) * min(abs(mom_5m) / 10, 0.2)
        
        # 15分钟动量
        mom_15m = factors.get("price_momentum_15m", 0)
        if abs(mom_15m) > 3.0:
            score += np.sign(mom_15m) * min(abs(mom_15m) / 15, 0.15)
        
        # 成交量动量
        vol_mom = factors.get("volume_momentum", 1.0)
        if vol_mom > 1.5:
            score += 0.1 * min((vol_mom - 1.5), 1.0)
        
        # 价格加速度
        accel = factors.get("price_acceleration", 0)
        score += np.sign(accel) * min(abs(accel) / 5, 0.1)
        
        return max(0.0, min(1.0, score))
    
    def _calc_trend_score(self, factors: Dict) -> float:
        """计算趋势评分"""
        score = 0.5
        
        # MA趋势
        ma_5 = factors.get("ma_5", 0)
        ma_20 = factors.get("ma_20", 0)
        if ma_5 > 0 and ma_20 > 0:
            ma_diff = (ma_5 - ma_20) / ma_20
            score += np.sign(ma_diff) * min(abs(ma_diff) * 10, 0.3)
        
        # MACD
        macd = factors.get("macd", 0)
        macd_signal = factors.get("macd_signal", 0)
        if macd > macd_signal:
            score += 0.1
        else:
            score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def _calc_sentiment_score(self, factors: Dict) -> float:
        """计算情绪评分"""
        score = 0.5
        
        rsi = factors.get("rsi_14", 50)
        if rsi > 70:
            score = 0.3  # 超买
        elif rsi < 30:
            score = 0.7  # 超卖
        else:
            score = 0.5 + (50 - rsi) / 100  # 中间区域
        
        # 布林带位置
        bb_upper = factors.get("bb_upper", 0)
        bb_lower = factors.get("bb_lower", 0)
        close = factors.get("ma_5", (bb_upper + bb_lower) / 2 if bb_upper and bb_lower else 0)
        if bb_upper > bb_lower > 0:
            bb_position = (close - bb_lower) / (bb_upper - bb_lower)
            if bb_position > 0.8:
                score -= 0.1
            elif bb_position < 0.2:
                score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def _calc_capital_flow_score(self, factors: Dict) -> float:
        """计算资金流评分"""
        score = 0.5
        
        # 主力资金比率
        main_ratio = factors.get("main_force_ratio", 0)
        score += main_ratio * 0.3
        
        # 北水强度
        northbound = factors.get("northbound_strength", 0)
        score += northbound * 0.2
        
        # 大单净流入
        large_net = factors.get("large_order_net", 0)
        if large_net != 0:
            score += np.sign(large_net) * min(abs(large_net) / 1e6, 0.1)
        
        return max(0.0, min(1.0, score))
    
    def _calc_orderbook_score(self, factors: Dict) -> float:
        """计算盘口评分"""
        score = 0.5
        
        # 订单簿不平衡
        imbalance = factors.get("orderbook_imbalance", 0)
        score += imbalance * 0.3
        
        # 深度不平衡
        depth_imb = factors.get("depth_imbalance", 0)
        score += depth_imb * 0.2
        
        # 买卖压力
        bid_pressure = factors.get("bid_pressure", 0.5)
        ask_pressure = factors.get("ask_pressure", 0.5)
        if bid_pressure + ask_pressure > 0:
            pressure_ratio = bid_pressure / (bid_pressure + ask_pressure)
            score += (pressure_ratio - 0.5) * 0.4
        
        return max(0.0, min(1.0, score))
    
    def _calc_cross_market_score(self, factors: Dict, context: MarketContext) -> float:
        """计算跨市场传导评分"""
        score = 0.5
        
        # Layer1信号 (Crypto)
        layer1 = factors.get("layer1_signal", 0)
        if abs(layer1) > 1.0:
            score += np.sign(layer1) * min(abs(layer1) / 10, 0.2)
        
        # Layer2信号 (美股)
        layer2 = factors.get("layer2_confirm", 0)
        if abs(layer2) > 1.0:
            score += np.sign(layer2) * min(abs(layer2) / 10, 0.15)
        
        # 综合传导动量
        cross_mom = factors.get("cross_market_momentum", 0)
        score += np.sign(cross_mom) * min(abs(cross_mom) / 10, 0.15)
        
        # 与BTC相关性调整
        btc_corr = factors.get("crypto_correlation", 0)
        if btc_corr > 0.3 and abs(context.btc_momentum) > 2.0:
            score += np.sign(context.btc_momentum) * btc_corr * 0.1
        
        return max(0.0, min(1.0, score))
    
    def _adjust_for_market_regime(self, score: float, context: MarketContext) -> float:
        """根据市场环境调整评分"""
        # 高波动环境降低极端评分
        if context.volatility_regime == "high":
            score = 0.5 + (score - 0.5) * 0.8
        
        # 强趋势环境增强方向性
        if context.trend_strength > 0.7:
            score = score * 1.1 if score > 0.5 else score * 0.9
        
        return max(0.0, min(1.0, score))