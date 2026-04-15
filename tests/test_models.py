"""
单元测试 - 模型模块
"""
import unittest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from agents.agent3_scanner.models.lightgbm_model import LightGBMModel
from agents.agent3_scanner.models.xgboost_model import XGBoostModel
from agents.agent3_scanner.models.rl_model import PPOPositionController, PositionAction
from agents.agent3_scanner.models.ensemble import ModelEnsemble


class TestLightGBMModel(unittest.TestCase):
    """测试LightGBM模型"""
    
    def setUp(self):
        self.model = LightGBMModel()
        self.test_features = {
            "price_momentum_5m": 2.5,
            "price_momentum_15m": 1.8,
            "momentum_strength": 0.7,
            "trend_score": 0.6,
            "ma_cross_5_20_strength": 0.5,
            "macd": 0.3,
            "macd_histogram": 0.1,
            "spread_score": 0.8,
            "depth_score": 0.7,
            "liquidity_score": 0.9,
            "funding_rate": 0.0002,
            "funding_extremity": 0.1,
            "oi_change_24h": 5.0,
            "long_short_ratio": 1.5,
            "sentiment_composite": 0.4,
            "contrarian_signal": False,
            "liquidation_risk_score": 0.2,
        }
    
    def test_prediction(self):
        """测试预测"""
        result = self.model.predict(self.test_features)
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 1)
        self.assertIn(result.direction, ["buy", "sell", "hold"])
        self.assertGreaterEqual(result.confidence, 0)
        self.assertLessEqual(result.confidence, 1)
    
    def test_batch_predict(self):
        """测试批量预测"""
        features_list = [self.test_features for _ in range(5)]
        results = self.model.batch_predict(features_list)
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertGreaterEqual(r.score, 0)
            self.assertLessEqual(r.score, 1)
    
    def test_feature_importance(self):
        """测试特征重要性"""
        importance = self.model.get_feature_importance(top_n=5)
        self.assertEqual(len(importance), 5)
    
    def test_health_check(self):
        """测试健康检查"""
        health = self.model.health_check()
        self.assertEqual(health["status"], "healthy")


class TestXGBoostModel(unittest.TestCase):
    """测试XGBoost模型"""
    
    def setUp(self):
        self.model = XGBoostModel()
        self.test_features = {
            "price_momentum_5m": 2.5,
            "price_momentum_15m": 1.8,
            "trend_score": 0.6,
            "macd": 0.3,
            "spread_score": 0.8,
            "depth_score": 0.7,
            "funding_rate": 0.0002,
            "oi_change_24h": 5.0,
            "long_short_ratio": 1.5,
            "sentiment_composite": 0.4,
            "liquidation_risk_score": 0.2,
        }
    
    def test_prediction(self):
        """测试预测"""
        result = self.model.predict(self.test_features)
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 1)
        self.assertIn(result.direction, ["buy", "sell", "hold"])
        self.assertIn("buy", result.probability)
        self.assertIn("sell", result.probability)
        self.assertIn("hold", result.probability)
    
    def test_batch_predict(self):
        """测试批量预测"""
        features_list = [self.test_features for _ in range(3)]
        results = self.model.batch_predict(features_list)
        self.assertEqual(len(results), 3)


class TestRLModel(unittest.TestCase):
    """测试RL仓位控制模型"""
    
    def setUp(self):
        self.model = PPOPositionController()
        self.symbol = "BTCUSDT"
        self.market_state = {
            "trend_score": 0.5,
            "volatility_ratio": 1.2,
            "liquidity_score": 0.8,
            "sentiment_composite": 0.3,
        }
    
    def test_position_decision(self):
        """测试仓位决策"""
        result = self.model.decide_position(
            self.symbol, self.market_state, 0.7, 50000.0
        )
        self.assertIn(result.action, PositionAction)
        self.assertGreaterEqual(result.target_position, 0)
        self.assertLessEqual(result.target_position, 1)
        self.assertGreaterEqual(result.confidence, 0)
    
    def test_position_state_tracking(self):
        """测试仓位状态跟踪"""
        # 第一次决策
        result1 = self.model.decide_position(
            self.symbol, self.market_state, 0.7, 50000.0
        )
        
        # 检查状态是否被记录
        state = self.model.get_position_state(self.symbol)
        self.assertIsNotNone(state)
        
        # 重置
        self.model.reset_position(self.symbol)
        state = self.model.get_position_state(self.symbol)
        self.assertIsNone(state)


class TestModelEnsemble(unittest.TestCase):
    """测试模型融合"""
    
    def setUp(self):
        self.ensemble = ModelEnsemble()
        
        # 模拟模型输出
        self.lightgbm_pred = type('obj', (object,), {
            'score': 0.7,
            'direction': 'buy',
            'confidence': 0.8,
            'feature_importance': {}
        })()
        
        self.xgboost_pred = type('obj', (object,), {
            'score': 0.65,
            'direction': 'buy',
            'confidence': 0.75,
            'probability': {'buy': 0.6, 'hold': 0.3, 'sell': 0.1}
        })()
        
        self.rl_decision = type('obj', (object,), {
            'action': type('Action', (), {'value': 'increase'})(),
            'target_position': 0.5,
            'confidence': 0.7
        })()
    
    def test_ensemble_prediction(self):
        """测试融合预测"""
        result = self.ensemble.predict(
            self.lightgbm_pred, self.xgboost_pred, self.rl_decision
        )
        self.assertGreaterEqual(result.final_score, 0)
        self.assertLessEqual(result.final_score, 1)
        self.assertIn(result.final_direction, ["buy", "sell", "hold"])
        self.assertGreaterEqual(result.position_size, 0)
        self.assertLessEqual(result.position_size, 1)
    
    def test_market_regime_adjustment(self):
        """测试市场状态权重调整"""
        result1 = self.ensemble.predict(
            self.lightgbm_pred, self.xgboost_pred, self.rl_decision, "trending_up"
        )
        result2 = self.ensemble.predict(
            self.lightgbm_pred, self.xgboost_pred, self.rl_decision, "high_volatility"
        )
        # 不同市场状态下权重应不同
        self.assertNotEqual(result1.model_weights, result2.model_weights)


if __name__ == '__main__':
    unittest.main()
