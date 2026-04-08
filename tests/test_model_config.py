#!/usr/bin/env python3
"""
Agent模型配置测试脚本
测试各Agent的模型连接和配置
"""
import asyncio
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.model_manager import ModelManager


async def test_agent_model(agent_name: str, model_mgr: ModelManager):
    """测试单个Agent的模型配置"""
    config = model_mgr.get_agent_config(agent_name)
    
    print(f"\n{'='*60}")
    print(f"测试 Agent: {agent_name}")
    print(f"{'='*60}")
    print(f"描述: {config.get('description', 'N/A')}")
    print(f"模型类型: {config.get('model_type', 'N/A')}")
    print(f"是否本地: {'✅ 本地' if config.get('local') else '☁️ API'}")
    
    if config.get('model_type') == 'ollama':
        print(f"Ollama模型: {config.get('model_name')}")
        print(f"Ollama地址: {config.get('ollama_host')}")
    elif config.get('model_type') == 'api':
        print(f"API提供商: {config.get('provider')}")
        print(f"API模型: {config.get('model_name')}")
        print(f"API地址: {config.get('api_base')}")
    
    # 测试连接
    print(f"\n连接测试...")
    connected = await model_mgr.test_connection(agent_name)
    
    if connected:
        print(f"✅ {agent_name} 模型配置正确，连接成功")
    else:
        print(f"❌ {agent_name} 连接失败，请检查配置")
    
    return connected


async def main():
    """主测试函数"""
    print("🚀 AM-HK Agent模型配置测试")
    print("=" * 60)
    
    model_mgr = ModelManager()
    
    # 所有Agent
    agents = [
        "agent1_harvester",
        "agent2_curator", 
        "agent3_scanner",
        "agent4_oracle",
        "agent5_guardian",
        "agent6_learning",
        "agent7_analyzer"
    ]
    
    results = {}
    
    for agent in agents:
        try:
            connected = await test_agent_model(agent, model_mgr)
            results[agent] = connected
        except Exception as e:
            print(f"❌ 测试 {agent} 时出错: {e}")
            results[agent] = False
    
    # 汇总
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for agent, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {agent}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有Agent模型配置测试通过!")
    else:
        print("⚠️ 部分Agent配置有问题，请检查")
    
    await model_mgr.close()


if __name__ == "__main__":
    asyncio.run(main())
