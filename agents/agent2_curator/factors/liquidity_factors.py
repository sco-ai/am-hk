"""
流动性因子模块 - Liquidity Factors
包含: 订单簿深度、资金费率变化、滑点估计
"""
import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum


class LiquidityLevel(Enum):
    """流动性水平"""
    EXCELLENT = "excellent"
    GOOD = "good"
    NORMAL = "normal"
    POOR = "poor"
    BAD = "bad"


@dataclass
class OrderBookDepthResult:
    """订单簿深度结果"""
    bid_depth: float  # 买盘深度 (base currency)
    ask_depth: float  # 卖盘深度
    total_depth: float
    bid_depth_usd: float  # 美元计价
    ask_depth_usd: float
    imbalance: float  # -1 到 1, 正值表示买盘更强
    depth_score: float  # 0-1 深度评分


@dataclass
class FundingRateResult:
    """资金费率结果"""
    current_rate: float
    predicted_rate: float
    avg_8h: float
    avg_24h: float
    trend: str  # "rising", "falling", "stable"
    extremity: float  # 极端程度 0-1
    signal: str  # "long_pays_short", "short_pays_long", "neutral"


@dataclass
class SlippageEstimate:
    """滑点估计"""
    buy_slippage_1k: float  # 买入1k USD的滑点 (%)
    buy_slippage_10k: float
    buy_slippage_100k: float
    sell_slippage_1k: float
    sell_slippage_10k: float
    sell_slippage_100k: float
    avg_slippage: float
    liquidity_score: float  # 0-1


class LiquidityFactors:
    """流动性因子计算器"""
    
    def __init__(self):
        self.depth_history: Dict[str, List[Dict]] = {}
        self.funding_history: Dict[str, List[float]] = {}
        self.max_history = 100
    
    def calculate_orderbook_depth(
        self,
        bids: List[List[float]],  # [[price, qty], ...]
        asks: List[List[float]],
        price: float,
        depth_levels: int = 10
    ) -> OrderBookDepthResult:
        """
        计算订单簿深度
        
        Args:
            bids: 买单 [[price, quantity], ...]
            asks: 卖单
            price: 当前价格
            depth_levels: 计算深度档位数
            
        Returns:
            OrderBookDepthResult
        """
        if not bids or not asks:
            return OrderBookDepthResult(
                bid_depth=0, ask_depth=0, total_depth=0,
                bid_depth_usd=0, ask_depth_usd=0,
                imbalance=0, depth_score=0
            )
        
        # 限制档位数
        bids = bids[:depth_levels]
        asks = asks[:depth_levels]
        
        # 计算深度
        bid_depth = sum(b[1] for b in bids)  # base currency数量
        ask_depth = sum(a[1] for a in asks)
        
        # 美元计价深度
        bid_depth_usd = sum(b[0] * b[1] for b in bids)
        ask_depth_usd = sum(a[0] * a[1] for a in asks)
        
        total_depth = bid_depth + ask_depth
        total_depth_usd = bid_depth_usd + ask_depth_usd
        
        # 买卖不平衡
        if total_depth > 0:
            imbalance = (bid_depth - ask_depth) / total_depth
        else:
            imbalance = 0
        
        # 深度评分 (基于美元深度)
        # 假设 > $1M 为优秀, < $10k 为差
        depth_score = min(total_depth_usd / 1_000_000, 1.0)
        
        return OrderBookDepthResult(
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            total_depth=total_depth,
            bid_depth_usd=bid_depth_usd,
            ask_depth_usd=ask_depth_usd,
            imbalance=imbalance,
            depth_score=depth_score
        )
    
    def calculate_funding_rate_features(
        self,
        symbol: str,
        current_rate: float,
        predicted_rate: Optional[float] = None
    ) -> FundingRateResult:
        """
        计算资金费率特征
        
        Args:
            symbol: 交易对
            current_rate: 当前资金费率
            predicted_rate: 预测资金费率 (可选)
            
        Returns:
            FundingRateResult
        """
        # 保存历史
        if symbol not in self.funding_history:
            self.funding_history[symbol] = []
        
        self.funding_history[symbol].append(current_rate)
        if len(self.funding_history[symbol]) > self.max_history:
            self.funding_history[symbol] = self.funding_history[symbol][-self.max_history:]
        
        history = self.funding_history[symbol]
        
        # 计算平均
        avg_8h = np.mean(history[-3:]) if len(history) >= 3 else current_rate
        avg_24h = np.mean(history[-9:]) if len(history) >= 9 else avg_8h
        
        # 趋势判断
        if len(history) >= 2:
            if current_rate > avg_8h * 1.2:
                trend = "rising"
            elif current_rate < avg_8h * 0.8:
                trend = "falling"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        # 极端程度 (资金费率通常在 -0.1% 到 0.1% 之间)
        extremity = min(abs(current_rate) / 0.001, 1.0)
        
        # 信号判断
        if current_rate > 0.0005:  # 0.05%
            signal = "long_pays_short"  # 多头支付空头, 做空有优势
        elif current_rate < -0.0005:
            signal = "short_pays_long"  # 空头支付多头, 做多有优势
        else:
            signal = "neutral"
        
        # 如果没有提供预测,使用简单线性预测
        if predicted_rate is None and len(history) >= 3:
            predicted_rate = history[-1] + (history[-1] - history[-3]) / 2
        else:
            predicted_rate = current_rate
        
        return FundingRateResult(
            current_rate=current_rate,
            predicted_rate=predicted_rate,
            avg_8h=avg_8h,
            avg_24h=avg_24h,
            trend=trend,
            extremity=extremity,
            signal=signal
        )
    
    def estimate_slippage(
        self,
        bids: List[List[float]],
        asks: List[List[float]],
        order_sizes: List[float] = [1000, 10000, 100000]  # USD
    ) -> SlippageEstimate:
        """
        估计不同订单规模的滑点
        
        Args:
            bids: 买单
            asks: 卖单
            order_sizes: 订单规模 (USD)
            
        Returns:
            SlippageEstimate
        """
        if not bids or not asks:
            return SlippageEstimate(
                buy_slippage_1k=0, buy_slippage_10k=0, buy_slippage_100k=0,
                sell_slippage_1k=0, sell_slippage_10k=0, sell_slippage_100k=0,
                avg_slippage=0, liquidity_score=0
            )
        
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid_price = (best_bid + best_ask) / 2
        
        def calc_slippage(orders: List[List[float]], size_usd: float, is_buy: bool) -> float:
            """计算指定规模的滑点"""
            remaining = size_usd
            total_qty = 0
            total_cost = 0
            
            for price, qty in orders:
                order_value = price * qty
                take = min(remaining, order_value)
                take_qty = take / price
                
                total_qty += take_qty
                total_cost += take
                remaining -= take
                
                if remaining <= 0:
                    break
            
            if total_qty == 0:
                return 1.0  # 100% 滑点 (无法成交)
            
            avg_price = total_cost / total_qty
            slippage = abs(avg_price - mid_price) / mid_price
            
            return slippage * 100  # 转为百分比
        
        # 计算各规模滑点
        buy_slippages = [calc_slippage(asks, size, True) for size in order_sizes]
        sell_slippages = [calc_slippage(bids, size, False) for size in order_sizes]
        
        # 流动性评分 (基于最大规模的平均滑点)
        avg_max_slippage = (buy_slippages[-1] + sell_slippages[-1]) / 2
        liquidity_score = max(0, 1 - avg_max_slippage / 0.01)  # 1%滑点为0分
        
        return SlippageEstimate(
            buy_slippage_1k=buy_slippages[0],
            buy_slippage_10k=buy_slippages[1],
            buy_slippage_100k=buy_slippages[2],
            sell_slippage_1k=sell_slippages[0],
            sell_slippage_10k=sell_slippages[1],
            sell_slippage_100k=sell_slippages[2],
            avg_slippage=np.mean(buy_slippages + sell_slippages),
            liquidity_score=liquidity_score
        )
    
    def calculate_liquidity_stress(
        self,
        symbol: str,
        current_depth: OrderBookDepthResult,
        price_change_pct: float
    ) -> Dict[str, any]:
        """
        计算流动性压力指标
        
        检测大单冲击后的流动性变化
        """
        # 保存历史深度
        if symbol not in self.depth_history:
            self.depth_history[symbol] = []
        
        self.depth_history[symbol].append({
            "depth": current_depth.total_depth_usd,
            "imbalance": current_depth.imbalance,
            "timestamp": pd.Timestamp.now()
        })
        
        if len(self.depth_history[symbol]) > self.max_history:
            self.depth_history[symbol] = self.depth_history[symbol][-self.max_history:]
        
        history = self.depth_history[symbol]
        
        # 深度变化
        if len(history) >= 2:
            depth_change = (history[-1]["depth"] - history[-2]["depth"]) / history[-2]["depth"] if history[-2]["depth"] > 0 else 0
        else:
            depth_change = 0
        
        # 压力指标: 价格大幅变动但深度没有相应恢复
        stress = 0.0
        if abs(price_change_pct) > 1 and depth_change < -0.2:
            stress = min(abs(price_change_pct) / 5, 1.0)
        
        return {
            "liquidity_stress": stress,
            "depth_change_1m": depth_change,
            "depth_vs_avg": current_depth.total_depth_usd / np.mean([h["depth"] for h in history]) if history else 1.0,
            "resilience": 1 - stress
        }
    
    def calculate_spread_factors(
        self,
        bids: List[List[float]],
        asks: List[List[float]],
        price: float
    ) -> Dict[str, float]:
        """
        计算价差相关因子
        """
        if not bids or not asks:
            return {
                "spread": 0,
                "spread_pct": 0,
                "spread_score": 0,
                "weighted_spread": 0
            }
        
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        
        # 基础价差
        spread = best_ask - best_bid
        spread_pct = (spread / price) * 100 if price > 0 else 0
        
        # 价差评分 (越小越好)
        # < 0.01% 优秀, > 0.1% 差
        spread_score = max(0, 1 - spread_pct / 0.1)
        
        # 加权价差 (考虑深度)
        total_bid_qty = sum(b[1] for b in bids[:5])
        total_ask_qty = sum(a[1] for a in asks[:5])
        
        weighted_bid = sum(b[0] * b[1] for b in bids[:5]) / total_bid_qty if total_bid_qty > 0 else best_bid
        weighted_ask = sum(a[0] * a[1] for a in asks[:5]) / total_ask_qty if total_ask_qty > 0 else best_ask
        weighted_spread = ((weighted_ask - weighted_bid) / price) * 100 if price > 0 else 0
        
        return {
            "spread": spread,
            "spread_pct": spread_pct,
            "spread_score": spread_score,
            "weighted_spread_pct": weighted_spread
        }
    
    def calculate_all(
        self,
        symbol: str,
        bids: List[List[float]],
        asks: List[List[float]],
        price: float,
        funding_rate: Optional[float] = None,
        price_change_pct: float = 0
    ) -> Dict[str, any]:
        """
        计算所有流动性因子
        """
        # 订单簿深度
        depth = self.calculate_orderbook_depth(bids, asks, price)
        
        # 滑点估计
        slippage = self.estimate_slippage(bids, asks)
        
        # 价差因子
        spread = self.calculate_spread_factors(bids, asks, price)
        
        result = {
            # 深度
            "bid_depth": depth.bid_depth,
            "ask_depth": depth.ask_depth,
            "total_depth_usd": depth.total_depth,
            "depth_imbalance": depth.imbalance,
            "depth_score": depth.depth_score,
            
            # 滑点
            "slippage_1k": (slippage.buy_slippage_1k + slippage.sell_slippage_1k) / 2,
            "slippage_10k": (slippage.buy_slippage_10k + slippage.sell_slippage_10k) / 2,
            "slippage_100k": (slippage.buy_slippage_100k + slippage.sell_slippage_100k) / 2,
            "liquidity_score": slippage.liquidity_score,
            
            # 价差
            "spread": spread["spread"],
            "spread_pct": spread["spread_pct"],
            "spread_score": spread["spread_score"],
            "weighted_spread_pct": spread["weighted_spread_pct"],
        }
        
        # 资金费率
        if funding_rate is not None:
            funding = self.calculate_funding_rate_features(symbol, funding_rate)
            result.update({
                "funding_rate": funding.current_rate,
                "funding_rate_8h_avg": funding.avg_8h,
                "funding_rate_24h_avg": funding.avg_24h,
                "funding_trend": funding.trend,
                "funding_extremity": funding.extremity,
                "funding_signal": funding.signal,
            })
        
        # 流动性压力
        stress = self.calculate_liquidity_stress(symbol, depth, price_change_pct)
        result.update({
            "liquidity_stress": stress["liquidity_stress"],
            "liquidity_resilience": stress["resilience"],
        })
        
        return result


# 全局实例
liquidity_factors = LiquidityFactors()
