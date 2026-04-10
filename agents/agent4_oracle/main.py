"""
Agent 4: TrendOracle (决策层) - v3.0 Dual-Track AI Decision
双轨AI决策系统：
- Track A (80%): 时间序列预测 (Informer/Autoformer + N-HiTS)
- Track B (20%): 大模型推理 (Qwen2.5 + Kimi)
- NLP情绪分析: FinBERT (并行输入)

输入: Kafka am-hk-trading-opportunities (Agent3输出)
输出: Kafka am-hk-trading-decisions
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np

from core.config import settings
from core.kafka import MessageBus, AgentConsumer
from core.models import MarketType, ActionType
from core.utils import generate_msg_id, generate_timestamp, setup_logging, CircuitBreaker

logger = setup_logging("agent4_oracle")


class DecisionAction(str, Enum):
    """决策动作"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    PASS = "PASS"


@dataclass
class TrackAPrediction:
    """Track A: 时间序列预测结果"""
    direction: str
    predicted_return: float
    confidence: float
    timeframes: Dict[str, Dict] = field(default_factory=dict)
    informer_score: float = 0.0
    nhits_score: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "direction": self.direction,
            "predicted_return": round(self.predicted_return, 4),
            "confidence": round(self.confidence, 4),
            "timeframes": self.timeframes,
            "informer_score": round(self.informer_score, 4),
            "nhits_score": round(self.nhits_score, 4),
        }


@dataclass
class TrackBAnalysis:
    """Track B: 大模型分析结果"""
    recommendation: str
    confidence: float
    reasoning: str
    key_factors: List[str] = field(default_factory=list)
    risk_assessment: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "recommendation": self.recommendation,
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "key_factors": self.key_factors,
            "risk_assessment": self.risk_assessment,
        }


@dataclass
class SentimentAnalysis:
    """情绪分析结果"""
    score: float
    confidence: float
    sources: List[str] = field(default_factory=list)
    summary: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "sources": self.sources,
            "summary": self.summary,
        }


@dataclass
class TradingDecision:
    """交易决策输出"""
    action: DecisionAction
    confidence: float
    entry: Dict[str, Any]
    tp: float
    sl: float
    position_size: float
    reasoning: str
    track_a_score: float
    track_b_score: float
    sentiment_score: float
    risk_score: float = 0.5  # 添加风险评分字段
    
    def to_dict(self) -> Dict:
        return {
            "action": self.action.value,
            "confidence": round(self.confidence, 4),
            "entry": self.entry,
            "tp": round(self.tp, 2),
            "sl": round(self.sl, 2),
            "position_size": round(self.position_size, 4),
            "reasoning": self.reasoning,
            "track_a_score": round(self.track_a_score, 4),
            "track_b_score": round(self.track_b_score, 4),
            "sentiment_score": round(self.sentiment_score, 4),
            "risk_score": round(self.risk_score, 4),  # 添加到输出
        }


class InformerAutoformerClient:
    """Informer/Autoformer API客户端"""
    
    def __init__(self):
        self.api_url = settings.INFORMER_API_URL or ""
        self.api_key = settings.INFORMER_API_KEY or ""
        self.client = httpx.AsyncClient(timeout=30.0)
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
    async def predict(self, symbol: str, prices: List[float], 
                     factors: Dict[str, float],
                     prediction_horizon: int = 5) -> Dict:
        """执行时间序列预测"""
        if not self.api_url or len(prices) < 60:
            return self._fallback_predict(prices, prediction_horizon)
        
        try:
            payload = {
                "symbol": symbol,
                "prices": prices,
                "factors": factors,
                "prediction_length": prediction_horizon,
                "model": "informer",
            }
            
            response = await self.client.post(
                f"{self.api_url}/predict",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            result = response.json()
            
            predictions = result.get("predictions", [])
            current_price = prices[-1] if prices else 0
            
            if predictions and current_price > 0:
                avg_pred = sum(predictions) / len(predictions)
                predicted_return = (avg_pred - current_price) / current_price
                direction = "up" if predicted_return > 0.005 else "down" if predicted_return < -0.005 else "sideways"
            else:
                predicted_return = 0
                direction = "sideways"
            
            return {
                "predictions": predictions,
                "confidence": result.get("confidence", 0.7),
                "direction": direction,
                "predicted_return": predicted_return,
                "source": "informer_api",
            }
            
        except Exception as e:
            logger.error(f"Informer API error: {e}")
            return self._fallback_predict(prices, prediction_horizon)
    
    def _fallback_predict(self, prices: List[float], horizon: int) -> Dict:
        """Fallback预测"""
        if len(prices) < 10:
            return {
                "predictions": [prices[-1]] * horizon if prices else [0] * horizon,
                "confidence": 0.3,
                "direction": "sideways",
                "predicted_return": 0.0,
                "source": "fallback_ma",
            }
        
        returns = np.diff(prices) / prices[:-1]
        recent_return = np.mean(returns[-5:]) if len(returns) >= 5 else 0
        
        last_price = prices[-1]
        predictions = []
        for i in range(horizon):
            trend_component = recent_return * (i + 1) * 0.5
            predictions.append(last_price * (1 + trend_component))
        
        avg_pred = sum(predictions) / len(predictions)
        predicted_return = (avg_pred - last_price) / last_price
        direction = "up" if predicted_return > 0.005 else "down" if predicted_return < -0.005 else "sideways"
        confidence = min(0.7, 0.4 + abs(predicted_return) * 10)
        
        return {
            "predictions": predictions,
            "confidence": confidence,
            "direction": direction,
            "predicted_return": predicted_return,
            "source": "fallback_rule",
        }


class NHITSClient:
    """N-HiTS模型客户端"""
    
    def __init__(self):
        self.api_url = settings.NHITS_API_URL or ""
        self.api_key = settings.NHITS_API_KEY or ""
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def predict(self, symbol: str, prices: List[float], 
                     prediction_horizon: int = 5) -> Dict:
        """N-HiTS趋势分解预测"""
        if not self.api_url or len(prices) < 30:
            return self._fallback_decompose(prices, prediction_horizon)
        
        try:
            response = await self.client.post(
                f"{self.api_url}/decompose",
                json={
                    "symbol": symbol,
                    "prices": prices,
                    "prediction_length": prediction_horizon,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            result = response.json()
            
            trend = result.get("trend", [])
            if len(trend) >= 2 and trend[0] != 0:
                trend_strength = (trend[-1] - trend[0]) / abs(trend[0])
            else:
                trend_strength = 0
            
            return {
                "trend": trend,
                "seasonal": result.get("seasonal", []),
                "forecast": result.get("forecast", []),
                "trend_strength": trend_strength,
                "source": "nhits_api",
            }
            
        except Exception as e:
            logger.error(f"N-HiTS API error: {e}")
            return self._fallback_decompose(prices, prediction_horizon)
    
    def _fallback_decompose(self, prices: List[float], horizon: int) -> Dict:
        """Fallback分解"""
        if len(prices) < 2:
            return {
                "trend": [prices[-1]] * horizon if prices else [0] * horizon,
                "seasonal": [0] * horizon,
                "forecast": [prices[-1]] * horizon if prices else [0] * horizon,
                "trend_strength": 0,
                "source": "fallback",
            }
        
        x = np.arange(len(prices))
        y = np.array(prices)
        slope = np.polyfit(x, y, 1)[0] if len(prices) > 1 else 0
        trend = [prices[-1] + slope * i for i in range(horizon)]
        
        return {
            "trend": trend,
            "seasonal": [0] * horizon,
            "forecast": trend,
            "trend_strength": slope / prices[-1] if prices[-1] != 0 else 0,
            "source": "fallback_linear",
        }


class QwenClient:
    """Qwen2.5大模型客户端"""
    
    def __init__(self):
        self.api_url = settings.QWEN_API_URL or "https://api.openai.com/v1"
        self.api_key = settings.QWEN_API_KEY or settings.OPENAI_API_KEY or ""
        self.model = "qwen2.5-72b-instruct"
        self.client = httpx.AsyncClient(timeout=60.0)
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    
    async def analyze(self, symbol: str, market_data: Dict, 
                     predictions: Dict, factors: Dict,
                     sentiment: Dict) -> TrackBAnalysis:
        """Qwen分析交易机会"""
        if not self.api_key:
            return self._fallback_analysis()
        
        try:
            prompt = self._build_prompt(symbol, market_data, predictions, factors, sentiment)
            
            response = await self.client.post(
                f"{self.api_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self._system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 800,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            result = response.json()
            
            content = result["choices"][0]["message"]["content"]
            return self._parse_analysis(content)
            
        except Exception as e:
            logger.error(f"Qwen API error: {e}")
            return self._fallback_analysis()
    
    def _system_prompt(self) -> str:
        return """你是一位专业的量化交易分析师，基于市场数据和技术指标做出交易决策。
请分析以下信息，输出JSON格式的交易建议：
{
    "recommendation": "buy/sell/hold",
    "confidence": 0.0-1.0,
    "reasoning": "详细分析理由",
    "key_factors": ["因子1", "因子2"],
    "risk_assessment": "风险评估"
}"""
    
    def _build_prompt(self, symbol: str, market_data: Dict, 
                     predictions: Dict, factors: Dict, sentiment: Dict) -> str:
        current_price = market_data.get("price", "N/A")
        
        prompt = f"""## 交易分析任务

标的: {symbol}
当前价格: {current_price}

### 时间序列预测 (Track A)
- 预测方向: {predictions.get('direction', 'unknown')}
- 预测收益率: {predictions.get('predicted_return', 0):.2%}
- 置信度: {predictions.get('confidence', 0):.2%}

### 关键技术指标
"""
        key_factors = ["price_momentum_5m", "price_momentum_15m", "rsi_14", 
                      "macd", "volatility_5m", "orderbook_imbalance"]
        for f in key_factors:
            if f in factors:
                prompt += f"- {f}: {factors[f]:.4f}\n"
        
        prompt += f"""
### 市场情绪
- 情绪分数: {sentiment.get('score', 0):.2f} (-1到1)
- 情绪来源: {', '.join(sentiment.get('sources', []))}

请基于以上信息，给出交易建议。
"""
        return prompt
    
    def _parse_analysis(self, content: str) -> TrackBAnalysis:
        """解析Qwen输出"""
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                data = json.loads(json_str)
            else:
                data = json.loads(content)
            
            return TrackBAnalysis(
                recommendation=data.get("recommendation", "hold"),
                confidence=data.get("confidence", 0.5),
                reasoning=data.get("reasoning", ""),
                key_factors=data.get("key_factors", []),
                risk_assessment=data.get("risk_assessment", ""),
            )
        except Exception as e:
            logger.warning(f"Failed to parse Qwen response: {e}")
            return TrackBAnalysis(
                recommendation="hold",
                confidence=0.5,
                reasoning=content[:200] if content else "解析失败",
                key_factors=[],
                risk_assessment="",
            )
    
    def _fallback_analysis(self) -> TrackBAnalysis:
        return TrackBAnalysis(
            recommendation="hold",
            confidence=0.3,
            reasoning="Qwen API不可用，使用保守策略",
            key_factors=["api_unavailable"],
            risk_assessment="高",
        )


class KimiClient:
    """Kimi大模型客户端 (Qwen备选)"""
    
    def __init__(self):
        self.api_url = settings.KIMI_API_URL or "https://api.moonshot.cn/v1"
        self.api_key = settings.KIMI_API_KEY or ""
        self.model = "kimi-k2.5"
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def analyze(self, symbol: str, market_data: Dict, 
                     predictions: Dict, factors: Dict,
                     sentiment: Dict) -> TrackBAnalysis:
        """Kimi分析交易机会"""
        if not self.api_key:
            return self._fallback_analysis()
        
        try:
            prompt = self._build_prompt(symbol, market_data, predictions, factors, sentiment)
            
            response = await self.client.post(
                f"{self.api_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "你是专业量化交易分析师，只输出JSON格式。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            result = response.json()
            
            content = result["choices"][0]["message"]["content"]
            return self._parse_analysis(content)
            
        except Exception as e:
            logger.error(f"Kimi API error: {e}")
            return self._fallback_analysis()
    
    def _build_prompt(self, symbol: str, market_data: Dict, 
                     predictions: Dict, factors: Dict, sentiment: Dict) -> str:
        current_price = market_data.get("price", "N/A")
        return f"""分析{symbol}交易机会，当前价格{current_price}。
预测方向: {predictions.get('direction', 'unknown')}, 
预测收益: {predictions.get('predicted_return', 0):.2%}
情绪分数: {sentiment.get('score', 0):.2f}
输出JSON: {{recommendation, confidence, reasoning, key_factors, risk_assessment}}"""
    
    def _parse_analysis(self, content: str) -> TrackBAnalysis:
        """解析Kimi输出"""
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(content[json_start:json_end])
                return TrackBAnalysis(
                    recommendation=data.get("recommendation", "hold"),
                    confidence=data.get("confidence", 0.5),
                    reasoning=data.get("reasoning", ""),
                    key_factors=data.get("key_factors", []),
                    risk_assessment=data.get("risk_assessment", ""),
                )
        except:
            pass
        return self._fallback_analysis()
    
    def _fallback_analysis(self) -> TrackBAnalysis:
        return TrackBAnalysis(
            recommendation="hold",
            confidence=0.3,
            reasoning="Kimi API不可用",
            key_factors=[],
            risk_assessment="高",
        )


class FinBERTClient:
    """FinBERT情绪分析客户端"""
    
    def __init__(self):
        self.api_url = settings.FINBERT_API_URL or ""
        self.api_key = settings.FINBERT_API_KEY or ""
        self.client = httpx.AsyncClient(timeout=30.0)
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = 300
    
    async def analyze(self, symbol: str, texts: Optional[List[str]] = None) -> SentimentAnalysis:
        """分析市场情绪"""
        cache_key = f"{symbol}_{int(datetime.now().timestamp()) // self.cache_ttl}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            return SentimentAnalysis(**cached)
        
        if not self.api_url:
            return self._fallback_sentiment(symbol)
        
        try:
            response = await self.client.post(
                f"{self.api_url}/analyze",
                json={
                    "symbol": symbol,
                    "texts": texts or [],
                    "sources": ["twitter", "news"],
                    "time_range": "1h",
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            result = response.json()
            
            sentiment = SentimentAnalysis(
                score=result.get("sentiment_score", 0),
                confidence=result.get("confidence", 0.5),
                sources=result.get("sources", ["twitter", "news"]),
                summary=result.get("summary", ""),
            )
            
            self.cache[cache_key] = sentiment.to_dict()
            return sentiment
            
        except Exception as e:
            logger.error(f"FinBERT API error: {e}")
            return self._fallback_sentiment(symbol)
    
    def _fallback_sentiment(self, symbol: str) -> SentimentAnalysis:
        return SentimentAnalysis(
            score=0.0,
            confidence=0.3,
            sources=["fallback"],
            summary="FinBERT API不可用，使用中性估计",
        )


class RiskCalculator:
    """风险计算模块"""
    
    def __init__(self):
        self.max_position = 0.15
        self.min_risk_reward = 2.0
    
    def calculate_tp_sl(self, entry_price: float, action: DecisionAction,
                       volatility: float, atr: Optional[float] = None) -> Tuple[float, float]:
        """计算止盈止损价格"""
        base_sl = atr * 1.5 if atr else entry_price * volatility * 2
        sl_pct = max(0.015, min(0.03, base_sl / entry_price if entry_price > 0 else 0.02))
        tp_pct = sl_pct * self.min_risk_reward
        
        if action == DecisionAction.BUY:
            sl_price = entry_price * (1 - sl_pct)
            tp_price = entry_price * (1 + tp_pct)
        elif action == DecisionAction.SELL:
            sl_price = entry_price * (1 + sl_pct)
            tp_price = entry_price * (1 - tp_pct)
        else:
            tp_price = entry_price
            sl_price = entry_price
        
        return round(tp_price, 2), round(sl_price, 2)
    
    def calculate_position_size(self, confidence: float, 
                               account_equity: float = 100000,
                               risk_per_trade: float = 0.02) -> float:
        """计算建议仓位大小 - Kelly公式"""
        p = confidence
        b = 2.0
        q = 1 - p
        
        kelly = (p * b - q) / b if b > 0 else 0
        position = min(kelly * 0.5, self.max_position)
        
        if confidence < 0.6:
            position *= 0.5
        elif confidence > 0.85:
            position = min(position * 1.2, self.max_position)
        
        return max(0, min(position, self.max_position))


class TrendOracle:
    """Agent 4: TrendOracle - 双轨AI决策层"""
    
    def __init__(self):
        self.agent_name = "agent4_oracle"
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-trading-opportunities"]
        )
        
        # Track A: 时间序列模型
        self.informer = InformerAutoformerClient()
        self.nhits = NHITSClient()
        
        # Track B: 大模型
        self.qwen = QwenClient()
        self.kimi = KimiClient()
        
        # 情绪分析
        self.finbert = FinBERTClient()
        
        # 风险计算
        self.risk_calc = RiskCalculator()
        
        # 权重配置
        self.track_a_weight = 0.8
        self.track_b_weight = 0.2
        
        # 价格缓存
        self.price_cache: Dict[str, List[float]] = {}
        self.max_cache_size = 200
        
        # 统计
        self.decision_count = 0
        self.running = False
        
        logger.info(f"{self.agent_name} initialized")
        logger.info(f"Weights: TrackA={self.track_a_weight}, TrackB={self.track_b_weight}")
    
    async def start(self):
        """启动决策层"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        logger.info(f"DEBUG: Registering handler for opportunity messages")
        
        self.consumer.register_handler("opportunity", self._on_opportunity)
        logger.info(f"DEBUG: Handler registered. Topics: {self.consumer.topics}")
        
        self.bus.publish_status({
            "state": "running",
            "track_a_weight": self.track_a_weight,
            "track_b_weight": self.track_b_weight,
            "models": {
                "informer": True,
                "nhits": True,
                "qwen": bool(settings.QWEN_API_KEY or settings.OPENAI_API_KEY),
                "kimi": bool(settings.KIMI_API_KEY),
                "finbert": bool(settings.FINBERT_API_URL),
            }
        })
        
        try:
            logger.info(f"DEBUG: Starting consumer...")
            # 在后台线程运行消费者
            import threading
            consumer_thread = threading.Thread(target=self.consumer.start)
            consumer_thread.daemon = True
            consumer_thread.start()
            logger.info(f"DEBUG: Consumer started in background thread")
            
            # 保持主循环运行
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
        finally:
            await self.stop()
    
    async def stop(self):
        """停止决策层"""
        logger.info(f"{self.agent_name} stopping...")
        self.running = False
        self.consumer.stop()
        
        self.bus.publish_status({
            "state": "stopped",
            "decision_count": self.decision_count,
        })
        self.bus.flush()
        self.bus.close()
        
        logger.info(f"{self.agent_name} stopped")
    
    def _on_opportunity(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理交易机会 - 在后台线程中运行异步处理"""
        logger.info(f"DEBUG: Received opportunity message for key={key}")
        
        # 在后台线程中创建新的事件循环来运行异步任务
        def run_async_in_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._process_opportunity_async(key, value, headers))
                loop.close()
            except Exception as e:
                logger.error(f"DEBUG: Error in thread processing: {e}", exc_info=True)
        
        import threading
        thread = threading.Thread(target=run_async_in_thread)
        thread.daemon = True
        thread.start()
        logger.info(f"DEBUG: Started processing thread for {key}")
    
    async def _process_opportunity_async(self, key: str, value: Dict, headers: Optional[Dict]):
        """异步处理交易机会"""
        try:
            payload = value.get("payload", value)
            
            symbol = payload.get("symbol", key)
            market = payload.get("market", "unknown")
            factors = payload.get("factors", {})
            
            logger.info(f"📊 Processing opportunity: {symbol} ({market})")
            
            # 更新价格缓存
            await self._update_price_cache(symbol, factors)
            prices = self.price_cache.get(symbol, [])
            
            # Track A + 情绪分析 (并行)
            track_a_task = self._run_track_a(symbol, prices, factors)
            sentiment_task = self.finbert.analyze(symbol)
            
            track_a_result, sentiment = await asyncio.gather(track_a_task, sentiment_task)
            
            # Track B: 大模型推理
            market_data = {"price": prices[-1] if prices else 0, "symbol": symbol}
            track_b_result = await self._run_track_b(symbol, market_data, track_a_result.to_dict(), factors, sentiment.to_dict())
            
            # 双轨融合决策
            decision = self._fuse_decision(symbol, track_a_result, track_b_result, sentiment, factors, prices)
            
            # 发布决策
            self._publish_decision(decision, symbol, track_a_result, track_b_result, sentiment)
            
            self.decision_count += 1
            
            logger.info(f"✅ Decision: {symbol} | action={decision.action.value} | "
                       f"confidence={decision.confidence:.2%} | "
                       f"position={decision.position_size:.2%}")
            
        except Exception as e:
            logger.error(f"❌ Error processing opportunity: {e}", exc_info=True)
    
    async def _update_price_cache(self, symbol: str, factors: Dict):
        """更新价格缓存"""
        price = factors.get("close") or factors.get("price") or factors.get("ma_5")
        if price is None:
            return
        
        if symbol not in self.price_cache:
            self.price_cache[symbol] = []
        
        self.price_cache[symbol].append(float(price))
        
        if len(self.price_cache[symbol]) > self.max_cache_size:
            self.price_cache[symbol] = self.price_cache[symbol][-self.max_cache_size:]
    
    async def _run_track_a(self, symbol: str, prices: List[float], 
                          factors: Dict) -> TrackAPrediction:
        """Track A: 时间序列预测"""
        prediction_horizon = 5
        
        informer_task = self.informer.predict(symbol, prices, factors, prediction_horizon)
        nhits_task = self.nhits.predict(symbol, prices, prediction_horizon)
        
        informer_result, nhits_result = await asyncio.gather(informer_task, nhits_task)
        
        informer_weight = 0.7
        nhits_weight = 0.3
        
        informer_conf = informer_result.get("confidence", 0)
        nhits_conf = 0.5
        
        combined_confidence = informer_conf * informer_weight + nhits_conf * nhits_weight
        direction = informer_result.get("direction", "sideways")
        predicted_return = informer_result.get("predicted_return", 0)
        
        nhits_trend = nhits_result.get("trend_strength", 0)
        if abs(nhits_trend) > 0.01:
            predicted_return = predicted_return * 0.8 + nhits_trend * 0.2
        
        return TrackAPrediction(
            direction=direction,
            predicted_return=predicted_return,
            confidence=combined_confidence,
            timeframes={
                "5min": {
                    "direction": direction,
                    "predicted_return": predicted_return,
                    "confidence": combined_confidence,
                }
            },
            informer_score=informer_conf,
            nhits_score=min(abs(nhits_trend) * 10, 1.0),
        )
    
    async def _run_track_b(self, symbol: str, market_data: Dict, 
                          track_a_result: Dict, factors: Dict,
                          sentiment: Dict) -> TrackBAnalysis:
        """Track B: 大模型推理"""
        # 优先使用Qwen，失败时尝试Kimi
        result = await self.qwen.analyze(symbol, market_data, track_a_result, factors, sentiment)
        
        if result.confidence < 0.4 and settings.KIMI_API_KEY:
            logger.info(f"Qwen confidence low, trying Kimi for {symbol}")
            result = await self.kimi.analyze(symbol, market_data, track_a_result, factors, sentiment)
        
        return result
    
    def _fuse_decision(self, symbol: str, track_a: TrackAPrediction, 
                      track_b: TrackBAnalysis, sentiment: SentimentAnalysis,
                      factors: Dict, prices: List[float]) -> TradingDecision:
        """双轨融合决策逻辑 (0.8*TrackA + 0.2*TrackB)"""
        
        # Track A信号转换
        track_a_action = DecisionAction.BUY if track_a.direction == "up" else \
                        DecisionAction.SELL if track_a.direction == "down" else DecisionAction.HOLD
        
        # Track B信号转换
        track_b_rec = track_b.recommendation.lower()
        track_b_action = DecisionAction.BUY if track_b_rec == "buy" else \
                        DecisionAction.SELL if track_b_rec == "sell" else DecisionAction.HOLD
        
        # 情绪调整
        sentiment_boost = sentiment.score * 0.1  # 情绪分数调整
        
        # 加权融合置信度
        track_a_conf = track_a.confidence * (1 + sentiment_boost if track_a.direction == "up" and sentiment.score > 0 else 1)
        track_b_conf = track_b.confidence
        
        fused_confidence = track_a_conf * self.track_a_weight + track_b_conf * self.track_b_weight
        fused_confidence = min(1.0, max(0.0, fused_confidence))
        
        # 动作决策
        # 如果两者一致，采用共同动作
        # 如果不一致，以Track A为主
        if track_a_action == track_b_action:
            final_action = track_a_action
        else:
            final_action = track_a_action
        
        # 低置信度时转为HOLD
        if fused_confidence < 0.5:
            final_action = DecisionAction.HOLD
        
        # 计算止盈止损
        current_price = prices[-1] if prices else 0
        volatility = factors.get("volatility_5m", 0.02) / 100
        atr = factors.get("atr_14")
        
        tp, sl = self.risk_calc.calculate_tp_sl(current_price, final_action, volatility, atr)
        
        # 计算仓位
        position_size = self.risk_calc.calculate_position_size(fused_confidence)
        
        # 构建reasoning
        reasoning = f"Informer预测{track_a.direction}+{track_a.predicted_return:.2%}, "
        reasoning += f"Qwen建议{track_b.recommendation}, "
        reasoning += f"情绪{sentiment.score:+.2f}"
        
        return TradingDecision(
            action=final_action,
            confidence=fused_confidence,
            entry={"price": current_price, "time": int(datetime.now().timestamp() * 1000)},
            tp=tp,
            sl=sl,
            position_size=position_size,
            reasoning=reasoning,
            track_a_score=track_a.confidence,
            track_b_score=track_b.confidence,
            sentiment_score=sentiment.score,
            risk_score=0.5,  # 添加风险评分
        )
    
    def _publish_decision(self, decision: TradingDecision, symbol: str, 
                          track_a: TrackAPrediction, track_b: TrackBAnalysis, 
                          sentiment: SentimentAnalysis):
        """发布交易决策到Kafka - 兼容 core.models.TradeDecision 格式"""
        
        # 构建符合 core.models.Signal 格式的 signal (注意：action小写，添加所有必需字段)
        decision_dict = {
            "signal": {
                "symbol": symbol,
                "market": "CRYPTO",  # 添加市场类型
                "action": decision.action.value.lower(),  # 转为小写: hold/buy/sell/pass
                "confidence": decision.confidence,
                "predicted_return": track_a.predicted_return,  # 添加预测收益
                "timeframe": "5min",  # 添加时间框架
                "reasoning": decision.reasoning,  # 添加推理
                "agent_id": "agent4_oracle",  # 添加agent_id
                "timestamp": generate_timestamp().isoformat(),
            },
            "position_size": decision.position_size,
            "stop_loss": decision.sl,
            "take_profit": decision.tp,
            "risk_score": decision.risk_score,
            "approved": False,
            "approval_reason": "",
        }
        
        message = {
            "msg_id": generate_msg_id(),
            "msg_type": "trading_decision",
            "source_agent": self.agent_name,
            "target_agent": "agent5_guardian",
            "timestamp": generate_timestamp().isoformat(),
            "priority": 2,
            "payload": {
                "symbol": symbol,
                "decision": decision_dict,
                "factors": {
                    "track_a_confidence": track_a.confidence,
                    "track_b_confidence": track_b.confidence,
                    "sentiment_score": sentiment.score,
                },
            },
        }
        
        self.bus.send(
            topic="am-hk-trading-decisions",
            key=symbol,
            value=message
        )
        self.bus.flush()


if __name__ == "__main__":
    oracle = TrendOracle()
    asyncio.run(oracle.start())
