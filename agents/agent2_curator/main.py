"""
Agent 2: DataCurator (数据策展师) - Enhanced v3.0
数据清洗、标准化、技术指标计算、跨市场信号融合

职责：
- 接收 Agent1 的原始数据（Kafka: am-hk-raw-market-data）
- 数据清洗、标准化、质量校验
- 计算30+机构级因子（量价/盘口/资金流/跨市场）
- 多市场特征融合（Crypto → 美股 → 港股）
- 标准化输出供 Agent3 使用（Kafka: am-hk-processed-data）
"""
import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from core.kafka import MessageBus, AgentConsumer
from core.models import MarketType, DataType
from core.utils import generate_timestamp, setup_logging

logger = setup_logging("agent2_curator")


class DataQualityLevel(str, Enum):
    """数据质量等级"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNRELIABLE = "unreliable"


class MarketLayer(str, Enum):
    """市场层级"""
    LAYER1_CRYPTO = "layer1_crypto"
    LAYER2_US_CONFIRM = "layer2_us"
    LAYER3_HK_EXECUTE = "layer3_hk"


@dataclass
class DataQualityMetrics:
    """数据质量指标"""
    symbol: str
    timestamp: datetime
    latency_ms: float
    completeness_pct: float
    outlier_count: int
    missing_count: int
    quality_level: DataQualityLevel
    quality_score: float

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": round(self.latency_ms, 2),
            "completeness_pct": round(self.completeness_pct, 2),
            "outlier_count": self.outlier_count,
            "missing_count": self.missing_count,
            "quality_level": self.quality_level.value,
            "quality_score": round(self.quality_score, 4),
        }


@dataclass
class FactorBundle:
    """30+机构级因子集合"""
    # 量价因子 (10个)
    price_momentum_5m: Optional[float] = None
    price_momentum_15m: Optional[float] = None
    price_momentum_1h: Optional[float] = None
    volume_momentum: Optional[float] = None
    volatility_5m: Optional[float] = None
    volatility_20: Optional[float] = None
    liquidity_score: Optional[float] = None
    turnover_rate: Optional[float] = None
    price_acceleration: Optional[float] = None
    volume_price_trend: Optional[float] = None
    
    # 技术指标 (8个)
    ma_5: Optional[float] = None
    ma_20: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    atr_14: Optional[float] = None
    
    # 盘口因子 (6个)
    bid_ask_spread: Optional[float] = None
    orderbook_imbalance: Optional[float] = None
    depth_imbalance: Optional[float] = None
    depth_change_rate: Optional[float] = None
    bid_pressure: Optional[float] = None
    ask_pressure: Optional[float] = None
    
    # 资金流因子 (6个)
    net_inflow_speed: Optional[float] = None
    main_force_ratio: Optional[float] = None
    retail_ratio: Optional[float] = None
    main_retail_ratio: Optional[float] = None
    northbound_strength: Optional[float] = None
    large_order_net: Optional[float] = None
    
    # 跨市场因子 (5个)
    crypto_correlation: Optional[float] = None
    us_lead_lag: Optional[float] = None
    cross_market_momentum: Optional[float] = None
    layer1_signal: Optional[float] = None
    layer2_confirm: Optional[float] = None

    def to_dict(self) -> Dict[str, float]:
        return {k: v for k, v in {
            "price_momentum_5m": self.price_momentum_5m,
            "price_momentum_15m": self.price_momentum_15m,
            "price_momentum_1h": self.price_momentum_1h,
            "volume_momentum": self.volume_momentum,
            "volatility_5m": self.volatility_5m,
            "volatility_20": self.volatility_20,
            "liquidity_score": self.liquidity_score,
            "turnover_rate": self.turnover_rate,
            "price_acceleration": self.price_acceleration,
            "volume_price_trend": self.volume_price_trend,
            "ma_5": self.ma_5,
            "ma_20": self.ma_20,
            "rsi_14": self.rsi_14,
            "macd": self.macd,
            "macd_signal": self.macd_signal,
            "bb_upper": self.bb_upper,
            "bb_lower": self.bb_lower,
            "atr_14": self.atr_14,
            "bid_ask_spread": self.bid_ask_spread,
            "orderbook_imbalance": self.orderbook_imbalance,
            "depth_imbalance": self.depth_imbalance,
            "depth_change_rate": self.depth_change_rate,
            "bid_pressure": self.bid_pressure,
            "ask_pressure": self.ask_pressure,
            "net_inflow_speed": self.net_inflow_speed,
            "main_force_ratio": self.main_force_ratio,
            "retail_ratio": self.retail_ratio,
            "main_retail_ratio": self.main_retail_ratio,
            "northbound_strength": self.northbound_strength,
            "large_order_net": self.large_order_net,
            "crypto_correlation": self.crypto_correlation,
            "us_lead_lag": self.us_lead_lag,
            "cross_market_momentum": self.cross_market_momentum,
            "layer1_signal": self.layer1_signal,
            "layer2_confirm": self.layer2_confirm,
        }.items() if v is not None}


class ProcessedMarketData(BaseModel):
    """处理后输出的标准化市场数据"""
    symbol: str
    market: MarketType
    timestamp: datetime
    data_type: DataType
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    factors: Dict[str, float] = Field(default_factory=dict)
    cross_market_signals: List[Dict] = Field(default_factory=list)
    quality_score: float = 0.0
    quality_metrics: Dict[str, Any] = Field(default_factory=dict)
    processing_timestamp: datetime = Field(default_factory=generate_timestamp)
    data_hash: str = ""


class DataCleaner:
    """数据清洗器 - Z-score异常检测"""
    
    def __init__(self, price_jump_threshold: float = 0.10, max_latency_ms: float = 50.0, zscore_threshold: float = 3.0):
        self.price_jump_threshold = price_jump_threshold
        self.max_latency_ms = max_latency_ms
        self.zscore_threshold = zscore_threshold
        self.last_prices: Dict[str, float] = {}
        self.price_history: Dict[str, deque] = {}

    def clean_kline_data(self, symbol: str, data: Dict) -> Tuple[Optional[Dict], DataQualityMetrics]:
        """清洗K线数据"""
        # K线数据复用Tick数据清洗逻辑，但添加OHLC字段
        start_time = time.time()
        
        # 使用close价格作为主要价格
        price = data.get("close")
        if price is None:
            price = self._extract_price(data)
        
        timestamp = self._extract_timestamp(data)
        volume = data.get("volume", 0)
        
        missing_count = 0
        if price is None:
            missing_count += 1
            price = self._forward_fill_price(symbol)
        
        if timestamp is None:
            missing_count += 1
            timestamp = generate_timestamp()
        
        outlier_count = 0
        is_outlier = False
        zscore = 0.0
        
        if price is not None:
            zscore = self._calculate_zscore(symbol, price)
            if abs(zscore) > self.zscore_threshold:
                outlier_count += 1
                is_outlier = True
                price = self._forward_fill_price(symbol) or price
        
        if isinstance(timestamp, datetime):
            timestamp = timestamp.replace(microsecond=(timestamp.microsecond // 1000) * 1000)
        
        latency_ms = (time.time() - start_time) * 1000
        if isinstance(timestamp, datetime):
            data_age_ms = (generate_timestamp() - timestamp).total_seconds() * 1000
            latency_ms = max(latency_ms, data_age_ms)
        
        expected_fields = ["open", "high", "low", "close", "volume"]
        present_fields = sum(1 for f in expected_fields if data.get(f) is not None)
        completeness_pct = (present_fields / len(expected_fields)) * 100
        
        quality_score = self._calculate_quality_score(latency_ms, completeness_pct, outlier_count)
        quality_level = self._determine_quality_level(latency_ms, completeness_pct, outlier_count)
        
        quality_metrics = DataQualityMetrics(
            symbol=symbol, timestamp=generate_timestamp(), latency_ms=latency_ms,
            completeness_pct=completeness_pct, outlier_count=outlier_count,
            missing_count=missing_count, quality_level=quality_level, quality_score=quality_score
        )
        
        if quality_level == DataQualityLevel.UNRELIABLE:
            return None, quality_metrics
        
        cleaned_data = {
            "symbol": symbol,
            "price": price,
            "open": data.get("open"),
            "high": data.get("high"),
            "low": data.get("low"),
            "close": data.get("close"),
            "volume": volume,
            "interval": data.get("interval"),
            "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            "zscore": zscore,
            "is_outlier": is_outlier,
        }
        
        if price is not None:
            self.last_prices[symbol] = price
            if symbol not in self.price_history:
                self.price_history[symbol] = deque(maxlen=1000)
            self.price_history[symbol].append({"timestamp": timestamp, "price": price, "volume": volume})
        
        return cleaned_data, quality_metrics

    def clean_orderbook_data(self, symbol: str, data: Dict) -> Tuple[Optional[Dict], DataQualityMetrics]:
        """清洗订单簿数据"""
        start_time = time.time()
        
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        timestamp = self._extract_timestamp(data)
        
        missing_count = 0
        if not bids or not asks:
            missing_count += 1
        
        if timestamp is None:
            missing_count += 1
            timestamp = generate_timestamp()
        
        # 计算买卖盘质量
        total_bid_volume = sum(b[1] for b in bids[:5]) if bids else 0
        total_ask_volume = sum(a[1] for a in asks[:5]) if asks else 0
        spread = (asks[0][0] - bids[0][0]) if bids and asks else 0
        
        outlier_count = 0
        if spread > 0 and bids:
            mid_price = (bids[0][0] + asks[0][0]) / 2
            spread_pct = spread / mid_price
            if spread_pct > 0.05:  # 5% spread is suspicious
                outlier_count += 1
        
        latency_ms = (time.time() - start_time) * 1000
        completeness_pct = 100 - (missing_count * 20)
        
        quality_score = self._calculate_quality_score(latency_ms, completeness_pct, outlier_count)
        quality_level = self._determine_quality_level(latency_ms, completeness_pct, outlier_count)
        
        quality_metrics = DataQualityMetrics(
            symbol=symbol, timestamp=generate_timestamp(), latency_ms=latency_ms,
            completeness_pct=completeness_pct, outlier_count=outlier_count,
            missing_count=missing_count, quality_level=quality_level, quality_score=quality_score
        )
        
        if quality_level == DataQualityLevel.UNRELIABLE:
            return None, quality_metrics
        
        cleaned_data = {
            "symbol": symbol,
            "bids": bids[:10],  # 只保留前10档
            "asks": asks[:10],
            "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            "spread": spread,
            "total_bid_volume": total_bid_volume,
            "total_ask_volume": total_ask_volume,
        }
        
        return cleaned_data, quality_metrics

    def clean_tick_data(self, symbol: str, data: Dict) -> Tuple[Optional[Dict], DataQualityMetrics]:
        """清洗Tick数据"""
        start_time = time.time()
        
        price = self._extract_price(data)
        timestamp = self._extract_timestamp(data)
        volume = data.get("volume", data.get("vol", 0))
        
        missing_count = 0
        if price is None:
            missing_count += 1
            price = self._forward_fill_price(symbol)
        
        if timestamp is None:
            missing_count += 1
            timestamp = generate_timestamp()
        
        outlier_count = 0
        is_outlier = False
        zscore = 0.0
        
        if price is not None:
            zscore = self._calculate_zscore(symbol, price)
            if abs(zscore) > self.zscore_threshold:
                outlier_count += 1
                is_outlier = True
                logger.warning(f"Z-score outlier for {symbol}: z={zscore:.2f}")
                price = self._forward_fill_price(symbol) or price
        
        if isinstance(timestamp, datetime):
            timestamp = timestamp.replace(microsecond=(timestamp.microsecond // 1000) * 1000)
        
        latency_ms = (time.time() - start_time) * 1000
        if isinstance(timestamp, datetime):
            data_age_ms = (generate_timestamp() - timestamp).total_seconds() * 1000
            latency_ms = max(latency_ms, data_age_ms)
        
        expected_fields = ["price", "timestamp", "volume"]
        present_fields = sum(1 for f in expected_fields if data.get(f) is not None)
        completeness_pct = (present_fields / len(expected_fields)) * 100
        
        quality_score = self._calculate_quality_score(latency_ms, completeness_pct, outlier_count)
        quality_level = self._determine_quality_level(latency_ms, completeness_pct, outlier_count)
        
        quality_metrics = DataQualityMetrics(
            symbol=symbol, timestamp=generate_timestamp(), latency_ms=latency_ms,
            completeness_pct=completeness_pct, outlier_count=outlier_count,
            missing_count=missing_count, quality_level=quality_level, quality_score=quality_score
        )
        
        if quality_level == DataQualityLevel.UNRELIABLE:
            return None, quality_metrics
        
        cleaned_data = {
            "symbol": symbol, "price": price,
            "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            "volume": volume, "zscore": zscore, "is_outlier": is_outlier, "original_data": data,
        }
        
        if price is not None:
            self.last_prices[symbol] = price
            if symbol not in self.price_history:
                self.price_history[symbol] = deque(maxlen=1000)
            self.price_history[symbol].append({"timestamp": timestamp, "price": price, "volume": volume})
        
        return cleaned_data, quality_metrics

    def _calculate_zscore(self, symbol: str, price: float) -> float:
        history = self.price_history.get(symbol, deque(maxlen=100))
        if len(history) < 20:
            return 0.0
        prices = [item["price"] for item in history]
        mean = np.mean(prices)
        std = np.std(prices)
        return (price - mean) / std if std > 0 else 0.0

    def _calculate_quality_score(self, latency_ms: float, completeness_pct: float, outlier_count: int) -> float:
        latency_score = max(0, 1 - latency_ms / self.max_latency_ms)
        completeness_score = completeness_pct / 100
        outlier_score = max(0, 1 - outlier_count * 0.2)
        return round(latency_score * 0.4 + completeness_score * 0.4 + outlier_score * 0.2, 4)

    def _determine_quality_level(self, latency_ms: float, completeness_pct: float, outlier_count: int) -> DataQualityLevel:
        if latency_ms < 10 and completeness_pct >= 100 and outlier_count == 0:
            return DataQualityLevel.EXCELLENT
        elif latency_ms < 30 and completeness_pct >= 99 and outlier_count <= 1:
            return DataQualityLevel.GOOD
        elif latency_ms < 50 and completeness_pct >= 95 and outlier_count <= 2:
            return DataQualityLevel.ACCEPTABLE
        elif latency_ms < 100 and completeness_pct >= 90:
            return DataQualityLevel.POOR
        else:
            return DataQualityLevel.UNRELIABLE

    def _extract_price(self, data: Dict) -> Optional[float]:
        for key in ["price", "last_price", "close", "last", "trade_price"]:
            if key in data and data[key] is not None:
                try:
                    return float(data[key])
                except (ValueError, TypeError):
                    continue
        return None

    def _extract_timestamp(self, data: Dict) -> Optional[datetime]:
        ts = data.get("timestamp")
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, (int, float)):
            if ts > 1e12:
                ts = ts / 1000
            return datetime.fromtimestamp(ts)
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except:
                pass
        return None

    def _forward_fill_price(self, symbol: str) -> Optional[float]:
        return self.last_prices.get(symbol)


class FactorCalculator:
    """30+机构级因子计算器"""
    
    def __init__(self):
        self.history_cache: Dict[str, deque] = {}
        self.orderbook_cache: Dict[str, Dict] = {}
        self.max_cache_size = 500

    def calculate_all_factors(self, symbol: str, market: str, cleaned_data: Dict, cross_market_state: Dict) -> FactorBundle:
        """计算全部30+因子"""
        bundle = FactorBundle()
        self._update_history(symbol, cleaned_data)
        history = self.history_cache.get(symbol, deque(maxlen=self.max_cache_size))
        
        if len(history) < 5:
            return bundle
        
        prices = pd.Series([h["price"] for h in history])
        volumes = pd.Series([h.get("volume", 0) for h in history])
        
        bundle = self._calculate_price_volume_factors(bundle, prices, volumes)
        bundle = self._calculate_technical_factors(bundle, prices)
        
        if "bids" in cleaned_data and "asks" in cleaned_data:
            bundle = self._calculate_orderbook_factors(bundle, cleaned_data, prices.iloc[-1] if len(prices) > 0 else None)
        
        if any(k in cleaned_data for k in ["main_force_inflow", "northbound_net_inflow"]):
            bundle = self._calculate_capital_flow_factors(bundle, cleaned_data)
        
        bundle = self._calculate_cross_market_factors(bundle, symbol, cross_market_state)
        
        return bundle

    def _calculate_price_volume_factors(self, bundle: FactorBundle, prices: pd.Series, volumes: pd.Series) -> FactorBundle:
        if len(prices) >= 6:
            bundle.price_momentum_5m = (prices.iloc[-1] - prices.iloc[-6]) / prices.iloc[-6] * 100
        if len(prices) >= 16:
            bundle.price_momentum_15m = (prices.iloc[-1] - prices.iloc[-16]) / prices.iloc[-16] * 100
        if len(prices) >= 61:
            bundle.price_momentum_1h = (prices.iloc[-1] - prices.iloc[-61]) / prices.iloc[-61] * 100
        
        if len(volumes) >= 20 and volumes.iloc[-20:].mean() > 0:
            bundle.volume_momentum = volumes.iloc[-1] / volumes.iloc[-20:].mean()
        
        if len(prices) >= 6:
            returns = prices.pct_change().dropna()
            bundle.volatility_5m = returns.iloc[-5:].std() * np.sqrt(252) * 100
        if len(prices) >= 21:
            returns = prices.pct_change().dropna()
            bundle.volatility_20 = returns.iloc[-20:].std() * np.sqrt(252) * 100
        
        if len(volumes) >= 20:
            avg_volume = volumes.iloc[-20:].mean()
            bundle.liquidity_score = min(1.0, volumes.iloc[-1] / (avg_volume * 2)) if avg_volume > 0 else 0.5
        
        if len(volumes) >= 10:
            bundle.turnover_rate = volumes.iloc[-1] / volumes.iloc[-10:].mean() if volumes.iloc[-10:].mean() > 0 else 1.0
        
        if len(prices) >= 3:
            v1 = prices.iloc[-2] - prices.iloc[-3]
            v2 = prices.iloc[-1] - prices.iloc[-2]
            bundle.price_acceleration = v2 - v1
        
        if len(prices) >= 10 and len(volumes) >= 10:
            price_change = (prices.iloc[-1] - prices.iloc[-10]) / prices.iloc[-10]
            volume_change = (volumes.iloc[-1] - volumes.iloc[-10]) / volumes.iloc[-10] if volumes.iloc[-10] > 0 else 0
            bundle.volume_price_trend = price_change * volume_change * 100
        
        return bundle

    def _calculate_technical_factors(self, bundle: FactorBundle, prices: pd.Series) -> FactorBundle:
        if len(prices) >= 5:
            bundle.ma_5 = prices.iloc[-5:].mean()
        if len(prices) >= 20:
            bundle.ma_20 = prices.iloc[-20:].mean()
        
        if len(prices) >= 15:
            deltas = prices.diff().dropna()
            gains = deltas.where(deltas > 0, 0)
            losses = -deltas.where(deltas < 0, 0)
            avg_gain = gains.iloc[-14:].mean()
            avg_loss = losses.iloc[-14:].mean()
            bundle.rsi_14 = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100.0
        
        if len(prices) >= 26:
            ema_12 = prices.ewm(span=12, adjust=False).mean().iloc[-1]
            ema_26 = prices.ewm(span=26, adjust=False).mean().iloc[-1]
            bundle.macd = ema_12 - ema_26
            macd_line = prices.ewm(span=12, adjust=False).mean() - prices.ewm(span=26, adjust=False).mean()
            bundle.macd_signal = macd_line.ewm(span=9, adjust=False).mean().iloc[-1]
        
        if len(prices) >= 20:
            ma = prices.iloc[-20:].mean()
            std = prices.iloc[-20:].std()
            bundle.bb_upper = ma + 2 * std
            bundle.bb_lower = ma - 2 * std
        
        return bundle

    def _calculate_orderbook_factors(self, bundle: FactorBundle, data: Dict, last_price: Optional[float]) -> FactorBundle:
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        if not bids or not asks:
            return bundle
        
        bid_prices, bid_qtys = self._parse_levels(bids)
        ask_prices, ask_qtys = self._parse_levels(asks)
        if not bid_prices or not ask_prices:
            return bundle
        
        best_bid, best_ask = bid_prices[0], ask_prices[0]
        mid_price = (best_bid + best_ask) / 2
        
        bundle.bid_ask_spread = best_ask - best_bid
        if mid_price > 0:
            bundle.bid_ask_spread = bundle.bid_ask_spread / mid_price * 100
        
        bid_depth = sum(bid_qtys)
        ask_depth = sum(ask_qtys)
        if bid_depth + ask_depth > 0:
            bundle.orderbook_imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth)
        
        bid_depth_5 = sum(bid_qtys[:5])
        ask_depth_5 = sum(ask_qtys[:5])
        if bid_depth_5 + ask_depth_5 > 0:
            bundle.depth_imbalance = (bid_depth_5 - ask_depth_5) / (bid_depth_5 + ask_depth_5)
        
        last_orderbook = self.orderbook_cache.get(data.get("symbol", ""), {})
        if last_orderbook:
            last_bid_depth = sum([q for _, q in self._parse_levels(last_orderbook.get("bids", []))])
            last_ask_depth = sum([q for _, q in self._parse_levels(last_orderbook.get("asks", []))])
            if last_bid_depth + last_ask_depth > 0:
                current_total = bid_depth + ask_depth
                last_total = last_bid_depth + last_ask_depth
                bundle.depth_change_rate = (current_total - last_total) / last_total * 100
        
        if bid_depth > 0:
            bundle.bid_pressure = bid_depth_5 / bid_depth
        if ask_depth > 0:
            bundle.ask_pressure = ask_depth_5 / ask_depth
        
        self.orderbook_cache[data.get("symbol", "")] = {"bids": bids, "asks": asks}
        return bundle

    def _calculate_capital_flow_factors(self, bundle: FactorBundle, data: Dict) -> FactorBundle:
        payload = data.get("payload", data)
        
        north_in = payload.get("northbound_net_inflow", 0)
        north_out = payload.get("northbound_net_outflow", 0)
        north_net = north_in - north_out
        if abs(north_in) + abs(north_out) > 0:
            bundle.northbound_strength = north_net / (abs(north_in) + abs(north_out))
        
        main_in = payload.get("main_force_inflow", 0)
        main_out = payload.get("main_force_outflow", 0)
        main_net = main_in - main_out
        retail_net = payload.get("retail_net", 0)
        
        total_flow = abs(main_net) + abs(retail_net)
        if total_flow > 0:
            bundle.main_force_ratio = main_net / total_flow
            bundle.retail_ratio = retail_net / total_flow
            if retail_net != 0:
                bundle.main_retail_ratio = main_net / retail_net
        
        bundle.large_order_net = payload.get("large_order_net", main_net)
        bundle.net_inflow_speed = main_net
        
        return bundle

    def _calculate_cross_market_factors(self, bundle: FactorBundle, symbol: str, cross_market_state: Dict) -> FactorBundle:
        btc_momentum = cross_market_state.get("BTCUSDT", {}).get("momentum_5m", 0)
        eth_momentum = cross_market_state.get("ETHUSDT", {}).get("momentum_5m", 0)
        bundle.layer1_signal = (btc_momentum + eth_momentum) / 2 if btc_momentum or eth_momentum else 0
        
        coin_momentum = cross_market_state.get("COIN", {}).get("momentum_5m", 0)
        mara_momentum = cross_market_state.get("MARA", {}).get("momentum_5m", 0)
        bundle.layer2_confirm = (coin_momentum + mara_momentum) / 2 if coin_momentum or mara_momentum else 0
        
        if symbol in ["00700", "09988", "00863"]:
            bundle.crypto_correlation = 0.35 if symbol == "00700" else 0.42 if symbol == "00863" else 0.30
        
        if bundle.layer1_signal and bundle.layer2_confirm:
            bundle.cross_market_momentum = bundle.layer1_signal * 0.6 + bundle.layer2_confirm * 0.4
        
        return bundle

    def _update_history(self, symbol: str, data: Dict):
        if symbol not in self.history_cache:
            self.history_cache[symbol] = deque(maxlen=self.max_cache_size)
        
        price = data.get("price") or data.get("close")
        if price:
            self.history_cache[symbol].append({
                "timestamp": data.get("timestamp"),
                "price": float(price),
                "volume": float(data.get("volume", 0)),
            })

    def _parse_levels(self, levels: List) -> Tuple[List[float], List[float]]:
        prices, qtys = [], []
        for level in levels:
            if isinstance(level, (list, tuple)) and len(level) >= 2:
                try:
                    prices.append(float(level[0]))
                    qtys.append(float(level[1]))
                except:
                    pass
            elif isinstance(level, dict):
                try:
                    prices.append(float(level.get("price", 0)))
                    qtys.append(float(level.get("quantity", level.get("qty", 0))))
                except:
                    pass
        return prices, qtys


class CrossMarketFusionEngine:
    """跨市场信号融合引擎"""
    
    def __init__(self):
        self.layer_symbols = {
            MarketLayer.LAYER1_CRYPTO: ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            MarketLayer.LAYER2_US_CONFIRM: ["COIN", "MARA", "NVDA"],
            MarketLayer.LAYER3_HK_EXECUTE: ["00700", "09988", "00863", "01024"],
        }
        self.market_states: Dict[str, Dict] = {}
        self.transmission_lags = {
            (MarketLayer.LAYER1_CRYPTO, MarketLayer.LAYER2_US_CONFIRM): 60,
            (MarketLayer.LAYER2_US_CONFIRM, MarketLayer.LAYER3_HK_EXECUTE): 300,
            (MarketLayer.LAYER1_CRYPTO, MarketLayer.LAYER3_HK_EXECUTE): 600,
        }
        self.correlations = {
            ("BTCUSDT", "COIN"): 0.75,
            ("BTCUSDT", "MARA"): 0.68,
            ("COIN", "00700"): 0.35,
        }

    def update_market_state(self, symbol: str, factors: Dict):
        """更新市场状态"""
        self.market_states[symbol] = {
            "timestamp": time.time(),
            "momentum_5m": factors.get("price_momentum_5m", 0),
            "momentum_15m": factors.get("price_momentum_15m", 0),
            "rsi": factors.get("rsi_14", 50),
        }

    def get_cross_market_signals(self, target_symbol: str) -> List[Dict]:
        """生成跨市场传导信号"""
        signals = []
        
        # 确定目标symbol所在层级
        target_layer = None
        for layer, symbols in self.layer_symbols.items():
            if target_symbol in symbols:
                target_layer = layer
                break
        
        if target_layer == MarketLayer.LAYER3_HK_EXECUTE:
            # Layer2 -> Layer3 信号
            for source_symbol in self.layer_symbols[MarketLayer.LAYER2_US_CONFIRM]:
                if source_symbol in self.market_states:
                    state = self.market_states[source_symbol]
                    signal = {
                        "source_layer": MarketLayer.LAYER2_US_CONFIRM.value,
                        "target_layer": MarketLayer.LAYER3_HK_EXECUTE.value,
                        "source_symbol": source_symbol,
                        "target_symbol": target_symbol,
                        "signal_type": "momentum",
                        "strength": abs(state["momentum_5m"]) / 10 if state["momentum_5m"] else 0,
                        "direction": "bullish" if state["momentum_5m"] > 0 else "bearish",
                        "lag_seconds": 300,
                        "correlation": self.correlations.get((source_symbol, target_symbol), 0.3),
                    }
                    signals.append(signal)
            
            # Layer1 -> Layer3 直接传导
            for source_symbol in self.layer_symbols[MarketLayer.LAYER1_CRYPTO]:
                if source_symbol in self.market_states:
                    state = self.market_states[source_symbol]
                    signal = {
                        "source_layer": MarketLayer.LAYER1_CRYPTO.value,
                        "target_layer": MarketLayer.LAYER3_HK_EXECUTE.value,
                        "source_symbol": source_symbol,
                        "target_symbol": target_symbol,
                        "signal_type": "momentum",
                        "strength": abs(state["momentum_5m"]) / 10 if state["momentum_5m"] else 0,
                        "direction": "bullish" if state["momentum_5m"] > 0 else "bearish",
                        "lag_seconds": 600,
                        "correlation": self.correlations.get((source_symbol, target_symbol), 0.2),
                    }
                    signals.append(signal)
        
        return signals

    def get_market_state(self) -> Dict:
        """获取当前市场状态"""
        return self.market_states.copy()


class DataCurator:
    """
    Agent 2: DataCurator - 数据策展师
    
    核心功能：
    1. 数据清洗（去除异常值>10%、前向填充、时间戳对齐）
    2. 30+机构级因子计算（量价/盘口/资金流/跨市场）
    3. 跨市场信号融合（Crypto → 美股 → 港股）
    4. 数据质量控制（延迟≤50ms、完整性检查）
    """
    
    def __init__(self):
        self.agent_name = "agent2_curator"
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-raw-market-data"]
        )
        
        # 核心组件
        self.data_cleaner = DataCleaner(
            price_jump_threshold=0.10,
            max_latency_ms=50.0,
            zscore_threshold=3.0
        )
        self.factor_calculator = FactorCalculator()
        self.fusion_engine = CrossMarketFusionEngine()
        
        # 统计
        self.processed_count = 0
        self.dropped_count = 0
        self.running = False
        
        logger.info(f"{self.agent_name} initialized (30+ factors, cross-market fusion)")

    async def start(self):
        """启动Agent2"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 注册消息处理器
        self.consumer.register_handler("market_data", self._on_market_data)
        self.consumer.register_handler("tick", self._on_tick_data)
        self.consumer.register_handler("kline", self._on_kline_data)
        self.consumer.register_handler("orderbook", self._on_orderbook_data)
        self.consumer.register_handler("capital_flow", self._on_capital_flow)
        
        # 发布状态
        self.bus.publish_status({
            "state": "running",
            "factors_count": 30,
            "cross_market_fusion": True,
            "data_quality_control": True,
        })
        
        # 在后台线程运行消费者，避免阻塞事件循环
        import threading
        consumer_thread = threading.Thread(target=self._run_consumer_sync, name="Agent2Consumer")
        consumer_thread.daemon = True
        consumer_thread.start()
        logger.info(f"Consumer started in background thread: {consumer_thread.name}")
        
        # 保持主循环运行
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Main loop cancelled")
        except Exception as e:
            logger.error(f"Main loop error: {e}", exc_info=True)
        finally:
            await self.stop()

    def _run_consumer_sync(self):
        """在后台线程中同步运行消费者"""
        try:
            self.consumer.start()
        except Exception as e:
            logger.error(f"Consumer thread error: {e}", exc_info=True)
    
    async def stop(self):
        """停止Agent2"""
        logger.info(f"{self.agent_name} stopping...")
        self.running = False
        self.consumer.stop()
        
        self.bus.publish_status({
            "state": "stopped",
            "processed_count": self.processed_count,
            "dropped_count": self.dropped_count
        })
        self.bus.flush()
        self.bus.close()
        
        logger.info(f"{self.agent_name} stopped")


    def _on_market_data(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理市场数据 - 统一入口，根据 data_type 分发到具体处理器"""
        try:
            # 处理可能的包装格式 (来自 message_bus.py)
            if "value" in value and "topic" in value:
                value = value.get("value", value)
            
            data_type = value.get("data_type", "unknown")
            
            # 路由到具体处理器
            if data_type == "tick":
                self._on_tick_data(key, value, headers)
            elif data_type == "kline":
                self._on_kline_data(key, value, headers)
            elif data_type == "orderbook":
                self._on_orderbook_data(key, value, headers)
            elif data_type == "capital_flow":
                self._on_capital_flow(key, value, headers)
            elif data_type in ["news", "sentiment", "status"]:
                # 新闻和情绪数据 - 直接透传或记录
                logger.debug(f"Received {data_type} data for {key}")
                # 可选：将新闻/情绪也发布到 processed-data 供后续 Agent 使用
                self._publish_processed_data(key, value, data_type)
            else:
                logger.debug(f"Unknown data_type '{data_type}' for key {key}, trying generic processing")
                # 尝试通用处理
                if "payload" in value:
                    self._publish_processed_data(key, value, data_type)
                
        except Exception as e:
            logger.error(f"Error processing market data: {e}", exc_info=True)

    def _publish_processed_data(self, key: str, value: Dict, data_type: str):
        """将数据直接发布到 processed-data topic"""
        try:
            symbol = value.get("symbol", key)
            processed_data = {
                "symbol": symbol,
                "market": value.get("market", "unknown"),
                "timestamp": value.get("timestamp", generate_timestamp().isoformat()),
                "data_type": data_type,
                "raw_data": value.get("payload", value),
                "factors": {},
                "cross_market_signals": [],
                "quality_score": 1.0,
                "quality_metrics": {"level": "passthrough"},
                "processing_timestamp": generate_timestamp().isoformat(),
            }
            self.bus.send(topic="am-hk-processed-data", key=symbol, value=processed_data)
        except Exception as e:
            logger.error(f"Error publishing processed data: {e}")


    def _on_tick_data(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理Tick数据"""
        # 解包可能的包装格式
        if "value" in value and "topic" in value:
            value = value.get("value", value)
        
        symbol = value.get("symbol", key)
        market = value.get("market", "unknown")
        payload = value.get("payload", value)
        
        # 1. 数据清洗
        cleaned_data, quality_metrics = self.data_cleaner.clean_tick_data(symbol, payload)
        
        if cleaned_data is None:
            self.dropped_count += 1
            logger.debug(f"Dropped tick data for {symbol}: quality={quality_metrics.quality_level.value}")
            return
        
        # 2. 计算30+因子
        cross_market_state = self.fusion_engine.get_market_state()
        factors = self.factor_calculator.calculate_all_factors(symbol, market, cleaned_data, cross_market_state)
        
        # 3. 更新市场状态
        self.fusion_engine.update_market_state(symbol, factors.to_dict())
        
        # 4. 生成跨市场信号

        cross_market_signals = self.fusion_engine.get_cross_market_signals(symbol)
        
        # 5. 构建输出数据
        processed_data = {
            "symbol": symbol,
            "market": market,
            "timestamp": cleaned_data["timestamp"],
            "data_type": "tick",
            "raw_data": {
                "price": cleaned_data["price"],
                "volume": cleaned_data["volume"],
            },
            "factors": factors.to_dict(),
            "cross_market_signals": cross_market_signals,
            "quality_score": quality_metrics.quality_score,
            "quality_metrics": quality_metrics.to_dict(),
            "processing_timestamp": generate_timestamp().isoformat(),
        }
        
        # 发布到processed-data topic
        self.bus.send(
            topic="am-hk-processed-data",
            key=symbol,
            value=processed_data
        )
        
        self.processed_count += 1
        
        if self.processed_count % 1000 == 0:
            logger.info(f"Processed {self.processed_count} messages, dropped {self.dropped_count}")

    def _on_kline_data(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理K线数据"""
        # 解包可能的包装格式
        if "value" in value and "topic" in value:
            value = value.get("value", value)
        
        symbol = value.get("symbol", key)
        market = value.get("market", "unknown")
        payload = value.get("payload", value)
        
        # 数据清洗
        cleaned_data, quality_metrics = self.data_cleaner.clean_kline_data(symbol, payload)
        
        if cleaned_data is None:
            self.dropped_count += 1
            return
        
        # 更新历史并计算因子
        self.factor_calculator._update_history(symbol, cleaned_data)
        cross_market_state = self.fusion_engine.get_market_state()
        
        # 使用OHLC数据计算更精确的因子
        history = self.factor_calculator.history_cache.get(symbol, deque(maxlen=500))
        if len(history) >= 5:
            prices = pd.Series([h["price"] for h in history])
            factors = self.factor_calculator._calculate_technical_factors(FactorBundle(), prices)
            factors = self.factor_calculator._calculate_price_volume_factors(
                factors, prices, pd.Series([h.get("volume", 0) for h in history])
            )
        else:
            factors = FactorBundle()
        
        # 更新市场状态
        self.fusion_engine.update_market_state(symbol, factors.to_dict())
        
        cross_market_signals = self.fusion_engine.get_cross_market_signals(symbol)
        
        processed_data = {
            "symbol": symbol,
            "market": market,
            "timestamp": cleaned_data["timestamp"],
            "data_type": "kline",
            "raw_data": {
                "open": cleaned_data.get("open"),
                "high": cleaned_data.get("high"),
                "low": cleaned_data.get("low"),
                "close": cleaned_data.get("close"),
                "volume": cleaned_data.get("volume"),
                "interval": cleaned_data.get("interval"),
            },
            "factors": factors.to_dict(),
            "cross_market_signals": cross_market_signals,
            "quality_score": quality_metrics.quality_score,
            "quality_metrics": quality_metrics.to_dict(),
            "processing_timestamp": generate_timestamp().isoformat(),
        }
        
        self.bus.send(topic="am-hk-processed-data", key=symbol, value=processed_data)
        self.processed_count += 1

    def _on_orderbook_data(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理订单簿数据"""
        # 解包可能的包装格式
        if "value" in value and "topic" in value:
            value = value.get("value", value)
        
        symbol = value.get("symbol", key)
        market = value.get("market", "unknown")
        payload = value.get("payload", value)
        
        cleaned_data, quality_metrics = self.data_cleaner.clean_orderbook_data(symbol, payload)
        
        if cleaned_data is None:
            self.dropped_count += 1
            return
        
        # 计算盘口因子
        last_price = self.data_cleaner.last_prices.get(symbol)
        factors = self.factor_calculator._calculate_orderbook_factors(
            FactorBundle(), cleaned_data, last_price
        )
        
        processed_data = {
            "symbol": symbol,
            "market": market,
            "timestamp": cleaned_data["timestamp"],
            "data_type": "orderbook",
            "raw_data": {
                "bids": cleaned_data.get("bids", [])[:5],
                "asks": cleaned_data.get("asks", [])[:5],
            },
            "factors": factors.to_dict(),
            "cross_market_signals": [],
            "quality_score": quality_metrics.quality_score,
            "quality_metrics": quality_metrics.to_dict(),
            "processing_timestamp": generate_timestamp().isoformat(),
        }
        
        self.bus.send(topic="am-hk-processed-data", key=symbol, value=processed_data)
        self.processed_count += 1

    def _on_capital_flow(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理资金流数据"""
        # 解包可能的包装格式
        if "value" in value and "topic" in value:
            value = value.get("value", value)
        
        symbol = value.get("symbol", key)
        market = value.get("market", "unknown")
        payload = value.get("payload", value)
        
        # 计算资金流因子
        factors = self.factor_calculator._calculate_capital_flow_factors(FactorBundle(), payload)
        
        processed_data = {
            "symbol": symbol,
            "market": market,
            "timestamp": generate_timestamp().isoformat(),
            "data_type": "capital_flow",
            "raw_data": payload,
            "factors": factors.to_dict(),
            "cross_market_signals": [],
            "quality_score": 1.0,
            "quality_metrics": {"level": "good"},
            "processing_timestamp": generate_timestamp().isoformat(),
        }
        
        self.bus.send(topic="am-hk-processed-data", key=symbol, value=processed_data)
        self.processed_count += 1


if __name__ == "__main__":
    curator = DataCurator()
    asyncio.run(curator.start())
