"""
组合风控管理器 - Risk Manager
组合级别的风险管理系统
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger("risk_manager")


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskCheckResult:
    """风险检查结果"""
    passed: bool
    risk_level: RiskLevel
    violations: List[str]
    warnings: List[str]
    
    # 指标
    total_exposure: float
    daily_pnl: float
    max_drawdown: float
    var_95: float  # 95% VaR
    
    # 建议
    recommended_action: str
    position_adjustments: Dict[str, float]


class RiskManager:
    """
    组合风控管理器
    
    管理组合级别的风险:
    - 总敞口限制
    - 单日亏损限制
    - 最大回撤限制
    - 相关性风险
    - VaR监控
    """
    
    def __init__(
        self,
        max_total_exposure: float = 1.0,      # 最大总敞口100%
        max_single_position: float = 0.3,      # 最大单笔仓位30%
        max_daily_loss_pct: float = 0.05,      # 最大日亏损5%
        max_drawdown_pct: float = 0.15,        # 最大回撤15%
        var_limit_pct: float = 0.03,           # VaR限制3%
        max_correlation: float = 0.8           # 最大相关性
    ):
        self.max_total_exposure = max_total_exposure
        self.max_single_position = max_single_position
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.var_limit_pct = var_limit_pct
        self.max_correlation = max_correlation
        
        # 状态跟踪
        self.daily_pnl: float = 0.0
        self.peak_value: float = 0.0
        self.current_drawdown: float = 0.0
        self.daily_starting_value: float = 0.0
        
        # 持仓
        self.positions: Dict[str, Dict] = {}
        self.pnl_history: List[float] = []
        self.last_check: Optional[datetime] = None
        
        # 风险日志
        self.risk_events: List[Dict] = []
    
    def check_risk(
        self,
        portfolio_value: float,
        positions: Dict[str, Dict],
        new_order: Optional[Dict] = None
    ) -> RiskCheckResult:
        """
        风险检查
        
        Args:
            portfolio_value: 组合总值
            positions: 当前持仓 {symbol: {size, price, value}}
            new_order: 新订单 (可选)
            
        Returns:
            RiskCheckResult
        """
        violations = []
        warnings = []
        position_adjustments = {}
        
        self.positions = positions
        
        # 1. 总敞口检查
        total_exposure = self._calculate_total_exposure(positions)
        if total_exposure > self.max_total_exposure:
            violations.append(f"总敞口超标: {total_exposure:.2%} > {self.max_total_exposure:.2%}")
        elif total_exposure > self.max_total_exposure * 0.9:
            warnings.append(f"总敞口接近上限: {total_exposure:.2%}")
        
        # 2. 单笔仓位检查
        for symbol, pos in positions.items():
            pos_pct = pos.get("value", 0) / portfolio_value if portfolio_value > 0 else 0
            if pos_pct > self.max_single_position:
                violations.append(f"{symbol}仓位超标: {pos_pct:.2%}")
                position_adjustments[symbol] = self.max_single_position * portfolio_value
        
        # 3. 日亏损检查
        self._update_daily_pnl(portfolio_value)
        daily_loss_pct = abs(self.daily_pnl) / self.daily_starting_value if self.daily_starting_value > 0 else 0
        if daily_loss_pct > self.max_daily_loss_pct:
            violations.append(f"日亏损超标: {daily_loss_pct:.2%}")
        elif daily_loss_pct > self.max_daily_loss_pct * 0.8:
            warnings.append(f"日亏损接近上限: {daily_loss_pct:.2%}")
        
        # 4. 回撤检查
        self._update_drawdown(portfolio_value)
        if self.current_drawdown > self.max_drawdown_pct:
            violations.append(f"回撤超标: {self.current_drawdown:.2%}")
        elif self.current_drawdown > self.max_drawdown_pct * 0.8:
            warnings.append(f"回撤接近上限: {self.current_drawdown:.2%}")
        
        # 5. VaR计算和检查
        var_95 = self._calculate_var()
        var_pct = var_95 / portfolio_value if portfolio_value > 0 else 0
        if var_pct > self.var_limit_pct:
            violations.append(f"VaR超标: {var_pct:.2%}")
        
        # 6. 相关性检查
        corr_violations = self._check_correlations(positions)
        warnings.extend(corr_violations)
        
        # 7. 新订单风险检查
        if new_order:
            new_risk = self._check_new_order_risk(positions, new_order, portfolio_value)
            if new_risk:
                violations.extend(new_risk)
        
        # 确定风险等级
        risk_level = self._determine_risk_level(violations, warnings, total_exposure)
        
        # 生成建议
        recommended_action = self._generate_recommendation(
            violations, warnings, risk_level
        )
        
        result = RiskCheckResult(
            passed=len(violations) == 0,
            risk_level=risk_level,
            violations=violations,
            warnings=warnings,
            total_exposure=total_exposure,
            daily_pnl=self.daily_pnl,
            max_drawdown=self.current_drawdown,
            var_95=var_95,
            recommended_action=recommended_action,
            position_adjustments=position_adjustments
        )
        
        # 记录风险事件
        if violations or risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            self._log_risk_event(result)
        
        self.last_check = datetime.now()
        
        return result
    
    def _calculate_total_exposure(self, positions: Dict[str, Dict]) -> float:
        """计算总敞口"""
        return sum(abs(pos.get("value", 0)) for pos in positions.values())
    
    def _update_daily_pnl(self, current_value: float):
        """更新日盈亏"""
        if self.daily_starting_value == 0:
            self.daily_starting_value = current_value
        
        self.daily_pnl = current_value - self.daily_starting_value
    
    def _update_drawdown(self, current_value: float):
        """更新回撤"""
        if current_value > self.peak_value:
            self.peak_value = current_value
        
        if self.peak_value > 0:
            self.current_drawdown = (self.peak_value - current_value) / self.peak_value
    
    def _calculate_var(self, confidence: float = 0.95) -> float:
        """计算VaR (简化版)"""
        if len(self.pnl_history) < 20:
            return 0.0
        
        returns = np.array(self.pnl_history[-20:])
        var = np.percentile(returns, (1 - confidence) * 100)
        return abs(var)
    
    def _check_correlations(self, positions: Dict[str, Dict]) -> List[str]:
        """检查相关性风险"""
        warnings = []
        symbols = list(positions.keys())
        
        # 简化版: 检查加密货币相关性
        crypto_groups = {
            "btc_eth": ["BTCUSDT", "ETHUSDT"],
            "altcoins": ["SOLUSDT", "XRPUSDT", "DOGEUSDT"],
        }
        
        for group_name, group_symbols in crypto_groups.items():
            group_positions = [s for s in symbols if any(gs in s for gs in group_symbols)]
            group_exposure = sum(
                abs(positions[s].get("value", 0)) for s in group_positions
            )
            
            if len(group_positions) > 1 and group_exposure > 0:
                warnings.append(f"{group_name}相关性风险: {len(group_positions)}个持仓")
        
        return warnings
    
    def _check_new_order_risk(
        self,
        positions: Dict[str, Dict],
        new_order: Dict,
        portfolio_value: float
    ) -> List[str]:
        """检查新订单风险"""
        violations = []
        
        symbol = new_order.get("symbol")
        order_value = new_order.get("value", 0)
        
        # 检查单笔限制
        current_value = positions.get(symbol, {}).get("value", 0)
        new_total = abs(current_value) + abs(order_value)
        new_pct = new_total / portfolio_value if portfolio_value > 0 else 0
        
        if new_pct > self.max_single_position:
            violations.append(f"新订单将超出单笔仓位限制")
        
        # 检查总敞口
        total_exposure = self._calculate_total_exposure(positions) + abs(order_value)
        if total_exposure > self.max_total_exposure * portfolio_value:
            violations.append(f"新订单将超出总敞口限制")
        
        return violations
    
    def _determine_risk_level(
        self,
        violations: List[str],
        warnings: List[str],
        total_exposure: float
    ) -> RiskLevel:
        """确定风险等级"""
        if len(violations) >= 2:
            return RiskLevel.CRITICAL
        elif len(violations) == 1:
            return RiskLevel.HIGH
        elif len(warnings) >= 2 or total_exposure > 0.8:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _generate_recommendation(
        self,
        violations: List[str],
        warnings: List[str],
        risk_level: RiskLevel
    ) -> str:
        """生成建议"""
        if risk_level == RiskLevel.CRITICAL:
            return "立即减仓,暂停新开仓"
        elif risk_level == RiskLevel.HIGH:
            return "逐步减仓,严格止损"
        elif risk_level == RiskLevel.MEDIUM:
            return "谨慎交易,监控风险"
        else:
            return "正常交易"
    
    def _log_risk_event(self, result: RiskCheckResult):
        """记录风险事件"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "risk_level": result.risk_level.value,
            "violations": result.violations,
            "warnings": result.warnings,
            "exposure": result.total_exposure,
            "drawdown": result.max_drawdown,
        }
        self.risk_events.append(event)
        
        # 日志记录
        logger.warning(f"风险事件: {event}")
    
    def reset_daily_stats(self, starting_value: float):
        """重置日统计"""
        self.daily_starting_value = starting_value
        self.daily_pnl = 0.0
    
    def record_pnl(self, pnl: float):
        """记录盈亏"""
        self.pnl_history.append(pnl)
        if len(self.pnl_history) > 100:
            self.pnl_history = self.pnl_history[-100:]
    
    def get_risk_summary(self) -> Dict:
        """获取风险摘要"""
        return {
            "current_drawdown": self.current_drawdown,
            "daily_pnl": self.daily_pnl,
            "total_exposure": self._calculate_total_exposure(self.positions),
            "risk_events_24h": len([e for e in self.risk_events 
                                   if (datetime.now() - datetime.fromisoformat(e["timestamp"])).days < 1]),
        }


# 全局实例
risk_manager = RiskManager()
