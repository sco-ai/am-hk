"""
AI模型客户端
集成外部AI服务：Informer、GPT-4.1、DeepSeek等
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import httpx

from core.config import settings
from core.utils import CircuitBreaker, setup_logging

logger = setup_logging("ai_models")


class BaseAIModel(ABC):
    """AI模型基类"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.circuit_breaker = CircuitBreaker()
        logger.info(f"AI model initialized: {model_name}")
    
    @abstractmethod
    async def predict(self, data: Dict) -> Dict:
        """执行预测"""
        pass


class InformerModel(BaseAIModel):
    """
    Informer时间序列预测模型
    
    长序列时间序列预测，适用于价格预测
    """
    
    def __init__(self, api_url: Optional[str] = None):
        super().__init__("informer")
        self.api_url = api_url or settings.INFORMER_API_URL or "https://api.informer.example.com"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def predict(self, data: Dict) -> Dict:
        """
        执行时间序列预测
        
        Args:
            data: {
                "symbol": str,
                "prices": List[float],  # 历史价格序列
                "prediction_length": int,  # 预测长度
            }
        
        Returns:
            {
                "predictions": List[float],  # 预测价格序列
                "confidence": float,
                "attention_weights": List[float],
            }
        """
        try:
            response = await self.client.post(
                f"{self.api_url}/predict",
                json=data,
                headers={"Authorization": f"Bearer {settings.INFORMER_API_KEY}"},
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Informer prediction: {data['symbol']} "
                       f"pred_length={len(result.get('predictions', []))}")
            
            return result
        
        except Exception as e:
            logger.error(f"Informer prediction failed: {e}")
            # Fallback to simple moving average
            return self._fallback_predict(data)
    
    def _fallback_predict(self, data: Dict) -> Dict:
        """Fallback预测（简单移动平均）"""
        prices = data.get("prices", [])
        pred_len = data.get("prediction_length", 5)
        
        if len(prices) < 10:
            return {
                "predictions": [prices[-1]] * pred_len if prices else [0] * pred_len,
                "confidence": 0.3,
                "attention_weights": [],
                "source": "fallback_ma",
            }
        
        # 简单移动平均预测
        ma_short = sum(prices[-5:]) / 5
        ma_long = sum(prices[-20:]) / 20 if len(prices) >= 20 else ma_short
        
        trend = (ma_short - ma_long) / ma_long if ma_long > 0 else 0
        last_price = prices[-1]
        
        predictions = []
        for i in range(pred_len):
            pred = last_price * (1 + trend * (i + 1) * 0.1)
            predictions.append(pred)
        
        return {
            "predictions": predictions,
            "confidence": 0.4,
            "attention_weights": [],
            "source": "fallback_ma",
        }


class NHITSModel(BaseAIModel):
    """
    N-HiTS时间序列模型
    
    趋势分解预测，适用于波动分析
    """
    
    def __init__(self, api_url: Optional[str] = None):
        super().__init__("n-hits")
        self.api_url = api_url or settings.NHITS_API_URL or "https://api.nhits.example.com"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def predict(self, data: Dict) -> Dict:
        """
        执行趋势分解预测
        
        Returns:
            {
                "trend": List[float],
                "seasonal": List[float],
                "residual": List[float],
                "forecast": List[float],
            }
        """
        try:
            response = await self.client.post(
                f"{self.api_url}/decompose",
                json=data,
                headers={"Authorization": f"Bearer {settings.NHITS_API_KEY}"},
            )
            response.raise_for_status()
            return response.json()
        
        except Exception as e:
            logger.error(f"N-HiTS prediction failed: {e}")
            return self._fallback_decompose(data)
    
    def _fallback_decompose(self, data: Dict) -> Dict:
        """Fallback分解"""
        prices = data.get("prices", [])
        pred_len = data.get("prediction_length", 5)
        
        return {
            "trend": prices[-pred_len:] if len(prices) >= pred_len else prices + [prices[-1]] * (pred_len - len(prices)),
            "seasonal": [0] * pred_len,
            "residual": [0] * pred_len,
            "forecast": [prices[-1] if prices else 0] * pred_len,
            "source": "fallback",
        }


class RLTradingModel(BaseAIModel):
    """
    强化学习交易模型（PPO）
    
    云训练模型，用于交易决策
    """
    
    def __init__(self, api_url: Optional[str] = None):
        super().__init__("ppo_trading")
        self.api_url = api_url or settings.RL_API_URL or "https://api.rl.example.com"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.model_version = "v1.0"
    
    async def predict(self, data: Dict) -> Dict:
        """
        执行RL决策
        
        Args:
            data: {
                "state": Dict,  # 市场环境状态
                "available_actions": List[str],
            }
        
        Returns:
            {
                "action": str,  # buy/sell/hold
                "action_prob": float,
                "position_ratio": float,
                "value_estimate": float,
            }
        """
        try:
            response = await self.client.post(
                f"{self.api_url}/predict",
                json={
                    **data,
                    "model_version": self.model_version,
                },
                headers={"Authorization": f"Bearer {settings.RL_API_KEY}"},
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"RL decision: action={result.get('action')} "
                       f"ratio={result.get('position_ratio', 0):.2%}")
            
            return result
        
        except Exception as e:
            logger.error(f"RL prediction failed: {e}")
            return self._fallback_decision(data)
    
    def _fallback_decision(self, data: Dict) -> Dict:
        """Fallback决策"""
        state = data.get("state", {})
        trend = state.get("trend", 0)
        
        if trend > 0.02:
            action = "buy"
            ratio = 0.05
        elif trend < -0.02:
            action = "sell"
            ratio = 0.05
        else:
            action = "hold"
            ratio = 0.0
        
        return {
            "action": action,
            "action_prob": 0.5,
            "position_ratio": ratio,
            "value_estimate": 0.0,
            "source": "fallback_rule",
        }


class LLMTradingAnalyzer:
    """
    LLM交易分析器
    
    使用GPT-4.1或DeepSeek进行策略分析
    """
    
    def __init__(self):
        self.openai_client = None
        self.deepseek_client = None
        self._init_clients()
    
    def _init_clients(self):
        """初始化API客户端"""
        if settings.OPENAI_API_KEY:
            self.openai_client = httpx.AsyncClient(
                base_url=settings.OPENAI_BASE_URL,
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                timeout=60.0,
            )
        
        if settings.DEEPSEEK_API_KEY:
            self.deepseek_client = httpx.AsyncClient(
                base_url=settings.DEEPSEEK_BASE_URL,
                headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
                timeout=60.0,
            )
    
    async def analyze_trading_opportunity(
        self,
        symbol: str,
        market_data: Dict,
        predictions: Dict,
        factors: Dict,
    ) -> Dict:
        """
        分析交易机会
        
        Returns:
            {
                "recommendation": str,
                "confidence": float,
                "reasoning": str,
                "risk_factors": List[str],
                "key_levels": Dict,
            }
        """
        prompt = self._build_analysis_prompt(symbol, market_data, predictions, factors)
        
        # 优先使用OpenAI
        if self.openai_client:
            return await self._call_openai(prompt)
        
        # 备选DeepSeek
        if self.deepseek_client:
            return await self._call_deepseek(prompt)
        
        # Fallback
        return self._fallback_analysis(symbol, factors)
    
    def _build_analysis_prompt(
        self,
        symbol: str,
        market_data: Dict,
        predictions: Dict,
        factors: Dict,
    ) -> str:
        """构建分析prompt"""
        prompt = f"""你是一位专业的量化交易分析师。请分析以下交易机会：

## 交易标的
- 代码: {symbol}
- 当前价格: {market_data.get('current_price', 'N/A')}

## 预测结果
"""
        for tf, pred in predictions.items():
            prompt += f"- {tf}: 方向={pred.get('direction', 'unknown')}, 置信度={pred.get('confidence', 0):.1%}\n"
        
        prompt += f"\n## 关键因子\n"
        key_factors = ["mom_5m", "mom_15m", "rsi", "macd", "volatility_5m"]
        for f in key_factors:
            if f in factors:
                prompt += f"- {f}: {factors[f]:.3f}\n"
        
        prompt += """
## 请提供
1. 交易建议（买入/卖出/观望）
2. 置信度评分（0-100%）
3. 详细推理（基于技术和基本面）
4. 关键风险因素
5. 关键价格位（支撑/阻力）

请以JSON格式输出。
"""
        return prompt
    
    async def _call_openai(self, prompt: str) -> Dict:
        """调用OpenAI API"""
        try:
            response = await self.openai_client.post(
                "/chat/completions",
                json={
                    "model": "gpt-4.1",
                    "messages": [
                        {"role": "system", "content": "你是专业量化交易分析师，只输出JSON格式结果。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            result = response.json()
            
            content = result["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            
            logger.info(f"OpenAI analysis: {parsed.get('recommendation', 'N/A')}")
            return parsed
        
        except Exception as e:
            logger.error(f"OpenAI API failed: {e}")
            return self._fallback_analysis("", {})
    
    async def _call_deepseek(self, prompt: str) -> Dict:
        """调用DeepSeek API"""
        try:
            response = await self.deepseek_client.post(
                "/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是专业量化交易分析师。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            result = response.json()
            
            content = result["choices"][0]["message"]["content"]
            
            # 尝试解析JSON
            try:
                parsed = json.loads(content)
            except:
                parsed = {"reasoning": content}
            
            logger.info(f"DeepSeek analysis: {parsed.get('recommendation', 'N/A')}")
            return parsed
        
        except Exception as e:
            logger.error(f"DeepSeek API failed: {e}")
            return self._fallback_analysis("", {})
    
    def _fallback_analysis(self, symbol: str, factors: Dict) -> Dict:
        """Fallback分析"""
        return {
            "recommendation": "hold",
            "confidence": 0.3,
            "reasoning": "API不可用，使用保守策略",
            "risk_factors": ["模型API故障"],
            "key_levels": {},
            "source": "fallback",
        }


# === 模型工厂 ===

class ModelFactory:
    """AI模型工厂"""
    
    _instances = {}
    
    @classmethod
    def get_informer(cls) -> InformerModel:
        """获取Informer模型实例"""
        if "informer" not in cls._instances:
            cls._instances["informer"] = InformerModel()
        return cls._instances["informer"]
    
    @classmethod
    def get_nhits(cls) -> NHITSModel:
        """获取N-HiTS模型实例"""
        if "n-hits" not in cls._instances:
            cls._instances["n-hits"] = NHITSModel()
        return cls._instances["n-hits"]
    
    @classmethod
    def get_rl_model(cls) -> RLTradingModel:
        """获取RL模型实例"""
        if "rl" not in cls._instances:
            cls._instances["rl"] = RLTradingModel()
        return cls._instances["rl"]
    
    @classmethod
    def get_llm_analyzer(cls) -> LLMTradingAnalyzer:
        """获取LLM分析器实例"""
        if "llm" not in cls._instances:
            cls._instances["llm"] = LLMTradingAnalyzer()
        return cls._instances["llm"]
