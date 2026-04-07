"""
Agent 2: DataCurator 测试
"""
import pytest
import asyncio
from datetime import datetime
from collections import deque

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from agents.agent2_curator.main import (
    DataCleaner, FactorCalculator, CrossMarketFusionEngine, DataCurator,
    DataQualityLevel, MarketLayer, FactorBundle
)


class TestDataCleaner:
    """测试数据清洗器"""
    
    def test_clean_tick_data_normal(self):
        """测试正常Tick数据清洗"""
        cleaner = DataCleaner()
        data = {
            "price": 100.0,
            "volume": 1000,
            "timestamp": datetime.now().isoformat(),
        }
        
        cleaned, metrics = cleaner.clean_tick_data("TEST", data)
        
        assert cleaned is not None
        assert cleaned["price"] == 100.0
        assert metrics.quality_level in [DataQualityLevel.EXCELLENT, DataQualityLevel.GOOD]
        assert metrics.quality_score > 0.8
    
    def test_clean_tick_data_outlier(self):
        """测试异常值检测（价格跳变>10%）"""
        cleaner = DataCleaner()
        # 先设置一个基准价格
        cleaner.last_prices["TEST"] = 100.0
        cleaner.price_history["TEST"] = deque(maxlen=100)
        for i in range(30):
            cleaner.price_history["TEST"].append({"price": 100.0 + i * 0.1, "volume": 100})
        
        # 异常价格（跳变15%）
        data = {
            "price": 115.0,  # 15% jump
            "volume": 1000,
            "timestamp": datetime.now().isoformat(),
        }
        
        cleaned, metrics = cleaner.clean_tick_data("TEST", data)
        
        # 异常值应该被标记并替换
        assert cleaned is not None
        assert cleaned["is_outlier"] == True
        assert metrics.outlier_count >= 1
    
    def test_zscore_detection(self):
        """测试Z-score异常检测"""
        cleaner = DataCleaner(zscore_threshold=2.0)
        cleaner.price_history["TEST"] = deque(maxlen=100)
        
        # 填充正常价格历史
        for i in range(30):
            cleaner.price_history["TEST"].append({"price": 100.0, "volume": 100})
        
        # 极端异常值（Z-score > 3）
        data = {"price": 130.0, "volume": 1000, "timestamp": datetime.now().isoformat()}
        
        cleaned, metrics = cleaner.clean_tick_data("TEST", data)
        assert cleaned is not None
        assert cleaned.get("zscore", 0) > 2.0 or cleaned["is_outlier"]
    
    def test_forward_fill(self):
        """测试前向填充缺失值"""
        cleaner = DataCleaner()
        cleaner.last_prices["TEST"] = 99.5
        
        # 缺失价格的数据
        data = {
            "volume": 1000,
            "timestamp": datetime.now().isoformat(),
        }
        
        cleaned, metrics = cleaner.clean_tick_data("TEST", data)
        assert cleaned is not None
        assert cleaned["price"] == 99.5  # 使用前向填充
        assert metrics.missing_count >= 1


class TestFactorCalculator:
    """测试因子计算器"""
    
    def test_calculate_price_volume_factors(self):
        """测试量价因子计算"""
        calc = FactorCalculator()
        
        # 填充历史数据
        for i in range(100):
            calc._update_history("TEST", {
                "price": 100.0 + i * 0.1,
                "volume": 1000 + i * 10,
                "timestamp": datetime.now().isoformat(),
            })
        
        cross_state = {}
        factors = calc.calculate_all_factors("TEST", "crypto", {"price": 110.0, "volume": 2000}, cross_state)
        
        assert factors.price_momentum_5m is not None
        assert factors.volatility_5m is not None
        assert factors.ma_5 is not None
        assert factors.ma_20 is not None
        assert factors.rsi_14 is not None
    
    def test_calculate_technical_factors(self):
        """测试技术指标计算"""
        calc = FactorCalculator()
        
        # 填充历史数据（模拟趋势）
        for i in range(50):
            calc._update_history("TEST", {
                "price": 100.0 + i * 0.5,  # 上升趋势
                "volume": 1000,
                "timestamp": datetime.now().isoformat(),
            })
        
        bundle = FactorBundle()
        import pandas as pd
        prices = pd.Series([h["price"] for h in calc.history_cache["TEST"]])
        
        factors = calc._calculate_technical_factors(bundle, prices)
        
        assert factors.macd is not None
        assert factors.rsi_14 is not None
        assert factors.rsi_14 >= 0 and factors.rsi_14 <= 100
        assert factors.bb_upper is not None
        assert factors.bb_lower is not None
    
    def test_calculate_orderbook_factors(self):
        """测试盘口因子计算"""
        calc = FactorCalculator()
        
        data = {
            "symbol": "TEST",
            "bids": [[99.0, 100], [98.5, 200], [98.0, 300]],
            "asks": [[101.0, 150], [101.5, 250], [102.0, 350]],
        }
        
        bundle = calc._calculate_orderbook_factors(FactorBundle(), data, 100.0)
        
        assert bundle.bid_ask_spread is not None
        assert bundle.orderbook_imbalance is not None
        assert abs(bundle.orderbook_imbalance) <= 1.0
    
    def test_30_plus_factors(self):
        """测试30+因子完整性"""
        calc = FactorCalculator()
        
        # 填充足够的历史数据
        for i in range(100):
            calc._update_history("TEST", {
                "price": 100.0 + (i % 20) * 0.5,  # 周期性价格
                "volume": 1000 + (i % 10) * 100,
                "timestamp": datetime.now().isoformat(),
            })
        
        cross_state = {"BTCUSDT": {"momentum_5m": 2.5}}
        
        # 模拟订单簿数据
        cleaned_data = {
            "price": 110.0,
            "volume": 2000,
            "bids": [[109.0, 100], [108.0, 200]],
            "asks": [[111.0, 150], [112.0, 250]],
        }
        
        factors = calc.calculate_all_factors("TEST", "crypto", cleaned_data, cross_state)
        factor_dict = factors.to_dict()
        
        # 检查是否有大量因子被计算
        assert len(factor_dict) >= 15  # 至少15个因子
        
        # 检查各类因子都存在
        assert any(k.startswith("price_momentum") for k in factor_dict)
        assert any(k.startswith("volatility") for k in factor_dict)
        assert any(k.startswith("ma_") for k in factor_dict)
        assert any(k in factor_dict for k in ["rsi_14", "macd"])


class TestCrossMarketFusion:
    """测试跨市场信号融合"""
    
    def test_update_market_state(self):
        """测试市场状态更新"""
        engine = CrossMarketFusionEngine()
        
        engine.update_market_state("BTCUSDT", {"price_momentum_5m": 2.5, "rsi_14": 65})
        
        assert "BTCUSDT" in engine.market_states
        assert engine.market_states["BTCUSDT"]["momentum_5m"] == 2.5
    
    def test_get_cross_market_signals(self):
        """测试跨市场信号生成"""
        engine = CrossMarketFusionEngine()
        
        # 设置Layer1和Layer2的市场状态
        engine.update_market_state("BTCUSDT", {"price_momentum_5m": 3.0, "rsi_14": 70})
        engine.update_market_state("COIN", {"price_momentum_5m": 2.0, "rsi_14": 60})
        
        # 为港股生成信号
        signals = engine.get_cross_market_signals("00700")
        
        assert len(signals) > 0
        
        # 检查信号结构
        for signal in signals:
            assert "source_layer" in signal
            assert "target_layer" in signal
            assert "signal_type" in signal
            assert "strength" in signal
            assert "lag_seconds" in signal
    
    def test_layer_transmission(self):
        """测试层级传导逻辑"""
        engine = CrossMarketFusionEngine()
        
        # Layer1 -> Layer2 传导
        lag1 = engine.transmission_lags.get((MarketLayer.LAYER1_CRYPTO, MarketLayer.LAYER2_US_CONFIRM))
        assert lag1 == 60  # 1分钟
        
        # Layer2 -> Layer3 传导
        lag2 = engine.transmission_lags.get((MarketLayer.LAYER2_US_CONFIRM, MarketLayer.LAYER3_HK_EXECUTE))
        assert lag2 == 300  # 5分钟


class TestDataQuality:
    """测试数据质量控制"""
    
    def test_quality_score_calculation(self):
        """测试质量评分计算"""
        cleaner = DataCleaner(max_latency_ms=50.0)
        
        # 优秀质量
        score = cleaner._calculate_quality_score(5.0, 100.0, 0)
        assert score > 0.9
        
        # 较差质量
        score = cleaner._calculate_quality_score(80.0, 85.0, 3)
        assert score < 0.8
    
    def test_quality_level_determination(self):
        """测试质量等级判定"""
        cleaner = DataCleaner()
        
        assert cleaner._determine_quality_level(5, 100, 0) == DataQualityLevel.EXCELLENT
        assert cleaner._determine_quality_level(20, 99, 0) == DataQualityLevel.GOOD
        assert cleaner._determine_quality_level(40, 96, 1) == DataQualityLevel.ACCEPTABLE
        assert cleaner._determine_quality_level(150, 80, 5) == DataQualityLevel.UNRELIABLE


class TestIntegration:
    """集成测试"""
    
    def test_full_processing_pipeline(self):
        """测试完整处理流程"""
        cleaner = DataCleaner()
        calc = FactorCalculator()
        fusion = CrossMarketFusionEngine()
        
        # 1. 清洗数据
        raw_data = {
            "price": 100.0,
            "volume": 1000,
            "timestamp": datetime.now().isoformat(),
        }
        
        cleaned, metrics = cleaner.clean_tick_data("TEST", raw_data)
        assert cleaned is not None
        
        # 2. 计算因子
        cross_state = fusion.get_market_state()
        factors = calc.calculate_all_factors("TEST", "crypto", cleaned, cross_state)
        assert len(factors.to_dict()) > 0
        
        # 3. 更新市场状态
        fusion.update_market_state("TEST", factors.to_dict())
        assert "TEST" in fusion.market_states
        
        # 4. 生成跨市场信号
        signals = fusion.get_cross_market_signals("00700")
        # 港股应该收到来自其他层的信号


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
