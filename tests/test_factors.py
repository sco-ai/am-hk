"""
单元测试 - 因子库
"""
import unittest
import numpy as np
import pandas as pd
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from agents.agent2_curator.factors.trend_factors import TrendFactors, TrendDirection
from agents.agent2_curator.factors.volatility_factors import VolatilityFactors, VolatilityRegime
from agents.agent2_curator.factors.liquidity_factors import LiquidityFactors, LiquidityLevel
from agents.agent2_curator.factors.crypto_factors import CryptoFactors, FundingTrend, OpenInterestTrend


class TestTrendFactors(unittest.TestCase):
    """测试趋势因子"""
    
    def setUp(self):
        self.tf = TrendFactors()
        # 生成测试数据 - 上升趋势
        self.up_trend = pd.Series([100, 102, 101, 104, 103, 106, 105, 108, 107, 110])
        # 生成测试数据 - 下降趋势
        self.down_trend = pd.Series([110, 108, 109, 106, 107, 104, 105, 102, 103, 100])
        # 生成测试数据 - 震荡
        self.range_bound = pd.Series([100, 102, 99, 101, 98, 100, 97, 99, 96, 98])
    
    def test_ma_cross_detection(self):
        """测试均线交叉检测"""
        result = self.tf.calculate_ma_cross(self.up_trend, fast_period=3, slow_period=5)
        self.assertIsNotNone(result.fast_ma)
        self.assertIsNotNone(result.slow_ma)
        self.assertIn(result.cross_type, ["golden", "death", None])
    
    def test_macd_calculation(self):
        """测试MACD计算"""
        result = self.tf.calculate_macd(self.up_trend)
        self.assertIsNotNone(result.macd)
        self.assertIsNotNone(result.signal)
        self.assertIsNotNone(result.histogram)
        self.assertIn(result.trend, ["bullish", "bearish", "neutral"])
    
    def test_momentum_calculation(self):
        """测试动量计算"""
        result = self.tf.calculate_momentum(self.up_trend)
        self.assertIsNotNone(result.momentum)
        self.assertIsNotNone(result.acceleration)
        self.assertGreaterEqual(result.strength, 0)
        self.assertLessEqual(result.strength, 1)
    
    def test_trend_direction_detection(self):
        """测试趋势方向检测"""
        up_result = self.tf.detect_trend_direction(self.up_trend)
        down_result = self.tf.detect_trend_direction(self.down_trend)
        range_result = self.tf.detect_trend_direction(self.range_bound)
        
        self.assertIn(up_result, TrendDirection)
        self.assertIn(down_result, TrendDirection)
        self.assertIn(range_result, TrendDirection)
    
    def test_all_factors_calculation(self):
        """测试所有因子计算"""
        result = self.tf.calculate_all("TEST", self.up_trend)
        self.assertIn("ma_cross_5_20_type", result)
        self.assertIn("macd", result)
        self.assertIn("momentum_5m", result)
        self.assertIn("trend_direction", result)


class TestVolatilityFactors(unittest.TestCase):
    """测试波动率因子"""
    
    def setUp(self):
        self.vf = VolatilityFactors()
        # 生成OHLC数据
        np.random.seed(42)
        n = 50
        self.prices = pd.Series(100 + np.cumsum(np.random.randn(n) * 0.5))
        self.high = self.prices * (1 + np.abs(np.random.randn(n) * 0.01))
        self.low = self.prices * (1 - np.abs(np.random.randn(n) * 0.01))
    
    def test_atr_calculation(self):
        """测试ATR计算"""
        result = self.vf.calculate_atr(self.high, self.low, self.prices)
        self.assertGreaterEqual(result.atr, 0)
        self.assertIn(result.trend, ["expanding", "contracting", "stable"])
    
    def test_bollinger_bands(self):
        """测试布林带计算"""
        result = self.vf.calculate_bollinger_bands(self.prices)
        self.assertGreater(result.upper, result.middle)
        self.assertLess(result.lower, result.middle)
        self.assertGreaterEqual(result.position, 0)
        self.assertLessEqual(result.position, 1)
    
    def test_volatility_regime(self):
        """测试波动率状态"""
        returns = self.prices.pct_change().dropna()
        result = self.vf.calculate_volatility_regime(returns)
        self.assertIn(result.regime, VolatilityRegime)
        self.assertGreaterEqual(result.current_vol, 0)
    
    def test_parkinson_volatility(self):
        """测试Parkinson波动率"""
        vol = self.vf.calculate_parkinson_volatility(self.high, self.low)
        self.assertGreaterEqual(vol, 0)
    
    def test_all_factors_calculation(self):
        """测试所有因子计算"""
        result = self.vf.calculate_all(self.prices, self.high, self.low)
        self.assertIn("atr", result)
        self.assertIn("bb_bandwidth", result)
        self.assertIn("volatility_regime", result)


class TestLiquidityFactors(unittest.TestCase):
    """测试流动性因子"""
    
    def setUp(self):
        self.lf = LiquidityFactors()
        # 模拟订单簿
        self.bids = [[100.0, 10.0], [99.5, 20.0], [99.0, 30.0]]
        self.asks = [[100.5, 10.0], [101.0, 20.0], [101.5, 30.0]]
        self.price = 100.0
    
    def test_orderbook_depth(self):
        """测试订单簿深度计算"""
        result = self.lf.calculate_orderbook_depth(self.bids, self.asks, self.price)
        self.assertGreater(result.total_depth, 0)
        self.assertGreaterEqual(result.depth_score, 0)
        self.assertLessEqual(result.depth_score, 1)
    
    def test_funding_rate_features(self):
        """测试资金费率特征"""
        result = self.lf.calculate_funding_rate_features("BTCUSDT", 0.0005)
        self.assertIsNotNone(result.current_rate)
        self.assertIn(result.trend, ["rising", "falling", "stable"])
        self.assertIn(result.signal, ["long_pays_short", "short_pays_long", "neutral"])
    
    def test_slippage_estimation(self):
        """测试滑点估计"""
        result = self.lf.estimate_slippage(self.bids, self.asks)
        self.assertGreaterEqual(result.buy_slippage_1k, 0)
        self.assertGreaterEqual(result.liquidity_score, 0)
        self.assertLessEqual(result.liquidity_score, 1)
    
    def test_spread_factors(self):
        """测试价差因子"""
        result = self.lf.calculate_spread_factors(self.bids, self.asks, self.price)
        self.assertIn("spread", result)
        self.assertIn("spread_pct", result)
        self.assertGreaterEqual(result["spread_score"], 0)


class TestCryptoFactors(unittest.TestCase):
    """测试加密货币专属因子"""
    
    def setUp(self):
        self.cf = CryptoFactors()
        self.symbol = "BTCUSDT"
        self.price = 50000.0
    
    def test_open_interest_features(self):
        """测试持仓量特征"""
        result = self.cf.calculate_open_interest_features(
            self.symbol, 10000.0, 500_000_000, self.price
        )
        self.assertIsNotNone(result.oi_value)
        self.assertIsNotNone(result.oi_usd)
        self.assertIn(result.trend, OpenInterestTrend)
    
    def test_long_short_ratio(self):
        """测试多空比"""
        result = self.cf.calculate_long_short_ratio(self.symbol, 2.5)
        self.assertEqual(result.long_short_ratio, 2.5)
        self.assertIn(result.signal, ["long_dominant", "short_dominant", "neutral"])
    
    def test_funding_momentum(self):
        """测试资金费率动量"""
        result = self.cf.calculate_funding_momentum(self.symbol, 0.001)
        self.assertIsNotNone(result.current)
        self.assertIn(result.trend, FundingTrend)
    
    def test_liquidation_risk(self):
        """测试爆仓风险"""
        oi_result = self.cf.calculate_open_interest_features(
            self.symbol, 10000.0, 500_000_000, self.price
        )
        funding_result = self.cf.calculate_funding_momentum(self.symbol, 0.002)
        
        result = self.cf.detect_liquidation_risk(
            self.symbol, oi_result, funding_result, self.price, 8.0
        )
        self.assertIn("liquidation_risk_score", result)
        self.assertIn("liquidation_risk_level", result)
    
    def test_sentiment_composite(self):
        """测试综合情绪"""
        ls_result = self.cf.calculate_long_short_ratio(self.symbol, 2.0)
        funding_result = self.cf.calculate_funding_momentum(self.symbol, 0.0008)
        oi_result = self.cf.calculate_open_interest_features(
            self.symbol, 10000.0, 500_000_000, self.price
        )
        
        result = self.cf.calculate_market_sentiment_composite(
            ls_result, funding_result, oi_result
        )
        self.assertIn("sentiment_composite", result)
        self.assertIn("sentiment_label", result)


if __name__ == '__main__':
    unittest.main()
