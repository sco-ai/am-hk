"""
单元测试主入口
"""
import unittest
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 导入所有测试模块
from tests.test_factors import TestTrendFactors, TestVolatilityFactors, TestLiquidityFactors, TestCryptoFactors
from tests.test_models import TestLightGBMModel, TestXGBoostModel, TestRLModel, TestModelEnsemble
from tests.test_market_state import TestMarketStateEngine, TestVolatilityRegimeDetector, TestAdaptiveWeightAdjuster
from tests.test_risk import TestPositionSizer, TestStopLossManager, TestRiskManager


def run_all_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加因子测试
    suite.addTests(loader.loadTestsFromTestCase(TestTrendFactors))
    suite.addTests(loader.loadTestsFromTestCase(TestVolatilityFactors))
    suite.addTests(loader.loadTestsFromTestCase(TestLiquidityFactors))
    suite.addTests(loader.loadTestsFromTestCase(TestCryptoFactors))
    
    # 添加模型测试
    suite.addTests(loader.loadTestsFromTestCase(TestLightGBMModel))
    suite.addTests(loader.loadTestsFromTestCase(TestXGBoostModel))
    suite.addTests(loader.loadTestsFromTestCase(TestRLModel))
    suite.addTests(loader.loadTestsFromTestCase(TestModelEnsemble))
    
    # 添加市场状态测试
    suite.addTests(loader.loadTestsFromTestCase(TestMarketStateEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestVolatilityRegimeDetector))
    suite.addTests(loader.loadTestsFromTestCase(TestAdaptiveWeightAdjuster))
    
    # 添加风控测试
    suite.addTests(loader.loadTestsFromTestCase(TestPositionSizer))
    suite.addTests(loader.loadTestsFromTestCase(TestStopLossManager))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskManager))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    result = run_all_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
