"""
简化版Agent3 Ollama测试
直接测试Ollama调用，无需完整依赖
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.ollama_adapter import get_ollama


def test_ollama_call():
    """测试Ollama调用"""
    print("🧠 测试Agent3 Ollama本地模型调用")
    print("=" * 60)
    
    # 获取Ollama实例
    ollama = get_ollama()
    
    # 1. 健康检查
    print("\n1️⃣ 检查Ollama服务状态...")
    healthy = ollama.health_check()
    print(f"   {'✅' if healthy else '❌'} Ollama服务: {'正常' if healthy else '异常'}")
    
    if not healthy:
        print("   ⚠️ Ollama服务不可用")
        return
    
    # 2. 列出模型
    print("\n2️⃣ 可用模型:")
    models = ollama.list_models()
    for m in models:
        print(f"   - {m}")
    
    # 3. 测试策略权重优化 (模拟Agent3调用)
    print("\n3️⃣ 测试策略权重优化 (模拟Agent3场景)...")
    print("   ⏳ 调用Ollama gemma4:31b...")
    print("   💡 请同时观察 nvidia-smi 确认GPU使用")
    
    prompt = """作为量化策略优化专家，请根据当前市场环境优化策略权重。

当前市场环境:
- 波动率状态: medium
- 趋势强度: 0.65
- 市场情绪: +0.30
- 资金流向: inflow
- BTC动量: +2.50%
- 美股状态: bullish

当前候选机会数量: 5

请输出JSON格式:
{
    "momentum_weight": 0.25,
    "value_weight": 0.20,
    "sentiment_weight": 0.25,
    "cross_market_weight": 0.30,
    "reasoning": "简要说明"
}
"""
    
    try:
        result = ollama.analyze(
            prompt=prompt,
            system="你是专业的量化交易策略优化专家，只输出JSON格式结果。",
            json_mode=True
        )
        
        print(f"   ✅ Ollama调用成功")
        print(f"   📊 原始响应:")
        print(f"   {result['content'][:200]}...")
        
        if result.get('parsed'):
            print(f"   📋 解析结果:")
            for k, v in result['parsed'].items():
                print(f"      - {k}: {v}")
        
        print(f"   🏷️ 使用模型: {result['model']}")
        
    except Exception as e:
        print(f"   ❌ 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. 测试个股分析 (模拟Agent3调用)
    print("\n4️⃣ 测试个股分析 (模拟Agent3场景)...")
    print("   标的: 00700 (腾讯)")
    print("   ⏳ 调用Ollama gemma4:31b...")
    
    prompt2 = """分析港股 00700 的交易机会。

市场环境:
- 波动率状态: medium
- 趋势强度: 0.65
- 市场情绪: +0.30
- 资金流向: inflow
- BTC动量: +2.50%
- 美股状态: bullish

关键因子:
- 短期动量(5m): 1.20%
- RSI: 58.0
- 主力资金比率: 0.35
- 北水强度: 0.42
- Layer1信号: 3.20
- Layer2确认: 2.10

基础评分: 0.72

请输出JSON格式:
{
    "direction": "BUY/SELL/HOLD",
    "confidence": 0.75,
    "reasoning": "简要分析理由",
    "risk_factors": ["风险1", "风险2"]
}
"""
    
    try:
        result2 = ollama.analyze(
            prompt=prompt2,
            system="你是专业的港股量化分析师，只输出JSON格式结果。",
            json_mode=True
        )
        
        print(f"   ✅ Ollama调用成功")
        print(f"   📊 原始响应:")
        print(f"   {result2['content'][:200]}...")
        
        if result2.get('parsed'):
            print(f"   📋 解析结果:")
            for k, v in result2['parsed'].items():
                print(f"      - {k}: {v}")
        
    except Exception as e:
        print(f"   ❌ 调用失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. 总结
    print("\n" + "=" * 60)
    print("📋 测试总结")
    print("=" * 60)
    print("✅ Agent3 Ollama调用测试完成")
    print("💡 请检查nvidia-smi确认GPU使用率")
    print("   预期: GPU-Util > 50% 当模型推理时")


if __name__ == "__main__":
    test_ollama_call()
