"""
Agent 6 测试脚本
"""
import asyncio
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from agents.agent6_learning.main import LearningFeedback
from agents.agent6_learning.modules import (
    LightGBMTrainer,
    KellyOptimizer,
    ModelVersionManager,
    ModelEvaluator,
)

async def test_lightgbm():
    """测试LightGBM训练器"""
    print("\n=== Testing LightGBM Trainer ===")
    trainer = LightGBMTrainer()
    
    # 添加样本
    for i in range(10):
        trainer.add_sample({
            "symbol": "BTCUSDT",
            "factors": {
                "mom_5m": 0.01,
                "rsi": 55,
                "macd": 0.02,
                "volatility_5m": 0.015,
            },
            "pnl": 100 if i % 3 == 0 else -50,
            "signal_confidence": 0.7,
        })
    
    print(f"Buffer size: {len(trainer.training_buffer)}")
    print(f"Has enough data: {trainer.has_enough_data()}")
    
    # 测试训练
    if trainer.has_enough_data():
        result = await trainer.incremental_train([])
        print(f"Training result: {result}")
    
    print("✓ LightGBM test passed")

async def test_kelly():
    """测试凯利公式"""
    print("\n=== Testing Kelly Optimizer ===")
    optimizer = KellyOptimizer()
    
    # 创建测试交易数据
    trade_history = []
    for i in range(100):
        trade_history.append({
            "symbol": "BTCUSDT",
            "pnl": 150 if i % 3 == 0 else -80,
            "pnl_pct": 0.015 if i % 3 == 0 else -0.008,
        })
    
    result = optimizer.optimize(trade_history, window_size=100)
    print(f"Kelly result: {result}")
    
    # 测试预期增长率
    growth = optimizer.calculate_expected_growth(result)
    print(f"Expected growth: {growth:.4f}")
    
    # 测试回撤风险
    risk = optimizer.calculate_drawdown_risk(result)
    print(f"Drawdown risk: {risk}")
    
    print("✓ Kelly optimizer test passed")

async def test_model_manager():
    """测试模型版本管理"""
    print("\n=== Testing Model Version Manager ===")
    manager = ModelVersionManager(config_path="/tmp/test_model_versions.json")
    
    # 创建新版本
    v1 = manager.bump_version("lightgbm", {"accuracy": 0.6})
    print(f"Created version: {v1}")
    
    v2 = manager.bump_version("lightgbm", {"accuracy": 0.65})
    print(f"Created version: {v2}")
    
    # 检查当前版本
    print(f"Current versions: {manager.get_current_versions()}")
    
    # 设置A/B测试
    ab_config = manager.setup_ab_test("lightgbm", v2)
    print(f"AB test config: {ab_config}")
    
    print("✓ Model manager test passed")

async def test_evaluator():
    """测试评估器"""
    print("\n=== Testing Model Evaluator ===")
    evaluator = ModelEvaluator()
    
    # 创建测试数据
    trade_history = []
    for i in range(100):
        trade_history.append({
            "symbol": "BTCUSDT" if i % 2 == 0 else "ETHUSDT",
            "factors": {"mom_5m": 0.01, "rsi": 55},
            "pnl": 100 if i % 3 == 0 else -50,
            "pnl_pct": 0.01 if i % 3 == 0 else -0.005,
            "predicted_return": 0.012 if i % 3 == 0 else -0.004,
            "signal_confidence": 0.7,
        })
    
    model_versions = {
        "lightgbm": "v1.1",
        "informer": "v1.0",
        "ppo": "v1.0",
        "gnn": "v1.0",
    }
    
    results = evaluator.evaluate_all_models(trade_history, model_versions)
    print(f"Evaluation results: {json.dumps(results, indent=2)}")
    
    # 生成报告
    report = evaluator.generate_report(results)
    print(f"\nReport preview:\n{report[:500]}...")
    
    print("✓ Evaluator test passed")

async def main():
    print("="*60)
    print("Agent 6 - LearningFeedback Test Suite")
    print("="*60)
    
    try:
        await test_lightgbm()
        await test_kelly()
        await test_model_manager()
        await test_evaluator()
        
        print("\n" + "="*60)
        print("All tests passed! ✓")
        print("="*60)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import json
    asyncio.run(main())
