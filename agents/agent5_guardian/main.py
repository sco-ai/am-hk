"""
Agent 5: RiskGuardian - 三层风控体系
风控守卫者 - 硬规则 + 动态规则 + 异常检测
"""
import asyncio
import logging
import json
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, time
from dataclasses import dataclass, field
from enum import Enum

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from core.kafka import MessageBus, AgentConsumer
from core.models import TradeDecision, Signal, ActionType
from core.utils import generate_msg_id, generate_timestamp, setup_logging

logger = setup_logging("agent5_guardian")


class RiskStatus(str, Enum):
    """风控审批状态"""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"  # 参数被调整


class MarketRegime(str, Enum):
    """市场环境状态"""
    HIGH_VOLATILITY = "high_volatility"  # 高波动
    STRONG_TREND = "strong_trend"        # 强趋势
    CHOPPY = "choppy"                    # 震荡
    NORMAL = "normal"                    # 正常


@dataclass
class HardRuleResult:
    """硬规则检查结果"""
    rule_name: str
    passed: bool
    value: float
    limit: float
    message: str


@dataclass
class DynamicRuleResult:
    """动态规则检查结果"""
    rule_name: str
    passed: bool
    position_limit: float
    sl_adjustment: float
    message: str


@dataclass
class AnomalyResult:
    """异常检测结果"""
    anomaly_score: float
    is_anomaly: bool
    anomaly_features: List[str]
    confidence: float


@dataclass
class RiskCheckSummary:
    """风控检查汇总"""
    hard_rules_passed: bool
    dynamic_rules_passed: bool
    anomaly_passed: bool
    risk_score: float
    warnings: List[str]
    adjusted_position: float
    adjusted_sl: float
    adjusted_tp: float


class HardRulesLayer:
    """
    Layer 1: 硬规则层 - 绝对限制
    不可逾越的风控底线
    """
    
    def __init__(self):
        # 账户级别的绝对限制
        self.max_daily_loss_pct = 0.02      # 单日最大亏损 ≤ 账户2%
        self.max_single_loss_pct = 0.005    # 单笔最大亏损 ≤ 账户0.5%
        self.max_positions = 10             # 最大持仓数 ≤ 10只
        self.max_leverage = 2.0             # 杠杆上限：2x
        
        # 禁止交易时段 (财报前30分钟)
        self.earnings_blackout_mins = 30
        self.earnings_calendar: Dict[str, datetime] = {}
        
        # 状态追踪
        self.daily_pnl = 0.0
        self.daily_loss = 0.0
        self.positions_count = 0
        self.today_date = datetime.now().date()
        
        logger.info("[HardRulesLayer] 硬规则层初始化完成")
    
    def check(self, decision: TradeDecision, account_value: float = 1000000.0) -> Tuple[bool, List[HardRuleResult]]:
        """
        执行硬规则检查
        
        Returns:
            (是否通过, 详细结果列表)
        """
        results = []
        
        # 重置每日统计
        current_date = datetime.now().date()
        if current_date != self.today_date:
            self.daily_pnl = 0.0
            self.daily_loss = 0.0
            self.today_date = current_date
        
        # 1. 单日亏损限制检查
        daily_loss_limit = account_value * self.max_daily_loss_pct
        daily_loss_check = HardRuleResult(
            rule_name="daily_loss_limit",
            passed=abs(self.daily_loss) < daily_loss_limit,
            value=abs(self.daily_loss),
            limit=daily_loss_limit,
            message=f"单日亏损: {abs(self.daily_loss):.2f} / 限制: {daily_loss_limit:.2f}"
        )
        results.append(daily_loss_check)
        
        # 2. 单笔亏损限制检查
        # 估算单笔潜在亏损 = 仓位 * 止损幅度
        position_value = decision.position_size * account_value
        potential_loss = position_value * decision.stop_loss
        single_loss_limit = account_value * self.max_single_loss_pct
        
        single_loss_check = HardRuleResult(
            rule_name="single_loss_limit",
            passed=potential_loss <= single_loss_limit,
            value=potential_loss,
            limit=single_loss_limit,
            message=f"单笔潜在亏损: {potential_loss:.2f} / 限制: {single_loss_limit:.2f}"
        )
        results.append(single_loss_check)
        
        # 3. 持仓数量限制
        positions_check = HardRuleResult(
            rule_name="max_positions",
            passed=self.positions_count < self.max_positions,
            value=float(self.positions_count),
            limit=float(self.max_positions),
            message=f"当前持仓: {self.positions_count} / 限制: {self.max_positions}"
        )
        results.append(positions_check)
        
        # 4. 杠杆限制
        leverage_check = HardRuleResult(
            rule_name="max_leverage",
            passed=decision.position_size <= self.max_leverage,
            value=decision.position_size,
            limit=self.max_leverage,
            message=f"当前杠杆: {decision.position_size:.2f}x / 限制: {self.max_leverage}x"
        )
        results.append(leverage_check)
        
        # 5. 财报禁止时段检查
        symbol = decision.signal.symbol
        is_earnings_time = self._check_earnings_time(symbol)
        earnings_check = HardRuleResult(
            rule_name="earnings_blackout",
            passed=not is_earnings_time,
            value=1.0 if is_earnings_time else 0.0,
            limit=0.0,
            message="财报发布前30分钟禁止交易" if is_earnings_time else "不在财报禁止时段"
        )
        results.append(earnings_check)
        
        # 所有硬规则必须通过
        all_passed = all(r.passed for r in results)
        
        return all_passed, results
    
    def _check_earnings_time(self, symbol: str) -> bool:
        """检查是否在财报禁止时段"""
        if symbol not in self.earnings_calendar:
            return False
        
        earnings_time = self.earnings_calendar[symbol]
        now = datetime.now()
        time_diff = (earnings_time - now).total_seconds() / 60  # 分钟
        
        # 财报前30分钟内禁止交易
        return 0 < time_diff <= self.earnings_blackout_mins
    
    def update_position_count(self, count: int):
        """更新持仓数量"""
        self.positions_count = count
    
    def update_daily_pnl(self, pnl: float):
        """更新当日盈亏"""
        self.daily_pnl += pnl
        if pnl < 0:
            self.daily_loss += pnl
    
    def add_earnings_event(self, symbol: str, earnings_time: datetime):
        """添加财报事件"""
        self.earnings_calendar[symbol] = earnings_time


class DynamicRulesLayer:
    """
    Layer 2: 动态规则层 - 自适应风控
    根据市场环境动态调整参数
    """
    
    def __init__(self):
        # 市场环境判定阈值
        self.volatility_threshold_high = 0.03    # 3%日波动视为高波动
        self.trend_strength_threshold = 0.02     # 2%趋势强度
        
        # 动态规则表
        self.regime_configs = {
            MarketRegime.HIGH_VOLATILITY: {
                "position_limit": 0.5,      # 仓位限制50%
                "sl_tighten": 0.20,         # 止损收紧20%
                "tp_loosen": -0.10,         # 止盈也收紧
                "risk_multiplier": 1.5,     # 风险权重提升
            },
            MarketRegime.STRONG_TREND: {
                "position_limit": 1.0,      # 仓位限制100%（不限制）
                "sl_tighten": -0.10,        # 止损放宽10%（负值表示放宽）
                "tp_loosen": 0.10,          # 止盈放宽10%
                "risk_multiplier": 0.8,     # 风险权重降低
            },
            MarketRegime.CHOPPY: {
                "position_limit": 0.3,      # 仓位限制30%
                "sl_tighten": 0.30,         # 止损收紧30%
                "tp_loosen": -0.20,         # 止盈收紧
                "risk_multiplier": 1.8,     # 风险权重大幅提升
            },
            MarketRegime.NORMAL: {
                "position_limit": 1.0,      # 无限制
                "sl_tighten": 0.0,          # 不变
                "tp_loosen": 0.0,
                "risk_multiplier": 1.0,
            }
        }
        
        # 当前市场环境
        self.current_regime = MarketRegime.NORMAL
        
        # 市场数据缓存（用于判定市场环境）
        self.price_history: Dict[str, List[float]] = {}
        self.volume_history: Dict[str, List[float]] = {}
        
        logger.info("[DynamicRulesLayer] 动态规则层初始化完成")
    
    def detect_market_regime(self, symbol: str, factors: Dict[str, float]) -> MarketRegime:
        """
        检测当前市场环境
        
        基于波动率和趋势强度判断
        """
        # 从factors获取关键指标
        volatility = factors.get("volatility_5m", 0.01)
        volatility_20d = factors.get("volatility_20d", 0.02)
        adx = factors.get("adx", 25)  # 平均趋向指数
        price_momentum = factors.get("mom_5m", 0)
        
        # 标准化波动率（相对20日均值）
        vol_ratio = volatility / volatility_20d if volatility_20d > 0 else 1.0
        
        # 判断逻辑
        if vol_ratio > 1.5 or volatility > self.volatility_threshold_high:
            # 高波动环境
            self.current_regime = MarketRegime.HIGH_VOLATILITY
        elif adx > 40 and abs(price_momentum) > 1.0:
            # 强趋势环境
            self.current_regime = MarketRegime.STRONG_TREND
        elif adx < 20 and vol_ratio < 0.8:
            # 震荡环境（低ADX + 低波动）
            self.current_regime = MarketRegime.CHOPPY
        else:
            self.current_regime = MarketRegime.NORMAL
        
        return self.current_regime
    
    def apply_rules(self, decision: TradeDecision, 
                   factors: Dict[str, float]) -> Tuple[bool, List[DynamicRuleResult], Dict]:
        """
        应用动态规则
        
        Returns:
            (是否通过, 详细结果列表, 调整参数)
        """
        # 检测市场环境
        regime = self.detect_market_regime(decision.signal.symbol, factors)
        config = self.regime_configs[regime]
        
        results = []
        adjustments = {
            "position_limit": config["position_limit"],
            "sl_adjustment": config["sl_tighten"],
            "tp_adjustment": config["tp_loosen"],
            "risk_multiplier": config["risk_multiplier"],
            "regime": regime.value,
        }
        
        # 1. 仓位限制检查
        original_position = decision.position_size
        max_allowed = original_position * config["position_limit"]
        position_passed = original_position <= max_allowed or config["position_limit"] >= 1.0
        
        position_check = DynamicRuleResult(
            rule_name="dynamic_position_limit",
            passed=True,  # 动态规则允许调整，不直接拒绝
            position_limit=config["position_limit"],
            sl_adjustment=config["sl_tighten"],
            message=f"市场环境: {regime.value}, 仓位限制: {config['position_limit']:.0%}, "
                   f"建议仓位: {max_allowed:.2%} (原: {original_position:.2%})"
        )
        results.append(position_check)
        
        # 2. 止损止盈调整
        sl_check = DynamicRuleResult(
            rule_name="dynamic_stop_adjustment",
            passed=True,
            position_limit=config["position_limit"],
            sl_adjustment=config["sl_tighten"],
            message=f"止损调整: {'收紧' if config['sl_tighten'] > 0 else '放宽'} "
                   f"{abs(config['sl_tighten']):.0%}, 止盈调整: "
                   f"{'放宽' if config['tp_loosen'] > 0 else '收紧'} {abs(config['tp_loosen']):.0%}"
        )
        results.append(sl_check)
        
        # 动态规则通常不直接拒绝，而是提供调整建议
        return True, results, adjustments
    
    def adjust_position_size(self, original_size: float, regime: MarketRegime) -> float:
        """根据市场环境调整仓位"""
        limit = self.regime_configs[regime]["position_limit"]
        return min(original_size, original_size * limit) if limit < 1.0 else original_size
    
    def adjust_stops(self, original_sl: float, original_tp: float, 
                    regime: MarketRegime) -> Tuple[float, float]:
        """根据市场环境调整止损止盈"""
        config = self.regime_configs[regime]
        
        # 调整止损
        sl_adjust = config["sl_tighten"]
        if sl_adjust > 0:
            adjusted_sl = original_sl * (1 + sl_adjust)  # 收紧：止损距离变大
        else:
            adjusted_sl = original_sl * (1 + sl_adjust)  # 放宽：止损距离变小
        
        # 调整止盈
        tp_adjust = config["tp_loosen"]
        if tp_adjust > 0:
            adjusted_tp = original_tp * (1 + tp_adjust)  # 放宽
        else:
            adjusted_tp = original_tp * (1 + tp_adjust)  # 收紧
        
        return adjusted_sl, adjusted_tp


class AnomalyDetectionLayer:
    """
    Layer 3: 异常检测层 - Isolation Forest
    检测价格、成交量、因子的异常模式
    """
    
    def __init__(self, contamination: float = 0.05):
        self.contamination = contamination  # 预期异常比例
        self.model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
            max_samples="auto"
        )
        self.scaler = StandardScaler()
        self.is_fitted = False
        
        # 历史数据缓存（用于训练）
        self.feature_history: List[List[float]] = []
        self.max_history = 1000
        
        # 特征名称（用于解释）
        self.feature_names = [
            "price_change_rate",     # 价格变化率
            "volume_surge",          # 成交量激增
            "volatility_spike",      # 波动率跳升
            "rsi_deviation",         # RSI偏离
            "macd_anomaly",          # MACD异常
            "spread_anomaly",        # 价差异常
            "momentum_divergence",   # 动量背离
            "factor_zscore",         # 因子Z分数
        ]
        
        logger.info("[AnomalyDetectionLayer] 异常检测层初始化完成")
    
    def extract_features(self, decision: TradeDecision, 
                        factors: Dict[str, float]) -> np.ndarray:
        """从决策和因子中提取特征向量"""
        features = [
            # 价格变化率
            abs(factors.get("mom_5m", 0)) / 100,
            
            # 成交量激增 (相对于均值)
            max(0, factors.get("volume_ma_ratio", 1) - 1),
            
            # 波动率跳升
            factors.get("volatility_5m", 0.01) / max(factors.get("volatility_20d", 0.02), 0.001),
            
            # RSI偏离 (距离50的距离)
            abs(factors.get("rsi", 50) - 50) / 50,
            
            # MACD异常 (归一化)
            abs(factors.get("macd", 0)) / max(abs(factors.get("macd_signal", 0.01)), 0.01),
            
            # 价差异常
            abs(factors.get("spread", 0)) / max(factors.get("price", 1), 1),
            
            # 动量背离
            abs(factors.get("momentum_divergence", 0)),
            
            # 信号置信度异常 (过高或过低的置信度都可能是异常)
            abs(decision.signal.confidence - 0.5) * 2,
        ]
        
        return np.array(features).reshape(1, -1)
    
    def fit(self, features: List[List[float]]):
        """训练Isolation Forest模型"""
        if len(features) < 100:
            logger.warning(f"[AnomalyDetectionLayer] 训练数据不足: {len(features)} < 100")
            return
        
        X = np.array(features)
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self.is_fitted = True
        
        logger.info(f"[AnomalyDetectionLayer] 模型训练完成，使用 {len(features)} 条记录")
    
    def detect(self, decision: TradeDecision, 
              factors: Dict[str, float]) -> AnomalyResult:
        """
        执行异常检测
        
        Returns:
            AnomalyResult: 异常检测结果
        """
        # 提取特征
        features = self.extract_features(decision, factors)
        
        # 添加到历史记录
        self.feature_history.append(features[0].tolist())
        if len(self.feature_history) > self.max_history:
            self.feature_history.pop(0)
        
        # 如果数据足够，重新训练模型
        if len(self.feature_history) >= 100 and len(self.feature_history) % 50 == 0:
            self.fit(self.feature_history)
        
        # 执行检测
        if not self.is_fitted:
            # 模型未训练时使用简单规则
            return self._rule_based_detection(features[0])
        
        # 使用Isolation Forest
        features_scaled = self.scaler.transform(features)
        anomaly_score = -self.model.score_samples(features_scaled)[0]  # 转换为异常分数
        is_anomaly = self.model.predict(features_scaled)[0] == -1
        
        # 识别异常特征
        anomaly_features = self._identify_anomaly_features(features[0])
        
        return AnomalyResult(
            anomaly_score=float(anomaly_score),
            is_anomaly=is_anomaly,
            anomaly_features=anomaly_features,
            confidence=min(1.0, anomaly_score * 2)
        )
    
    def _rule_based_detection(self, features: np.ndarray) -> AnomalyResult:
        """基于规则的异常检测（冷启动）"""
        # 简单规则：任何特征超过阈值视为异常
        thresholds = [0.05, 2.0, 2.0, 0.8, 3.0, 0.01, 0.5, 0.8]
        
        anomaly_features = []
        for i, (feat, thresh) in enumerate(zip(features, thresholds)):
            if abs(feat) > thresh:
                anomaly_features.append(self.feature_names[i])
        
        score = len(anomaly_features) / len(features)
        
        return AnomalyResult(
            anomaly_score=score,
            is_anomaly=score > 0.3,
            anomaly_features=anomaly_features,
            confidence=score
        )
    
    def _identify_anomaly_features(self, features: np.ndarray) -> List[str]:
        """识别哪些特征导致了异常"""
        # 计算每个特征的偏离程度（相对于历史均值）
        if len(self.feature_history) < 10:
            return []
        
        history = np.array(self.feature_history[-100:])
        means = np.mean(history, axis=0)
        stds = np.std(history, axis=0) + 1e-6
        
        z_scores = np.abs((features - means) / stds)
        
        anomaly_features = []
        for i, z_score in enumerate(z_scores):
            if z_score > 2.0:  # 超过2个标准差
                anomaly_features.append(f"{self.feature_names[i]}(z={z_score:.2f})")
        
        return anomaly_features


class RiskGuardian:
    """
    Agent 5: RiskGuardian - 三层风控审批中心
    
    架构:
    1. Layer 1: Hard Rules - 绝对限制，不可逾越
    2. Layer 2: Dynamic Rules - 自适应调整
    3. Layer 3: Anomaly Detection - Isolation Forest
    """
    
    def __init__(self):
        self.agent_name = "agent5_guardian"
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-trading-decisions"]  # 从Agent 4接收决策
        )
        
        # 三层风控
        self.hard_rules = HardRulesLayer()
        self.dynamic_rules = DynamicRulesLayer()
        self.anomaly_detector = AnomalyDetectionLayer()
        
        # 账户状态
        self.account_value = 1000000.0  # 默认100万
        self.positions: Dict[str, Dict] = {}
        
        # 审批统计
        self.stats = {
            "total_reviewed": 0,
            "approved": 0,
            "rejected": 0,
            "modified": 0,
        }
        
        self.running = False
        logger.info(f"[{self.agent_name}] RiskGuardian 初始化完成")
    
    async def start(self):
        """启动风控中心"""
        self.running = True
        logger.info(f"[{self.agent_name}] 风控中心启动")
        
        # 注册消息处理器 - 支持多种消息类型
        self.consumer.register_handler("trade_decision", self._on_decision)
        self.consumer.register_handler("decision", self._on_decision)
        self.consumer.register_handler("trading_decision", self._on_decision)
        
        # 发布状态
        self.bus.publish_status({
            "state": "running",
            "layers": ["hard_rules", "dynamic_rules", "anomaly_detection"],
            "stats": self.stats,
        })
        
        try:
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
        """停止风控中心"""
        logger.info(f"[{self.agent_name}] 正在停止...")
        self.running = False
        self.consumer.stop()
        
        self.bus.publish_status({"state": "stopped"})
        self.bus.flush()
        self.bus.close()
        
        logger.info(f"[{self.agent_name}] 已停止")
    
    def _on_decision(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理交易决策 - 在后台线程中运行"""
        import threading
        
        def run_async_in_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._process_decision_async(key, value, headers))
                loop.close()
            except Exception as e:
                logger.error(f"DEBUG: Error in thread processing: {e}", exc_info=True)
        
        thread = threading.Thread(target=run_async_in_thread)
        thread.daemon = True
        thread.start()
    
    async def _process_decision_async(self, key: str, value: Dict, headers: Optional[Dict]):
        """异步处理交易决策 - 三层风控顺序执行"""
        try:
            payload = value.get("payload", {})
            decision_data = payload.get("decision", {})
            factors = payload.get("factors", {})
            
            decision = TradeDecision(**decision_data)
            symbol = decision.signal.symbol
            
            logger.info(f"[{self.agent_name}] 审查决策: {symbol} {decision.signal.action.value}")
            
            # ===== Layer 1: 硬规则检查 =====
            hard_passed, hard_results = self.hard_rules.check(decision, self.account_value)
            
            if not hard_passed:
                # 硬规则未通过，直接拒绝
                failed_rules = [r.rule_name for r in hard_results if not r.passed]
                self._reject_decision(decision, f"硬规则未通过: {', '.join(failed_rules)}", 
                                     hard_results, [], None)
                return
            
            # ===== Layer 2: 动态规则检查 =====
            dynamic_passed, dynamic_results, adjustments = self.dynamic_rules.apply_rules(
                decision, factors
            )
            
            # ===== Layer 3: 异常检测 =====
            anomaly_result = self.anomaly_detector.detect(decision, factors)
            
            # 综合决策
            final_result = self._make_final_decision(
                decision, hard_results, dynamic_results, 
                anomaly_result, adjustments
            )
            
            # 发布结果
            if final_result.risk_status == RiskStatus.REJECTED:
                self._reject_decision(decision, final_result.message, 
                                     hard_results, dynamic_results, anomaly_result,
                                     final_result.adjusted_params)
            else:
                self._approve_decision(decision, final_result,
                                      hard_results, dynamic_results, anomaly_result)
            
            # 更新统计
            self.stats["total_reviewed"] += 1
            if final_result.risk_status == RiskStatus.APPROVED:
                self.stats["approved"] += 1
            elif final_result.risk_status == RiskStatus.REJECTED:
                self.stats["rejected"] += 1
            else:
                self.stats["modified"] += 1
        
        except Exception as e:
            logger.error(f"[{self.agent_name}] 处理决策出错: {e}", exc_info=True)
    
    def _make_final_decision(self, decision: TradeDecision,
                            hard_results: List[HardRuleResult],
                            dynamic_results: List[DynamicRuleResult],
                            anomaly_result: AnomalyResult,
                            adjustments: Dict) -> 'FinalDecisionResult':
        """
        综合三层风控结果做出最终决策
        """
        warnings = []
        
        # 计算风险评分
        hard_score = sum(1 for r in hard_results if r.passed) / len(hard_results)
        anomaly_score = 1.0 - min(1.0, anomaly_result.anomaly_score)
        confidence_score = decision.signal.confidence
        
        # 加权风险评分
        risk_score = (hard_score * 0.4 + 
                     anomaly_score * 0.4 + 
                     confidence_score * 0.2)
        
        # 应用动态调整
        regime = MarketRegime(adjustments.get("regime", "normal"))
        adjusted_position = self.dynamic_rules.adjust_position_size(
            decision.position_size, regime
        )
        adjusted_sl, adjusted_tp = self.dynamic_rules.adjust_stops(
            decision.stop_loss, decision.take_profit, regime
        )
        
        # 异常检测拒绝逻辑
        if anomaly_result.is_anomaly and anomaly_result.anomaly_score > 0.7:
            return FinalDecisionResult(
                risk_status=RiskStatus.REJECTED,
                risk_score=risk_score,
                message=f"异常检测触发: {', '.join(anomaly_result.anomaly_features[:3])}",
                adjusted_params={
                    "position": adjusted_position,
                    "sl": adjusted_sl,
                    "tp": adjusted_tp,
                }
            )
        
        # 参数调整
        params_modified = (adjusted_position != decision.position_size or 
                          adjusted_sl != decision.stop_loss or
                          adjusted_tp != decision.take_profit)
        
        status = RiskStatus.MODIFIED if params_modified else RiskStatus.APPROVED
        
        if anomaly_result.anomaly_features:
            warnings.append(f"检测到异常特征: {', '.join(anomaly_result.anomaly_features[:2])}")
        
        return FinalDecisionResult(
            risk_status=status,
            risk_score=risk_score,
            message="审批通过" if status == RiskStatus.APPROVED else "参数已调整",
            adjusted_params={
                "position": adjusted_position,
                "sl": adjusted_sl,
                "tp": adjusted_tp,
            },
            warnings=warnings
        )
    
    def _approve_decision(self, decision: TradeDecision, 
                         result: 'FinalDecisionResult',
                         hard_results: List[HardRuleResult],
                         dynamic_results: List[DynamicRuleResult],
                         anomaly_result: AnomalyResult):
        """发布审批通过的决策"""
        symbol = decision.signal.symbol
        params = result.adjusted_params
        
        output = {
            "symbol": symbol,
            "original_decision": decision.signal.action.value,
            "risk_status": result.risk_status.value,
            "risk_score": round(result.risk_score, 4),
            "approved_position": round(params["position"], 4),
            "adjusted_sl": round(params["sl"], 6),
            "adjusted_tp": round(params["tp"], 6),
            "risk_checks": {
                "hard_rules": "PASS",
                "dynamic_rules": "PASS",
                "anomaly_detection": "PASS" if not anomaly_result.is_anomaly else "WARNING",
            },
            "warnings": result.warnings,
            "details": {
                "hard_rules": [{"name": r.rule_name, "passed": r.passed} for r in hard_results],
                "dynamic_rules": [{"name": r.rule_name, "passed": r.passed} for r in dynamic_results],
                "anomaly_score": round(anomaly_result.anomaly_score, 4),
            },
            "timestamp": generate_timestamp().isoformat(),
        }
        
        # 发布到Kafka
        message = {
            "msg_id": generate_msg_id(),
            "msg_type": "risk_approved_trade",
            "source_agent": self.agent_name,
            "target_agent": "executor",
            "timestamp": generate_timestamp().isoformat(),
            "priority": 1,
            "payload": output,
        }
        
        self.bus.send("am-hk-risk-approved-trades", symbol, message)
        self.bus.flush()
        
        logger.info(f"[{self.agent_name}] ✅ 审批通过: {symbol} | "
                   f"仓位: {params['position']:.2%} | 风险分: {result.risk_score:.2f}")
    
    def _reject_decision(self, decision: TradeDecision, reason: str,
                        hard_results: List[HardRuleResult],
                        dynamic_results: List[DynamicRuleResult],
                        anomaly_result: Optional[AnomalyResult],
                        adjusted_params: Optional[Dict] = None):
        """发布拒绝的决策"""
        symbol = decision.signal.symbol
        
        output = {
            "symbol": symbol,
            "original_decision": decision.signal.action.value,
            "risk_status": RiskStatus.REJECTED.value,
            "risk_score": 0.0,
            "rejection_reason": reason,
            "risk_checks": {
                "hard_rules": "PASS" if all(r.passed for r in hard_results) else "FAIL",
                "dynamic_rules": "PASS" if dynamic_results and all(r.passed for r in dynamic_results) else "SKIP",
                "anomaly_detection": "FAIL" if anomaly_result and anomaly_result.is_anomaly else "PASS",
            },
            "warnings": [reason],
            "timestamp": generate_timestamp().isoformat(),
        }
        
        # 发布到反馈队列
        message = {
            "msg_id": generate_msg_id(),
            "msg_type": "risk_rejected_trade",
            "source_agent": self.agent_name,
            "target_agent": "agent6_learning",
            "timestamp": generate_timestamp().isoformat(),
            "priority": 3,
            "payload": output,
        }
        
        self.bus.publish_feedback(message)
        self.bus.flush()
        
        logger.warning(f"[{self.agent_name}] ❌ 审批拒绝: {symbol} | 原因: {reason}")


@dataclass
class FinalDecisionResult:
    """最终决策结果"""
    risk_status: RiskStatus
    risk_score: float
    message: str
    adjusted_params: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


if __name__ == "__main__":
    guardian = RiskGuardian()
    asyncio.run(guardian.start())
