"""
模型管理器 - 统一封装Ollama和API调用
"""
import os
import json
import logging
from typing import Dict, Optional, Any, AsyncGenerator
import aiohttp
import yaml

logger = logging.getLogger(__name__)


class ModelManager:
    """统一管理Ollama本地模型和API模型"""
    
    def __init__(self, config_path: str = "config/models.yaml"):
        self.config = self._load_config(config_path)
        self.ollama_host = self.config.get("ollama", {}).get("host", "http://localhost:11434")
        self.session: Optional[aiohttp.ClientSession] = None
        
    def _load_config(self, path: str) -> Dict:
        """加载模型配置"""
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load model config: {e}")
            return {}
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def get_agent_config(self, agent_name: str) -> Dict:
        """获取Agent的模型配置"""
        agents = self.config.get("agents", {})
        return agents.get(agent_name, {})
    
    async def chat(self, agent_name: str, messages: list, stream: bool = False) -> str:
        """
        统一Chat接口
        
        Args:
            agent_name: Agent名称
            messages: 消息列表 [{"role": "user", "content": "..."}]
            stream: 是否流式输出
            
        Returns:
            模型回复文本
        """
        config = self.get_agent_config(agent_name)
        model_type = config.get("model_type")
        
        if model_type == "none" or model_type == "statistical":
            return ""
            
        elif model_type == "ollama":
            return await self._call_ollama(config, messages, stream)
            
        elif model_type == "api":
            return await self._call_api(config, messages, stream)
            
        else:
            logger.warning(f"Unknown model type: {model_type} for {agent_name}")
            return ""
    
    async def _call_ollama(self, config: Dict, messages: list, stream: bool = False) -> str:
        """调用Ollama本地模型"""
        model_name = config.get("model_name", "gemma4:31b")
        host = config.get("ollama_host", self.ollama_host)
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", 2048)
        
        url = f"{host}/api/chat"
        
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Ollama error: {error_text}")
                    return ""
                    
                if stream:
                    # 流式处理
                    full_response = ""
                    async for line in resp.content:
                        if line:
                            try:
                                data = json.loads(line)
                                if "message" in data and "content" in data["message"]:
                                    full_response += data["message"]["content"]
                            except:
                                pass
                    return full_response
                else:
                    # 非流式
                    result = await resp.json()
                    return result.get("message", {}).get("content", "")
                    
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return ""
    
    async def _call_api(self, config: Dict, messages: list, stream: bool = False) -> str:
        """调用API模型"""
        provider = config.get("provider")
        model_name = config.get("model_name")
        api_base = config.get("api_base")
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", 2048)
        
        # 获取API Key
        api_key = os.getenv("DEEPSEEK_API_KEY") if provider == "deepseek" else \
                  os.getenv("OPENAI_API_KEY") if provider == "openai" else \
                  os.getenv("KIMI_API_KEY") if provider == "kimi" else None
        
        if not api_key:
            logger.error(f"API key not found for {provider}")
            return ""
        
        url = f"{api_base}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        try:
            session = await self._get_session()
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"API error: {error_text}")
                    return ""
                
                result = await resp.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
        except Exception as e:
            logger.error(f"API call failed: {e}")
            return ""
    
    async def test_connection(self, agent_name: str) -> bool:
        """测试模型连接"""
        config = self.get_agent_config(agent_name)
        model_type = config.get("model_type")
        
        if model_type in ["none", "statistical"]:
            return True
            
        elif model_type == "ollama":
            host = config.get("ollama_host", self.ollama_host)
            model = config.get("model_name")
            
            try:
                session = await self._get_session()
                async with session.get(f"{host}/api/tags") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m.get("name") for m in data.get("models", [])]
                        if model in models:
                            logger.info(f"✅ Ollama model {model} is available")
                            return True
                        else:
                            logger.warning(f"⚠️ Model {model} not found in Ollama")
                            return False
                    else:
                        logger.error(f"❌ Ollama server not responding")
                        return False
            except Exception as e:
                logger.error(f"❌ Ollama connection failed: {e}")
                return False
                
        elif model_type == "api":
            provider = config.get("provider")
            api_key = os.getenv(f"{provider.upper()}_API_KEY")
            
            if api_key:
                logger.info(f"✅ API key for {provider} is configured")
                return True
            else:
                logger.error(f"❌ API key for {provider} not found")
                return False
        
        return False
    
    async def close(self):
        """关闭连接"""
        if self.session:
            await self.session.close()


# 全局模型管理器实例
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """获取全局模型管理器实例"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
