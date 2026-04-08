"""
Agent 4: TrendOracle 测试
"""
import asyncio
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from agents.agent4_oracle.main import (
    TrendOracle, 
    TradingDecision, 
    TrackAPrediction, 
    TrackBAnalysis,
    SentimentAnalysis,
    DecisionAction,
    InformerAutoformerClient,
    NHITSClient,
    QwenClient,
    KimiClient,
    FinBERTClient,
    RiskCalculator,
)


class TestRiskCalculator:
    """测试风险计算模块"""
    
    def test_calculate_tp_sl_buy(self):
        calc = RiskCalculator()
        tp, sl = calc.calculate_tp_sl(100.0, DecisionAction.BUY, 0.02)
        
        assert tp > 100.0  # 止盈价高于入场价
        assert sl < 100.0  # 止损价低于入场价
        assert tp - 100.0 > 100.0 - sl  # 止盈空间大于止损空间
    
    def test_calculate_tp_sl_sell(self):
        calc = RiskCalculator()
        tp, sl = calc.calculate_tp_sl(100.0, DecisionAction.SELL, 0.02)
        
        assert tp < 100.0  # 止盈价低于入场价
        assert sl > 100.0  # 止损价高于入场价
    
    def test_calculate_position_size(self):
        calc = RiskCalculator()
        
        # 高置信度 = 大仓位
        high_conf = calc.calculate_position_size(0.9)
        low_conf = calc.calculate_position_size(0.5)
        
        assert high_conf > low_conf
        assert high_conf <= 0.15  # 最大仓位限制


class TestTrackAPrediction:
    """测试Track A预测"""
    
    def test_to_dict(self):
        pred = TrackAPrediction(
            direction="up",
            predicted_return=0.032,
            confidence=0.85,
            informer_score=0.9,
            nhits_score=0.7,
        )
        
        d = pred.to_dict()
        assert d["direction"] == "up"
        assert d["predicted_return"] == 0.032
        assert d["confidence"] == 0.85


class TestTradingDecision:
    """测试交易决策"""
    
    def test_to_dict(self):
        decision = TradingDecision(
            action=DecisionAction.BUY,
            confidence=0.82,
            entry={"price": 65800, "time": 1744082400000},
            tp=66200,
            sl=64500,
            position_size=0.15,
            reasoning="Informer预测上涨+3.2%, Qwen确认趋势",
            track_a_score=0.85,
            track_b_score=0.75,
            sentiment_score=0.68,
        )
        
        d = decision.to_dict()
        assert d["action"] == "BUY"
        assert d["confidence"] == 0.82
        assert d["entry"]["price"] == 65800
        assert d["tp"] == 66200
        assert d["sl"] == 64500
        assert d["position_size"] == 0.15
        assert d["track_a_score"] == 0.85
        assert d["track_b_score"] == 0.75
        assert d["sentiment_score"] == 0.68


@pytest.mark.asyncio
class TestInformerAutoformerClient:
    """测试Informer客户端"""
    
    async def test_fallback_predict(self):
        client = InformerAutoformerClient()
        prices = [100.0 + i * 0.5 for i in range(70)]  # 上涨趋势
        
        result = client._fallback_predict(prices, 5)
        
        assert "predictions" in result
        assert "confidence" in result
        assert "direction" in result
        assert len(result["predictions"]) == 5


@pytest.mark.asyncio
class TestNHITSClient:
    """测试N-HiTS客户端"""
    
    async def test_fallback_decompose(self):
        client = NHITSClient()
        prices = [100.0 + i * 0.3 for i in range(50)]
        
        result = client._fallback_decompose(prices, 5)
        
        assert "trend" in result
        assert "seasonal" in result
        assert "forecast" in result
        assert len(result["trend"]) == 5


@pytest.mark.asyncio
class TestFinBERTClient:
    """测试FinBERT客户端"""
    
    async def test_fallback_sentiment(self):
        client = FinBERTClient()
        
        result = client._fallback_sentiment("00700")
        
        assert result.score == 0.0
        assert result.confidence == 0.3
        assert "fallback" in result.sources


class TestTrendOracle:
    """测试TrendOracle主类"""
    
    def test_initialization(self):
        oracle = TrendOracle()
        
        assert oracle.agent_name == "agent4_oracle"
        assert oracle.track_a_weight == 0.8
        assert oracle.track_b_weight == 0.2
        assert oracle.max_cache_size == 200
    
    def test_fuse_decision_consensus(self):
        """测试双轨融合 - 两者一致时"""
        oracle = TrendOracle()
        
        track_a = TrackAPrediction(
            direction="up",
            predicted_return=0.03,
            confidence=0.85,
        )
        
        track_b = TrackBAnalysis(
            recommendation="buy",
            confidence=0.8,
            reasoning="Strong momentum",
        )
        
        sentiment = SentimentAnalysis(
            score=0.5,
            confidence=0.7,
            sources=["twitter"],
        )
        
        factors = {"volatility_5m": 2.0, "atr_14": 1.5}
        prices = [100.0] * 10
        
        decision = oracle._fuse_decision(
            "00700", track_a, track_b, sentiment, factors, prices
        )
        
        assert decision.action == DecisionAction.BUY
        assert decision.confidence > 0.5
        assert decision.track_a_score == 0.85
        assert decision.track_b_score == 0.8
        assert decision.sentiment_score == 0.5
    
    def test_fuse_decision_low_confidence_hold(self):
        """测试低置信度时转为HOLD"""
        oracle = TrendOracle()
        
        track_a = TrackAPrediction(
            direction="up",
            predicted_return=0.01,
            confidence=0.3,  # 低置信度
        )
        
        track_b = TrackBAnalysis(
            recommendation="buy",
            confidence=0.3,
            reasoning="Uncertain",
        )
        
        sentiment = SentimentAnalysis(
            score=0.0,
            confidence=0.5,
            sources=[],
        )
        
        factors = {"volatility_5m": 2.0}
        prices = [100.0] * 10
        
        decision = oracle._fuse_decision(
            "00700", track_a, track_b, sentiment, factors, prices
        )
        
        # 低置信度应该转为HOLD
        assert decision.action == DecisionAction.HOLD


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
