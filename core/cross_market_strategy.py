"""
多市场联动策略
基于GNN分析的跨市场套利和趋势跟踪策略
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from core.gnn_model import GNNMarketAnalyzer, analyze_market_correlation
from core.models import Signal, ActionType
from core.utils import setup_logging

logger = setup_logging("cross_market_strategy")


@dataclass
class CrossMarketOpportunity:
    """跨市场机会"""
    primary_symbol: str
    secondary_symbol: str
    opportunity_type: str  # lead_lag, arbitrage, sector_momentum
    expected_return: float
    confidence: float
    reasoning: str
    time_horizon: str


class CrossMarketStrategy:
    """
    多市场联动交易策略
    
    策略类型：
    1. 领先-滞后套利：BTC夜盘 -> 美股开盘
    2. 板块轮动：科技股 -> 港股科技ETF
    3. 避险资产联动：黄金上涨 -> BTC回调
    4. 传染效应反向交易：过度反应后的回归
    """
    
    def __init__(self):
        self.gnn_analyzer = GNNMarketAnalyzer()
        
        # 策略配置
        self.min_correlation = 0.5
        self.min_confidence = 0.6
        self.max_contagion_risk = 0.8
        
        logger.info("Cross Market Strategy initialized")
    
    async def scan_opportunities(self, market_data: Dict) -> List[CrossMarketOpportunity]:
        """
        扫描跨市场机会
        
        Args:
            market_data: 多市场实时数据
        
        Returns:
            机会列表
        """
        opportunities = []
        
        # 1. GNN分析
        gnn_result = await analyze_market_correlation(market_data)
        
        # 2. 领先-滞后套利
        lead_lag_ops = self._find_lead_lag_opportunities(
            gnn_result.get('lead_lag_relations', []),
            market_data
        )
        opportunities.extend(lead_lag_ops)
        
        # 3. 板块轮动
        sector_ops = self._find_sector_rotation_opportunities(
            gnn_result.get('sector_clusters', []),
            market_data
        )
        opportunities.extend(sector_ops)
        
        # 4. 传染效应反向
        contagion_risk = gnn_result.get('contagion_risk', 0)
        if contagion_risk > 0.7:
            reverse_ops = self._find_reverse_opportunities(market_data, contagion_risk)
            opportunities.extend(reverse_ops)
        
        # 5. GNN预测机会
        gnn_predictions = gnn_result.get('predictions', [])
        prediction_ops = self._convert_predictions_to_opportunities(gnn_predictions)
        opportunities.extend(prediction_ops)
        
        # 按预期收益排序
        opportunities.sort(key=lambda x: x.expected_return, reverse=True)
        
        logger.info(f"Found {len(opportunities)} cross-market opportunities")
        return opportunities
    
    def _find_lead_lag_opportunities(self, 
                                     lead_lag_relations: List[Dict],
                                     market_data: Dict) -> List[CrossMarketOpportunity]:
        """寻找领先-滞后套利机会"""
        opportunities = []
        
        for relation in lead_lag_relations:
            leader = relation['leader']
            follower = relation['follower']
            correlation = relation['correlation']
            lag = relation['lag_minutes']
            
            # 检查相关性是否足够强
            if abs(correlation) < self.min_correlation:
                continue
            
            # 获取领先者数据
            leader_data = market_data.get(leader, {})
            leader_change = leader_data.get('change_pct', 0)
            
            # BTC夜盘大幅上涨 -> 预测美股科技股高开
            if leader == 'BTCUSDT' and leader_change > 3:
                if 'AAPL' in follower or 'NVDA' in follower:
                    opportunities.append(CrossMarketOpportunity(
                        primary_symbol=leader,
                        secondary_symbol=follower,
                        opportunity_type='lead_lag',
                        expected_return=leader_change * 0.5,
                        confidence=abs(correlation),
                        reasoning=f"BTC夜盘上涨{leader_change:.1f}%，"
                                 f"历史相关性{correlation:.2f}，"
                                 f"预测{follower}开盘跟随上涨",
                        time_horizon='30min'
                    ))
            
            # 美股收盘大涨 -> 预测港股高开
            if leader in ['AAPL', 'NVDA'] and leader_change > 2:
                if follower in ['00700', '09988']:  # 腾讯、阿里
                    opportunities.append(CrossMarketOpportunity(
                        primary_symbol=leader,
                        secondary_symbol=follower,
                        opportunity_type='lead_lag',
                        expected_return=leader_change * 0.4,
                        confidence=abs(correlation),
                        reasoning=f"{leader}美股上涨{leader_change:.1f}%，"
                                 f"预测港股{follower}开盘跟随",
                        time_horizon='1h'
                    ))
        
        return opportunities
    
    def _find_sector_rotation_opportunities(self,
                                           sector_clusters: List[Dict],
                                           market_data: Dict) -> List[CrossMarketOpportunity]:
        """寻找板块轮动机会"""
        opportunities = []
        
        for cluster in sector_clusters:
            momentum = cluster.get('momentum', 'neutral')
            avg_change = cluster.get('avg_change_pct', 0)
            symbols = cluster.get('symbols', [])
            
            # 强势板块内的跟随机会
            if momentum in ['strong_up', 'up'] and avg_change > 2:
                # 找到板块内涨幅落后的标的
                for symbol in symbols:
                    symbol_data = market_data.get(symbol, {})
                    symbol_change = symbol_data.get('change_pct', 0)
                    
                    if symbol_change < avg_change * 0.5:
                        opportunities.append(CrossMarketOpportunity(
                            primary_symbol=cluster.get('name', 'sector'),
                            secondary_symbol=symbol,
                            opportunity_type='sector_momentum',
                            expected_return=(avg_change - symbol_change) * 0.5,
                            confidence=0.65,
                            reasoning=f"{cluster.get('theme')}整体上涨{avg_change:.1f}%，"
                                     f"{symbol}仅上涨{symbol_change:.1f}%，"
                                     f"存在补涨空间",
                            time_horizon='2h'
                        ))
        
        return opportunities
    
    def _find_reverse_opportunities(self, 
                                   market_data: Dict,
                                   contagion_risk: float) -> List[CrossMarketOpportunity]:
        """寻找传染效应反向交易机会（过度反应后的回归）"""
        opportunities = []
        
        # 当传染风险极高时，寻找被错杀的标的
        for symbol, data in market_data.items():
            change_pct = data.get('change_pct', 0)
            
            # 大盘恐慌但基本面未变的标的
            if change_pct < -5 and contagion_risk > 0.8:
                opportunities.append(CrossMarketOpportunity(
                    primary_symbol='MARKET_PANIC',
                    secondary_symbol=symbol,
                    opportunity_type='contagion_reverse',
                    expected_return=abs(change_pct) * 0.3,
                    confidence=0.55,
                    reasoning=f"市场恐慌（传染风险{contagion_risk:.1%}），"
                             f"{symbol}超跌{change_pct:.1f}%，"
                             f"预期情绪修复后反弹",
                    time_horizon='4h'
                ))
        
        return opportunities
    
    def _convert_predictions_to_opportunities(self,
                                             predictions: List[Dict]) -> List[CrossMarketOpportunity]:
        """将GNN预测转换为交易机会"""
        opportunities = []
        
        for pred in predictions:
            confidence = pred.get('confidence', 0)
            
            if confidence < self.min_confidence:
                continue
            
            opportunities.append(CrossMarketOpportunity(
                primary_symbol=pred.get('source_symbol', 'gnn'),
                secondary_symbol=pred.get('target_symbol', ''),
                opportunity_type='gnn_prediction',
                expected_return=pred.get('predicted_change_pct', 0),
                confidence=confidence,
                reasoning=pred.get('reasoning', ''),
                time_horizon=pred.get('time_horizon', '1h')
            ))
        
        return opportunities
    
    def generate_trading_signals(self, 
                                opportunities: List[CrossMarketOpportunity]) -> List[Signal]:
        """
        将机会转换为交易信号
        
        Returns:
            Signal列表
        """
        signals = []
        
        for opp in opportunities[:3]:  # 只取前3个机会
            # 确定操作方向
            if opp.expected_return > 0:
                action = ActionType.BUY
            else:
                action = ActionType.SELL
            
            signal = Signal(
                symbol=opp.secondary_symbol,
                market=self._detect_market_type(opp.secondary_symbol),
                action=action,
                confidence=min(opp.confidence, 0.9),
                predicted_return=opp.expected_return,
                timeframe=opp.time_horizon,
                reasoning=f"[跨市场联动] {opp.opportunity_type}: {opp.reasoning}",
                agent_id='cross_market_strategy',
                timestamp=datetime.utcnow(),
                metadata={
                    'primary_symbol': opp.primary_symbol,
                    'opportunity_type': opp.opportunity_type,
                }
            )
            
            signals.append(signal)
        
        return signals
    
    def _detect_market_type(self, symbol: str) -> str:
        """检测市场类型"""
        if symbol.endswith('USDT') or symbol in ['BTC', 'ETH']:
            return 'btc'
        elif symbol.isdigit() or (len(symbol) == 5 and symbol[0] == '0'):
            return 'hk_stock'
        else:
            return 'us_stock'
    
    async def close(self):
        """关闭分析器"""
        await self.gnn_analyzer.close()


# === 便捷函数 ===

async def scan_cross_market_opportunities(market_data: Dict) -> List[Signal]:
    """
    快速扫描跨市场机会并生成信号
    
    Args:
        market_data: {
            'BTCUSDT': {'price': 65000, 'change_pct': 2.5, 'volume': 1000},
            'AAPL': {'price': 180, 'change_pct': 1.2, 'volume': 50000},
            ...
        }
    
    Returns:
        交易信号列表
    """
    strategy = CrossMarketStrategy()
    try:
        opportunities = await strategy.scan_opportunities(market_data)
        signals = strategy.generate_trading_signals(opportunities)
        return signals
    finally:
        await strategy.close()
