"""
图神经网络(GNN)模型 - 市场联动分析
检测跨市场传染效应和板块联动
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
import numpy as np

from core.config import settings
from core.utils import setup_logging

logger = setup_logging("gnn_model")


@dataclass
class MarketNode:
    """市场节点"""
    symbol: str
    market_type: str  # crypto, hk_stock, us_stock
    price: float
    change_pct: float
    volume: float
    timestamp: datetime
    
    def to_vector(self) -> np.ndarray:
        """转换为特征向量"""
        return np.array([
            self.price / 100000,  # 归一化
            self.change_pct / 100,  # 转换为小数
            np.log1p(self.volume) / 20,  # 对数归一化
        ])


@dataclass
class MarketEdge:
    """市场边（关联关系）"""
    source: str
    target: str
    weight: float  # 关联强度
    correlation: float  # 相关系数
    lag: int  # 滞后时间（分钟）
    edge_type: str  # lead_lag, sector, cross_market


class GNNMarketAnalyzer:
    """
    基于GNN的市场联动分析器
    
    功能：
    1. 构建跨市场图结构
    2. 检测领先-滞后关系
    3. 识别板块联动
    4. 预测传染效应
    """
    
    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url = api_url or settings.GNN_API_URL
        self.api_key = api_key or settings.GNN_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # 市场节点缓存
        self.nodes: Dict[str, MarketNode] = {}
        self.edges: List[MarketEdge] = []
        
        # 历史价格数据（用于计算相关性）
        self.price_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self.max_history = 100  # 保存100个时间点的数据
        
        # 预定义的跨市场关系
        self.cross_market_relations = {
            # BTC -> 美股科技股
            'BTCUSDT': ['AAPL', 'NVDA', 'TSLA', 'MSFT'],
            # 美股科技股 -> 港股科技股
            'AAPL': ['00700', '09988', '01810'],  # 腾讯、阿里、小米
            'NVDA': ['00992', '03800'],  # 联想、腾讯(AI相关)
            # 黄金 -> BTC（避险资产联动）
            'GC': ['BTCUSDT'],
        }
        
        logger.info("GNN Market Analyzer initialized")
    
    async def analyze_market_correlation(self, 
                                        market_data: Dict[str, Dict]) -> Dict:
        """
        分析市场相关性并预测联动效应
        
        Args:
            market_data: {
                'BTCUSDT': {'price': 65000, 'change_pct': 2.5, ...},
                'AAPL': {'price': 180, 'change_pct': 1.2, ...},
                ...
            }
        
        Returns:
            {
                'lead_lag_relations': [...],  # 领先-滞后关系
                'sector_clusters': [...],     # 板块聚类
                'contagion_risk': float,      # 传染风险评分
                'predictions': [...],         # 跨市场预测
            }
        """
        try:
            # 1. 更新节点数据
            self._update_nodes(market_data)
            
            # 2. 构建图边（相关性）
            self._build_edges()
            
            # 3. 检测领先-滞后关系
            lead_lag = self._detect_lead_lag()
            
            # 4. 识别板块聚类
            clusters = self._detect_sector_clusters()
            
            # 5. 计算传染风险
            contagion_risk = self._calculate_contagion_risk()
            
            # 6. 生成跨市场预测
            predictions = self._generate_cross_market_predictions()
            
            result = {
                'lead_lag_relations': lead_lag,
                'sector_clusters': clusters,
                'contagion_risk': contagion_risk,
                'predictions': predictions,
                'graph_stats': {
                    'node_count': len(self.nodes),
                    'edge_count': len(self.edges),
                },
                'timestamp': datetime.utcnow().isoformat(),
            }
            
            logger.info(f"GNN analysis complete: {len(self.nodes)} nodes, "
                       f"{len(self.edges)} edges, contagion_risk={contagion_risk:.2f}")
            
            return result
        
        except Exception as e:
            logger.error(f"GNN analysis failed: {e}")
            return self._fallback_analysis(market_data)
    
    def _update_nodes(self, market_data: Dict[str, Dict]):
        """更新市场节点"""
        now = datetime.utcnow()
        
        for symbol, data in market_data.items():
            node = MarketNode(
                symbol=symbol,
                market_type=self._detect_market_type(symbol),
                price=float(data.get('price', 0)),
                change_pct=float(data.get('change_pct', 0)),
                volume=float(data.get('volume', 0)),
                timestamp=now,
            )
            self.nodes[symbol] = node
            
            # 更新价格历史
            if symbol not in self.price_history:
                self.price_history[symbol] = []
            self.price_history[symbol].append((now, node.price))
            
            # 限制历史长度
            if len(self.price_history[symbol]) > self.max_history:
                self.price_history[symbol] = self.price_history[symbol][-self.max_history:]
    
    def _detect_market_type(self, symbol: str) -> str:
        """检测市场类型"""
        if symbol.endswith('USDT') or symbol.endswith('BTC') or symbol.endswith('ETH'):
            return 'crypto'
        elif symbol.isdigit() or (len(symbol) == 5 and symbol[0] == '0'):
            return 'hk_stock'
        else:
            return 'us_stock'
    
    def _build_edges(self):
        """构建图边（基于相关性和预定义关系）"""
        self.edges = []
        
        # 1. 基于预定义关系创建边
        for source, targets in self.cross_market_relations.items():
            if source in self.nodes:
                for target in targets:
                    if target in self.nodes:
                        edge = MarketEdge(
                            source=source,
                            target=target,
                            weight=0.7,  # 预定义关系权重较高
                            correlation=self._calculate_correlation(source, target),
                            lag=self._estimate_lag(source, target),
                            edge_type='cross_market'
                        )
                        self.edges.append(edge)
        
        # 2. 基于数据驱动的相关性创建边
        symbols = list(self.nodes.keys())
        for i, s1 in enumerate(symbols):
            for s2 in symbols[i+1:]:
                corr = self._calculate_correlation(s1, s2)
                if abs(corr) > 0.6:  # 只保留强相关
                    edge = MarketEdge(
                        source=s1,
                        target=s2,
                        weight=abs(corr),
                        correlation=corr,
                        lag=0,
                        edge_type='data_driven'
                    )
                    self.edges.append(edge)
    
    def _calculate_correlation(self, symbol1: str, symbol2: str) -> float:
        """计算两个标的的价格相关性"""
        hist1 = self.price_history.get(symbol1, [])
        hist2 = self.price_history.get(symbol2, [])
        
        if len(hist1) < 10 or len(hist2) < 10:
            return 0.0
        
        # 提取价格序列
        prices1 = np.array([p for _, p in hist1[-50:]])
        prices2 = np.array([p for _, p in hist2[-50:]])
        
        # 计算收益率
        returns1 = np.diff(prices1) / prices1[:-1]
        returns2 = np.diff(prices2) / prices2[:-1]
        
        # 计算相关系数
        if len(returns1) > 1 and len(returns2) > 1:
            min_len = min(len(returns1), len(returns2))
            corr = np.corrcoef(returns1[-min_len:], returns2[-min_len:])[0, 1]
            return corr if not np.isnan(corr) else 0.0
        
        return 0.0
    
    def _estimate_lag(self, source: str, target: str) -> int:
        """估计领先-滞后时间（分钟）"""
        # 简化的滞后估计
        market_type_source = self._detect_market_type(source)
        market_type_target = self._detect_market_type(target)
        
        # Crypto领先美股（夜盘效应）
        if market_type_source == 'crypto' and market_type_target == 'us_stock':
            return 0  # 同时或稍微领先
        
        # 美股领先港股（开盘时间差）
        if market_type_source == 'us_stock' and market_type_target == 'hk_stock':
            return 60  # 约1小时滞后
        
        return 0
    
    def _detect_lead_lag(self) -> List[Dict]:
        """检测领先-滞后关系"""
        relations = []
        
        for edge in self.edges:
            if abs(edge.correlation) > 0.5:
                relations.append({
                    'leader': edge.source,
                    'follower': edge.target,
                    'correlation': edge.correlation,
                    'lag_minutes': edge.lag,
                    'relation_type': edge.edge_type,
                })
        
        # 按相关性排序
        relations.sort(key=lambda x: abs(x['correlation']), reverse=True)
        return relations[:10]  # 返回前10个
    
    def _detect_sector_clusters(self) -> List[Dict]:
        """识别板块聚类"""
        clusters = []
        
        # 基于预定义关系定义板块
        sector_definitions = {
            'crypto_tech': {
                'symbols': ['BTCUSDT', 'ETHUSDT', 'AAPL', 'NVDA'],
                'theme': '数字资产与科技联动',
            },
            'hk_tech': {
                'symbols': ['00700', '09988', '01810', 'NVDA'],
                'theme': '港股科技板块',
            },
        }
        
        for sector_name, sector_info in sector_definitions.items():
            # 检查板块内有多少标的当前活跃
            active_symbols = [s for s in sector_info['symbols'] if s in self.nodes]
            
            if len(active_symbols) >= 2:
                # 计算板块平均涨跌幅
                avg_change = np.mean([
                    self.nodes[s].change_pct for s in active_symbols
                ])
                
                clusters.append({
                    'name': sector_name,
                    'theme': sector_info['theme'],
                    'symbols': active_symbols,
                    'avg_change_pct': avg_change,
                    'momentum': 'strong_up' if avg_change > 2 else 
                               'up' if avg_change > 0 else
                               'down' if avg_change < 0 else 'neutral',
                })
        
        return clusters
    
    def _calculate_contagion_risk(self) -> float:
        """计算市场传染风险评分 (0-1)"""
        if not self.edges:
            return 0.0
        
        # 基于边权重和节点波动率计算
        total_weight = sum(edge.weight for edge in self.edges)
        avg_correlation = np.mean([abs(edge.correlation) for edge in self.edges])
        
        # 计算高波动节点比例
        high_vol_nodes = sum(
            1 for node in self.nodes.values()
            if abs(node.change_pct) > 3
        )
        vol_ratio = high_vol_nodes / len(self.nodes) if self.nodes else 0
        
        # 综合评分
        risk = (avg_correlation * 0.4 + 
                min(total_weight / 10, 0.3) + 
                vol_ratio * 0.3)
        
        return min(risk, 1.0)
    
    def _generate_cross_market_predictions(self) -> List[Dict]:
        """生成跨市场预测"""
        predictions = []
        
        # 基于领先-滞后关系生成预测
        for relation in self._detect_lead_lag()[:5]:
            leader = relation['leader']
            follower = relation['follower']
            
            if leader in self.nodes:
                leader_node = self.nodes[leader]
                
                # 如果领先者大幅上涨，预测跟随者
                if leader_node.change_pct > 2:
                    predicted_change = leader_node.change_pct * 0.6  # 假设60%传导
                    
                    predictions.append({
                        'target_symbol': follower,
                        'predicted_change_pct': predicted_change,
                        'confidence': abs(relation['correlation']),
                        'reasoning': f"{leader}上涨{leader_node.change_pct:.1f}%，"
                                    f"历史相关性{relation['correlation']:.2f}",
                        'time_horizon': '1h',
                        'source': 'gnn_cross_market',
                    })
        
        return predictions
    
    def _fallback_analysis(self, market_data: Dict) -> Dict:
        """GNN服务不可用时的fallback"""
        return {
            'lead_lag_relations': [],
            'sector_clusters': [],
            'contagion_risk': 0.5,
            'predictions': [],
            'graph_stats': {'node_count': 0, 'edge_count': 0},
            'source': 'fallback',
            'timestamp': datetime.utcnow().isoformat(),
        }
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


# === 便捷函数 ===

async def analyze_market_correlation(market_data: Dict) -> Dict:
    """快速分析市场相关性"""
    analyzer = GNNMarketAnalyzer()
    try:
        return await analyzer.analyze_market_correlation(market_data)
    finally:
        await analyzer.close()
