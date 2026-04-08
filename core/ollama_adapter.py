"""
Ollama模型适配器
将外部API调用替换为本地Ollama调用
用于Agent3/5/6/7
"""
import json
import logging
from typing import Dict, List, Optional
import urllib.request
import urllib.error

logger = logging.getLogger("ollama_adapter")


class OllamaAdapter:
    """
    Ollama适配器 - 替代外部API
    所有Agent通过此类调用本地模型
    """
    
    DEFAULT_MODEL = "gemma4:31b"
    DEFAULT_URL = "http://localhost:11434"
    
    def __init__(self, model: str = None, api_url: str = None):
        self.model = model or self.DEFAULT_MODEL
        self.api_url = api_url or self.DEFAULT_URL
    
    def chat(self, 
             messages: List[Dict[str, str]], 
             temperature: float = 0.2,
             max_tokens: int = 800,
             json_mode: bool = True) -> Dict:
        """
        调用Ollama进行对话
        
        Args:
            messages: [{"role": "system/user", "content": "..."}]
            temperature: 温度
            max_tokens: 最大token数
            json_mode: 是否要求JSON输出
        
        Returns:
            {"content": str, "model": str, "usage": {...}}
        """
        try:
            # 构建prompt
            prompt = self._build_prompt(messages)
            
            if json_mode:
                prompt += "\n\n请以JSON格式输出结果。"
            
            data = json.dumps({
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json" if json_mode else None,
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
                
                return {
                    "content": result.get("response", ""),
                    "model": self.model,
                    "usage": {
                        "prompt_tokens": result.get("prompt_eval_count", 0),
                        "completion_tokens": result.get("eval_count", 0),
                    }
                }
            
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise
    
    def analyze(self, prompt: str, system: str = None, json_mode: bool = True) -> Dict:
        """
        简化版分析调用
        
        Args:
            prompt: 用户提示
            system: 系统提示
            json_mode: 是否要求JSON输出
        
        Returns:
            {"content": str, "parsed": Dict}
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        result = self.chat(messages, json_mode=json_mode)
        content = result["content"]
        
        # 尝试解析JSON
        parsed = None
        if json_mode:
            try:
                parsed = json.loads(content)
            except:
                # 尝试从文本中提取JSON
                try:
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        parsed = json.loads(content[start:end])
                except:
                    pass
        
        return {
            "content": content,
            "parsed": parsed,
            "model": result["model"],
        }
    
    def _build_prompt(self, messages: List[Dict[str, str]]) -> str:
        """构建Ollama格式的prompt"""
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
        except:
            return []


# === 全局实例 ===
_ollama_instance: Optional[OllamaAdapter] = None

def get_ollama() -> OllamaAdapter:
    """获取全局Ollama实例"""
    global _ollama_instance
    if _ollama_instance is None:
        _ollama_instance = OllamaAdapter()
    return _ollama_instance


def reset_ollama(model: str = None):
    """重置Ollama实例（用于切换模型）"""
    global _ollama_instance
    _ollama_instance = OllamaAdapter(model=model)
