"""
测试Agent3 Ollama本地模型调用
验证GPU使用情况
"""
import asyncio
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from agents.agent3_scanner.main import AlphaScanner, MarketContext, OpportunityPool, Direction
from core.ollama_adapter import get_ollama


async def test_agent3_ollama():
    """测试Agent3 Ollama调用"""
    print("🧠 测试Agent3 Ollama本地模型调用")
    print("=" * 60)
    
    # 1. 检查Ollama健康状态
    print("\n1️⃣ 检查Ollama服务状态...")
    scanner = AlphaScanner()
    healthy = scanner.health_check()
    print(f"   {'✅' if healthy else '❌'} Ollama服务: {'正常' if healthy else '异常'}")
    
    if not healthy:
        print("   ⚠️ Ollama服务不可用，测试中止")
        return
    
    # 2. 创建市场环境上下文
    print("\n2️⃣ 创建市场环境...")
    context = MarketContext(
        timestamp=1712553600,
        volatility_regime="medium",
        trend_strength=0.65,
        market_sentiment=0.3,
        capital_flow_direction="inflow",
        btc_momentum=2.5,
        us_market_state="bullish"
    )
    print("   ✅ 市场环境创建完成")
    
    # 3. 测试策略权重优化 (关键测试 - 调用Ollama)
    print("\n3️⃣ 测试策略权重优化 (将触发Ollama调用)...")
    print("   ⏳ 调用本地模型 gemma4:31b...")
    print("   💡 请同时观察 nvidia-smi 确认GPU使用")
    
    try:
        weights = await scanner.optimize_strategy_weights([], context)
        print(f"   ✅ Ollama优化完成")
        print(f"   📊 优化权重:")
        for k, v in weights.items():
            print(f"      - {k}: {v:.2f}")
    except Exception as e:
        print(f"   ❌ 优化失败: {e}")
    
    # 4. 测试个股分析 (关键测试 - 调用Ollama)
    print("\n4️⃣ 测试个股机会分析 (将触发Ollama调用)...")
    print("   标的: 00700 (腾讯)")
    print("   ⏳ 调用本地模型 gemma4:31b...")
    
    test_factors = {
        "price_momentum_5m": 1.2,
        "price_momentum_15m": 2.5,
        "rsi_14": 58.0,
        "main_force_ratio": 0.35,
        "northbound_strength": 0.42,
        "layer1_signal": 3.2,
        "layer2_confirm": 2.1,
        "orderbook_imbalance": 0.15,
        "crypto_correlation": 0.45,
    }
    
    try:
        opp = await scanner.analyze_opportunity("00700", test_factors, context)
        print(f"   ✅ 分析完成")
        print(f"   📈 方向: {opp.direction.value}")
        print(f"   📊 置信度: {opp.confidence:.2%}")
        print(f"   📝 推理: {opp.reasoning[:100]}...")
        print(f"   ⏱️ 处理时间: {opp.processing_time_ms:.0f}ms")
        print(f"   🏷️ 模型版本: {opp.model_version}")
    except Exception as e:
        print(f"   ❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. 总结
    print("\n" + "=" * 60)
    print("📋 测试总结")
    print("=" * 60)
    print("✅ Agent3 Ollama集成测试完成")
    print("💡 请检查nvidia-smi确认GPU使用率上升")
    print("   预期: GPU-Util > 50% 当模型推理时")


if __name__ == "__main__":
    asyncio.run(test_agent3_ollama())
