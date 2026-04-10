"""
单元测试 - 风控系统
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.risk.position_sizer import PositionSizer, PositionSizeResult
from core.risk.stop_loss import StopLossManager, StopType, StopLossResult
from core.risk.risk_manager import RiskManager, RiskLevel


class TestPositionSizer(unittest.TestCase):
    """测试仓位管理器"""
    
    def setUp(self):
        self.sizer = PositionSizer(
            max_position_pct=0.3,
            max_risk_per_trade=0.02,
            account_risk_limit=0.06
        )
        self.symbol = "BTCUSDT"
    
    def test_position_size_calculation(self):
        """测试仓位计算"""
        result = self.sizer.calculate_position_size(
            symbol=self.symbol,
            signal_strength=0.8,
            confidence=0.75,
            volatility=50.0,
            liquidity_score=0.8,
            stop_loss_pct=0.02,
            portfolio_value=100000.0,
            correlation_with_portfolio=0.3
        )
        self.assertIsInstance(result, PositionSizeResult)
        self.assertGreaterEqual(result.target_position, 0)
        self.assertLessEqual(result.target_position, 0.3)
    
    def test_high_volatility_reduction(self):
        """测试高波动率降低仓位"""
        result_low_vol = self.sizer.calculate_position_size(
            self.symbol, 0.8, 0.75, 30.0, 0.8, 0.02, 100000.0
        )
        result_high_vol = self.sizer.calculate_position_size(
            self.symbol, 0.8, 0.75, 100.0, 0.8, 0.02, 100000.0
        )
        self.assertLess(result_high_vol.target_position, result_low_vol.target_position)
    
    def test_position_tracking(self):
        """测试仓位跟踪"""
        self.sizer.update_position(self.symbol, 0.15)
        pos = self.sizer.get_position(self.symbol)
        self.assertEqual(pos, 0.15)
        
        self.sizer.close_position(self.symbol)
        pos = self.sizer.get_position(self.symbol)
        self.assertEqual(pos, 0.0)


class TestStopLossManager(unittest.TestCase):
    """测试止损管理器"""
    
    def setUp(self):
        self.manager = StopLossManager()
        self.symbol = "BTCUSDT"
    
    def test_fixed_stop_registration(self):
        """测试固定止损注册"""
        self.manager.register_position(self.symbol, 50000.0, "long", StopType.FIXED)
        info = self.manager.get_position_info(self.symbol)
        self.assertIsNotNone(info)
        self.assertEqual(info["direction"], "long")
    
    def test_stop_trigger_long(self):
        """测试多头止损触发"""
        self.manager.register_position(self.symbol, 50000.0, "long", StopType.FIXED, 0.02)
        result = self.manager.check_stop(self.symbol, 48900.0)
        self.assertTrue(result.should_exit)
    
    def test_no_stop_trigger(self):
        """测试未触发止损"""
        self.manager.register_position(self.symbol, 50000.0, "long", StopType.FIXED, 0.02)
        result = self.manager.check_stop(self.symbol, 49900.0)
        self.assertFalse(result.should_exit)


class TestRiskManager(unittest.TestCase):
    """测试组合风控管理器"""
    
    def setUp(self):
        self.manager = RiskManager()
    
    def test_risk_check_basic(self):
        """测试基础风险检查"""
        positions = {"BTCUSDT": {"size": 0.01, "price": 50000, "value": 500}}
        result = self.manager.check_risk(100000.0, positions)
        self.assertIsInstance(result.passed, bool)
        self.assertIn(result.risk_level, RiskLevel)
    
    def test_risk_metrics(self):
        """测试风险指标"""
        positions = {"BTCUSDT": {"size": 0.01, "price": 50000, "value": 500}}
        result = self.manager.check_risk(100000.0, positions)
        self.assertGreaterEqual(result.total_exposure, 0)
        self.assertIsInstance(result.violations, list)
        self.assertIsInstance(result.warnings, list)


if __name__ == '__main__':
    unittest.main()
