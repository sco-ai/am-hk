"""
单元测试 - 市场状态引擎
"""
import unittest
import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.market_state.market_state import MarketStateEngine, MarketState
from core.market_state.volatility_regime import VolatilityRegimeDetector, VolRegime
from core.market_state.adaptive_weights import AdaptiveWeightAdjuster


class TestMarketStateEngine(unittest.TestCase):
    """测试市场状态引擎"""
    
    def setUp(self):
        self.engine = MarketStateEngine()
        # 生成测试数据
        np.random.seed(42)
        # 明显的上升趋势
        self.bull_prices = pd.Series(100 + np.cumsum(np.abs(np.random.randn(50) + 0.5)))
        # 明显的下降趋势
        self.bear_prices = pd.Series(100 - np.cumsum(np.abs(np.random.randn(50) + 0.5)))
        # 震荡数据
        self.range_prices = pd.Series(100 + np.sin(np.linspace(0, 8*np.pi, 100)) * 3)
    
    def test_bull_market_detection(self):
        """测试牛市检测"""
        result = self.engine.detect_market_state("TEST_BULL", self.bull_prices)
        self.assertIn(result.state, [MarketState.BULL, MarketState.TRANSITION, MarketState.RANGE])
        self.assertGreaterEqual(result.confidence, 0)
        self.assertLessEqual(result.confidence, 1)
    
    def test_bear_market_detection(self):
        """测试熊市检测"""
        result = self.engine.detect_market_state("TEST_BEAR", self.bear_prices)
        self.assertIn(result.state, [MarketState.BEAR, MarketState.TRANSITION, MarketState.RANGE])
    
    def test_range_market_detection(self):
        """测试震荡市检测"""
        result = self.engine.detect_market_state("TEST_RANGE", self.range_prices)
        self.assertIn(result.state, list(MarketState))
    
    def test_state_consistency(self):
        """测试状态一致性"""
        for _ in range(5):
            self.engine.detect_market_state("TEST", self.bull_prices)
        
        current = self.engine.get_current_state("TEST")
        self.assertIsNotNone(current)


class TestVolatilityRegimeDetector(unittest.TestCase):
    """测试波动率状态检测器"""
    
    def setUp(self):
        self.detector = VolatilityRegimeDetector()
        np.random.seed(42)
        # 低波动数据
        self.low_vol_returns = pd.Series(np.random.randn(100) * 0.005)
        # 高波动数据
        self.high_vol_returns = pd.Series(np.random.randn(100) * 0.08)
    
    def test_volatility_detection(self):
        """测试波动率检测"""
        result = self.detector.detect("TEST", self.low_vol_returns)
        self.assertIn(result.regime, VolRegime)
        self.assertGreaterEqual(result.current_vol, 0)
    
    def test_high_volatility_detection(self):
        """测试高波动检测"""
        result = self.detector.detect("TEST_HIGH", self.high_vol_returns)
        self.assertIn(result.regime, VolRegime)
    
    def test_position_adjustment(self):
        """测试仓位调整建议"""
        result = self.detector.detect("TEST", self.high_vol_returns)
        self.assertGreaterEqual(result.position_adjustment, 0)
        self.assertLessEqual(result.position_adjustment, 1.5)
    
    def test_forecast(self):
        """测试波动率预测"""
        result = self.detector.detect("TEST", self.low_vol_returns)
        self.assertGreaterEqual(result.forecast_vol, 0)
        self.assertGreaterEqual(result.forecast_confidence, 0)
        self.assertLessEqual(result.forecast_confidence, 1)


class TestAdaptiveWeightAdjuster(unittest.TestCase):
    """测试自适应权重调整器"""
    
    def setUp(self):
        self.adjuster = AdaptiveWeightAdjuster()
    
    def test_bull_market_weights(self):
        """测试牛市权重调整"""
        result = self.adjuster.adjust_weights("bull", "normal", 0.7)
        self.assertIn("trend_following", result.strategy_weights)
        self.assertIn("momentum", result.strategy_weights)
        self.assertGreater(result.strategy_weights["trend_following"], 0.1)
    
    def test_bear_market_weights(self):
        """测试熊市权重调整"""
        result = self.adjuster.adjust_weights("bear", "high", -0.6)
        self.assertIn("mean_reversion", result.strategy_weights)
    
    def test_range_market_weights(self):
        """测试震荡市权重调整"""
        result = self.adjuster.adjust_weights("range", "normal", 0.1)
        self.assertGreater(result.strategy_weights["mean_reversion"], 0.1)
    
    def test_high_volatility_adjustment(self):
        """测试高波动调整"""
        result = self.adjuster.adjust_weights("bull", "extreme", 0.5)
        self.assertLess(result.position_multiplier, 1.0)
    
    def test_weight_normalization(self):
        """测试权重归一化"""
        result = self.adjuster.adjust_weights("bull", "normal", 0.5)
        total_strategy = sum(result.strategy_weights.values())
        total_factor = sum(result.factor_weights.values())
        self.assertAlmostEqual(total_strategy, 1.0, places=2)
        self.assertAlmostEqual(total_factor, 1.0, places=2)
    
    def test_performance_adjustment(self):
        """测试基于表现的调整"""
        performance = {
            "trend_following": 1.5,
            "mean_reversion": 0.8,
            "momentum": 1.2,
            "breakout": 0.5,
            "liquidity": 1.0,
        }
        result = self.adjuster.adjust_weights("bull", "normal", 0.5, performance)
        self.assertGreater(result.strategy_weights["trend_following"], 0.1)


if __name__ == '__main__':
    unittest.main()
