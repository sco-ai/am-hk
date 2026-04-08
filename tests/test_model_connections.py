#!/usr/bin/env python3
"""
模型连接测试脚本
测试Ollama本地模型和DeepSeek API
"""
import asyncio
import os
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

import aiohttp


async def test_ollama():
    """测试Ollama本地模型"""
    print("\n🦙 测试 Ollama (gemma4:31b)")
    print("-" * 50)
    
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": "gemma4:31b",
        "messages": [{"role": "user", "content": "Hello, 请用一句话确认模型运行正常"}],
        "stream": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    response = result.get("message", {}).get("content", "")
                    print(f"✅ Ollama 连接成功")
                    print(f"📝 响应: {response[:100]}...")
                    return True
                else:
                    print(f"❌ Ollama 错误: {resp.status}")
                    return False
    except Exception as e:
        print(f"❌ Ollama 连接失败: {e}")
        return False


async def test_deepseek():
    """测试DeepSeek API"""
    print("\n🧠 测试 DeepSeek API")
    print("-" * 50)
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ DeepSeek API Key 未设置")
        return False
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "Hello, 请用一句话确认API连接正常"}],
        "max_tokens": 100
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    response = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    print(f"✅ DeepSeek API 连接成功")
                    print(f"📝 响应: {response[:100]}...")
                    return True
                else:
                    error = await resp.text()
                    print(f"❌ DeepSeek 错误: {resp.status} - {error[:200]}")
                    return False
    except Exception as e:
        print(f"❌ DeepSeek 连接失败: {e}")
        return False


async def main():
    print("🚀 AM-HK 模型连接测试")
    print("=" * 50)
    
    ollama_ok = await test_ollama()
    deepseek_ok = await test_deepseek()
    
    print("\n" + "=" * 50)
    print("📊 测试结果汇总")
    print("=" * 50)
    print(f"{'✅' if ollama_ok else '❌'} Ollama (gemma4:31b)")
    print(f"{'✅' if deepseek_ok else '❌'} DeepSeek API")
    
    if ollama_ok and deepseek_ok:
        print("\n🎉 所有模型连接测试通过！")
    else:
        print("\n⚠️ 部分模型连接失败，请检查配置")


if __name__ == "__main__":
    asyncio.run(main())
