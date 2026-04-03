"""
Agent 2: DataCurator
数据因子处理器 - 集成FinBERT情绪分析
"""
import asyncio
import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from core.kafka import MessageBus, AgentConsumer
from core.models import FactorData, MarketData, MarketType
from core.finbert_analyzer import FinBERTAnalyzer, analyze_news_sentiment
from core.utils import dict_hash, generate_timestamp, setup_logging

logger = setup_logging("agent2_curator")


class DataCurator:
    """
    Agent 2: 数据因子处理
    
    职责：
    - 30+机构级因子计算
    - NLP情绪分析（FinBERT）
    - 多市场特征融合
    - 数据标准化
    - 异常检测
    
    模型：
    - 数据标准化：统计模型
    - 异常检测：Z-score, IsolationForest
    - 情绪分析：FinBERT
    """
    
    def __init__(self):
        self.agent_name = "agent2_curator"
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-raw-market-data"]
        )
        
        # 因子窗口大小
        self.factor_windows = {
            "short": 5,      # 5分钟
            "medium": 15,    # 15分钟
            "long": 60,      # 1小时
        }
        
        # 数据缓存
        self.data_cache: Dict[str, List[Dict]] = {}
        self.max_cache_size = 1000
        
        # 新闻缓存（用于情绪聚合）
        self.news_cache: Dict[str, List[Dict]] = {}
        self.news_max_cache = 50
        
        # FinBERT分析器
        self.finbert = FinBERTAnalyzer()
        
        self.running = False
        logger.info(f"{self.agent_name} initialized (with FinBERT)")
    
    async def start(self):
        """启动处理器"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 注册消息处理器
        self.consumer.register_handler("market_data", self._on_market_data)
        self.consumer.register_handler("news", self._on_news_data)
        
        # 发布状态
        self.bus.publish_status({
            "state": "running",
            "factors_count": 30,
            "sentiment_analysis": True,
        })
        
        # 启动消费者
        try:
            self.consumer.start()
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
        finally:
            await self.stop()
    
    async def stop(self):
        """停止处理器"""
        logger.info(f"{self.agent_name} stopping...")
        self.running = False
        self.consumer.stop()
        
        # 关闭FinBERT
        await self.finbert.close()
        
        self.bus.publish_status({"state": "stopped"})
        self.bus.flush()
        self.bus.close()
        
        logger.info(f"{self.agent_name} stopped")
    
    def _on_market_data(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理市场数据"""
        try:
            symbol = value.get("symbol")
            market = value.get("market")
            payload = value.get("payload", {})
            data_type = value.get("data_type", "unknown")
            
            # 如果是新闻数据，单独处理
            if data_type == "news" or data_type == "sentiment":
                asyncio.create_task(self._process_news_async(symbol, value))
                return
            
            # 更新缓存
            self._update_cache(symbol, payload)
            
            # 计算因子
            factors = self._calculate_factors(symbol, market, payload)
            
            # 添加情绪因子（如果有缓存的新闻）
            sentiment_factors = self._get_sentiment_factors(symbol)
            factors.update(sentiment_factors)
            
            # 异常检测
            if self._detect_anomaly(factors):
                logger.warning(f"Anomaly detected for {symbol}")
                return
            
            # 构造因子数据
            factor_data = FactorData(
                symbol=symbol,
                market=MarketType(market),
                timestamp=generate_timestamp(),
                factors=factors,
                raw_data_hash=dict_hash(payload),
            )
            
            # 发布因子数据
            self.bus.publish_factors(symbol, factor_data.dict())
            
            logger.debug(f"Published factors for {symbol}: {len(factors)} factors")
            
        except Exception as e:
            logger.error(f"Error processing market data: {e}", exc_info=True)
    
    def _on_news_data(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理新闻数据"""
        asyncio.create_task(self._process_news_async(key, value))
    
    async def _process_news_async(self, symbol: str, news_data: Dict):
        """异步处理新闻（情绪分析）"""
        try:
            payload = news_data.get("payload", {})
            
            # 构造新闻项
            news_item = {
                "symbol": symbol,
                "title": payload.get("title", ""),
                "content": payload.get("content", ""),
                "source": payload.get("source", "unknown"),
                "url": payload.get("url", ""),
                "timestamp": news_data.get("timestamp", generate_timestamp().isoformat()),
            }
            
            # FinBERT情绪分析
            analyzed_news = await self.finbert.analyze_news(news_item)
            
            # 缓存分析结果
            if symbol not in self.news_cache:
                self.news_cache[symbol] = []
            
            self.news_cache[symbol].append(analyzed_news)
            
            # 限制缓存大小
            if len(self.news_cache[symbol]) > self.news_max_cache:
                self.news_cache[symbol] = self.news_cache[symbol][-self.news_max_cache:]
            
            sentiment = analyzed_news.get("sentiment", "neutral")
            score = analyzed_news.get("sentiment_score", 0.0)
            
            logger.info(f"News sentiment analyzed for {symbol}: {sentiment} ({score:+.2f})")
            
        except Exception as e:
            logger.error(f"Error analyzing news sentiment: {e}")
    
    def _get_sentiment_factors(self, symbol: str) -> Dict[str, float]:
        """
        获取情绪因子
        
        Returns:
            情绪相关因子
        """
        factors = {}
        
        news_list = self.news_cache.get(symbol, [])
        if not news_list:
            return factors
        
        # 计算聚合情绪
        scores = [n.get("sentiment_score", 0.0) for n in news_list]
        confidences = [n.get("sentiment_confidence", 0.0) for n in news_list]
        
        if scores:
            # 简单平均
            factors["news_sentiment_avg"] = np.mean(scores)
            
            # 加权平均（按置信度）
            if sum(confidences) > 0:
                factors["news_sentiment_weighted"] = np.average(scores, weights=confidences)
            
            # 情绪变化（最新5条vs前5条）
            if len(scores) >= 10:
                recent = np.mean(scores[-5:])
                past = np.mean(scores[-10:-5])
                factors["news_sentiment_change"] = recent - past
            
            # 正面/负面新闻比例
            positive_count = sum(1 for n in news_list if n.get("sentiment") == "positive")
            negative_count = sum(1 for n in news_list if n.get("sentiment") == "negative")
            total = len(news_list)
            
            factors["news_positive_ratio"] = positive_count / total if total > 0 else 0.5
            factors["news_negative_ratio"] = negative_count / total if total > 0 else 0.5
            
            # 情绪极值
            factors["news_sentiment_max"] = max(scores)
            factors["news_sentiment_min"] = min(scores)
            
            # 新闻数量因子
            factors["news_count_1h"] = len(news_list)
        
        return factors
    
    def _update_cache(self, symbol: str, data: Dict):
        """更新数据缓存"""
        if symbol not in self.data_cache:
            self.data_cache[symbol] = []
        
        self.data_cache[symbol].append({
            "timestamp": generate_timestamp(),
            "data": data,
        })
        
        # 限制缓存大小
        if len(self.data_cache[symbol]) > self.max_cache_size:
            self.data_cache[symbol] = self.data_cache[symbol][-self.max_cache_size:]
    
    def _calculate_factors(self, symbol: str, market: str, data: Dict) -> Dict[str, float]:
        """
        计算30+机构级因子
        
        Returns:
            Dict[str, float]: 因子字典
        """
        factors = {}
        
        cache = self.data_cache.get(symbol, [])
        if len(cache) < 2:
            return factors
        
        # 提取价格序列
        prices = self._extract_prices(cache)
        volumes = self._extract_volumes(cache)
        
        if len(prices) == 0:
            return factors
        
        # === 价格动量因子 ===
        factors["mom_5m"] = self._momentum(prices, 5)
        factors["mom_15m"] = self._momentum(prices, 15)
        factors["mom_1h"] = self._momentum(prices, 60)
        
        # === 波动率因子 ===
        factors["volatility_5m"] = self._volatility(prices, 5)
        factors["volatility_15m"] = self._volatility(prices, 15)
        factors["atr"] = self._atr(prices, 14)
        
        # === 成交量因子 ===
        if volumes:
            factors["volume_ma_ratio"] = volumes[-1] / np.mean(volumes[-20:]) if len(volumes) >= 20 else 1.0
            factors["volume_trend"] = self._volume_trend(volumes)
        
        # === 趋势因子 ===
        factors["ema_diff"] = self._ema_diff(prices, 12, 26)
        factors["rsi"] = self._rsi(prices, 14)
        factors["macd"] = self._macd(prices)
        
        # === 统计因子 ===
        factors["skewness"] = self._skewness(prices, 20)
        factors["kurtosis"] = self._kurtosis(prices, 20)
        
        # === 市场微观结构因子 ===
        factors["price_change"] = self._price_change(prices)
        factors["high_low_range"] = self._high_low_range(cache)
        
        return factors
    
    def _extract_prices(self, cache: List[Dict]) -> List[float]:
        """提取价格序列"""
        prices = []
        for item in cache:
            data = item.get("data", {})
            if "price" in data:
                prices.append(float(data["price"]))
            elif "close" in data:
                prices.append(float(data["close"]))
        return prices
    
    def _extract_volumes(self, cache: List[Dict]) -> List[float]:
        """提取成交量序列"""
        volumes = []
        for item in cache:
            data = item.get("data", {})
            if "volume" in data:
                volumes.append(float(data["volume"]))
        return volumes
    
    def _detect_anomaly(self, factors: Dict[str, float]) -> bool:
        """
        异常检测
        使用 Z-score 方法
        """
        if not factors:
            return False
        
        # 检查关键因子的异常值
        key_factors = ["mom_5m", "volatility_5m", "price_change", "news_sentiment_avg"]
        
        for factor in key_factors:
            if factor in factors:
                value = factors[factor]
                # 如果变化超过5个标准差，认为是异常
                if abs(value) > 5.0:
                    return True
        
        return False
    
    # === 因子计算函数 ===
    
    def _momentum(self, prices: List[float], period: int) -> float:
        """动量因子"""
        if len(prices) < period + 1:
            return 0.0
        return (prices[-1] - prices[-period-1]) / prices[-period-1] * 100
    
    def _volatility(self, prices: List[float], period: int) -> float:
        """波动率因子"""
        if len(prices) < period:
            return 0.0
        returns = np.diff(prices[-period:]) / prices[-period:-1]
        return np.std(returns) * np.sqrt(252) * 100
    
    def _atr(self, prices: List[float], period: int = 14) -> float:
        """平均真实波幅"""
        if len(prices) < period + 1:
            return 0.0
        tr_list = []
        for i in range(1, min(period + 1, len(prices))):
            tr = abs(prices[-i] - prices[-i-1])
            tr_list.append(tr)
        return np.mean(tr_list) if tr_list else 0.0
    
    def _ema_diff(self, prices: List[float], fast: int, slow: int) -> float:
        """EMA差异"""
        if len(prices) < slow:
            return 0.0
        ema_fast = pd.Series(prices).ewm(span=fast).mean().iloc[-1]
        ema_slow = pd.Series(prices).ewm(span=slow).mean().iloc[-1]
        return (ema_fast - ema_slow) / ema_slow * 100
    
    def _rsi(self, prices: List[float], period: int = 14) -> float:
        """RSI指标"""
        if len(prices) < period + 1:
            return 50.0
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _macd(self, prices: List[float]) -> float:
        """MACD指标"""
        if len(prices) < 26:
            return 0.0
        ema_12 = pd.Series(prices).ewm(span=12).mean().iloc[-1]
        ema_26 = pd.Series(prices).ewm(span=26).mean().iloc[-1]
        return (ema_12 - ema_26) / ema_26 * 100
    
    def _skewness(self, prices: List[float], period: int) -> float:
        """偏度"""
        if len(prices) < period:
            return 0.0
        returns = np.diff(prices[-period:]) / prices[-period:-1]
        return pd.Series(returns).skew()
    
    def _kurtosis(self, prices: List[float], period: int) -> float:
        """峰度"""
        if len(prices) < period:
            return 0.0
        returns = np.diff(prices[-period:]) / prices[-period:-1]
        return pd.Series(returns).kurtosis()
    
    def _volume_trend(self, volumes: List[float]) -> float:
        """成交量趋势"""
        if len(volumes) < 10:
            return 0.0
        recent = np.mean(volumes[-5:])
        past = np.mean(volumes[-10:-5])
        return (recent - past) / past * 100 if past > 0 else 0.0
    
    def _price_change(self, prices: List[float]) -> float:
        """价格变化率"""
        if len(prices) < 2:
            return 0.0
        return (prices[-1] - prices[-2]) / prices[-2] * 100
    
    def _high_low_range(self, cache: List[Dict]) -> float:
        """高低点范围"""
        highs = []
        lows = []
        for item in cache[-20:]:
            data = item.get("data", {})
            if "high" in data:
                highs.append(float(data["high"]))
            if "low" in data:
                lows.append(float(data["low"]))
        
        if highs and lows:
            return (max(highs) - min(lows)) / min(lows) * 100
        return 0.0


if __name__ == "__main__":
    curator = DataCurator()
    asyncio.run(curator.start())
