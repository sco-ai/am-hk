"""
本地Ollama模型客户端 (GPU加速)
用于Agent本地推理
"""
import json
import logging
from typing import Dict, List, Optional
import urllib.request
import urllib.error

logger = logging.getLogger("ollama_client")


class OllamaClient:
    """
    Ollama本地模型客户端
    使用本地GPU进行推理
    """
    
    def __init__(self, model: str = "gemma4:31b", api_url: str = "http://localhost:11434"):
        self.model = model
        self.api_url = api_url
    
    def chat(self, 
             messages: List[Dict[str, str]], 
             temperature: float = 0.2,
             max_tokens: int = 800) -> str:
        """
        调用Ollama进行对话 (同步版本)
        
        Args:
            messages: [{"role": "system/user", "content": "..."}]
            temperature: 温度
            max_tokens: 最大token数
        
        Returns:
            模型回复文本
        """
        try:
            # 构建prompt (Ollama原生格式)
            prompt = self._build_prompt(messages)
            
            data = json.dumps({
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }).encode('utf-8')
            
            req = urllib.request.Request(
                f"{self.api_url}/api/generate",
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get("response", "")
            
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise
    
    def _build_prompt(self, messages: List[Dict[str, str]]) -> str:
        """构建Ollama原生格式的prompt"""
        prompt_parts = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        prompt_parts.append("Assistant:")
        return "\n\n".join(prompt_parts)
    
    def health_check(self) -> bool:
        """检查Ollama服务状态"""
        try:
            req = urllib.request.Request(f"{self.api_url}/api/tags", method='GET')
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except:
            return False
    
    def list_models(self) -> List[str]:
        """列出可用模型"""
        try:
            req = urllib.request.Request(f"{self.api_url}/api/tags", method='GET')
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []


# === 便捷函数 ===

def ollama_chat(prompt: str, 
                model: str = "gemma4:31b",
                system: str = None) -> str:
    """
    快速调用Ollama
    
    Usage:
        response = ollama_chat("分析比特币走势", system="你是交易分析师")
    """
    client = OllamaClient(model=model)
    
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    return client.chat(messages)


# === 测试 ===

def test_ollama():
    """测试Ollama连接"""
    print("🧠 测试Ollama本地模型 (GPU)")
    print("=" * 60)
    
    client = OllamaClient()
    
    # 1. 检查健康状态
    print("\n1️⃣ 检查Ollama服务...")
    healthy = client.health_check()
    if healthy:
        print("   ✅ Ollama服务正常")
    else:
        print("   ❌ Ollama服务不可用")
        return
    
    # 2. 列出模型
    print("\n2️⃣ 可用模型:")
    models = client.list_models()
    for m in models:
        print(f"   - {m}")
    
    # 3. 测试推理 (触发GPU)
    print("\n3️⃣ 测试推理 (将使用GPU)...")
    print("   提示: 分析港股腾讯(00700)的投资价值")
    print("   ⏳ 正在生成，请稍候...")
    
    try:
        response = ollama_chat(
            prompt="请简要分析港股腾讯(00700)当前的投资价值，给出BUY/SELL/HOLD建议",
            system="你是专业港股分析师，只给出简洁结论",
            model="gemma4:31b"
        )
        print(f"\n   📝 模型回复:\n   {response[:200]}...")
        print("\n   ✅ 推理完成 (请检查nvidia-smi确认GPU使用)")
    except Exception as e:
        print(f"   ❌ 推理失败: {e}")


if __name__ == "__main__":
    test_ollama()
