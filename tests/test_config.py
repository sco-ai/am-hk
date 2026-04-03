#!/usr/bin/env python3
"""
AM-HK 配置验证测试
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

def test_config():
    """测试配置加载"""
    print("=" * 60)
    print("配置验证测试")
    print("=" * 60)
    print()
    
    try:
        from core.config import settings
        print("✓ 配置加载成功")
        print(f"  - 币安API: {'已配置' if settings.BINANCE_API_KEY else '未配置'}")
        print(f"  - 老虎API: {'已配置' if settings.TIGER_ACCOUNT else '未配置'}")
        print(f"  - 飞书Webhook: {'已配置' if settings.FEISHU_WEBHOOK_URL else '未配置'}")
        print(f"  - API端口: {settings.API_PORT}")
        print()
        return True
    except Exception as e:
        print(f"✗ 配置加载失败: {e}")
        return False

def test_modules():
    """测试模块导入"""
    print("=" * 60)
    print("模块导入测试")
    print("=" * 60)
    print()
    
    modules = [
        'core.models',
        'core.config',
        'core.utils',
        'core.kafka.config',
        'core.feishu',
        'core.feishu_commands',
    ]
    
    errors = []
    for mod in modules:
        try:
            __import__(mod)
            print(f'✓ {mod}')
        except Exception as e:
            errors.append((mod, str(e)))
            print(f'✗ {mod}: {e}')
    
    print()
    if errors:
        print(f"⚠️  {len(errors)}个模块导入失败")
        return False
    else:
        print(f"✅ 所有{len(modules)}个模块检查通过")
        return True

def test_agents():
    """测试Agent导入"""
    print()
    print("=" * 60)
    print("Agent模块测试")
    print("=" * 60)
    print()
    
    agents = [
        'agents.agent1_harvester.main',
        'agents.agent2_curator.main',
        'agents.agent3_scanner.main',
        'agents.agent4_oracle.main',
        'agents.agent5_guardian.main',
        'agents.agent6_learning.main',
    ]
    
    for agent in agents:
        try:
            __import__(agent)
            print(f'✓ {agent}')
        except Exception as e:
            print(f'✗ {agent}: {e}')
    
    print()
    return True

if __name__ == "__main__":
    success = True
    success = test_config() and success
    success = test_modules() and success
    success = test_agents() and success
    
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    if success:
        print("✅ 所有测试通过")
    else:
        print("⚠️ 部分测试失败")
    sys.exit(0 if success else 1)
