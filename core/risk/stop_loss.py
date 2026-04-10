"""
止损管理器 - Stop Loss Manager
管理止损逻辑和跟踪止损
"""
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class StopType(Enum):
    """止损类型"""
    FIXED = "fixed"           # 固定止损
    TRAILING = "trailing"     # 跟踪止损
    ATR_BASED = "atr_based"   # ATR动态止损
    TIME_BASED = "time_based" # 时间止损


@dataclass
class StopLossResult:
    """止损结果"""
    should_exit: bool
    exit_price: float
    stop_type: StopType
    reason: str
    pnl_pct: float
    
    # 止损信息
    stop_price: float
    initial_stop: float
    current_distance_pct: float


class StopLossManager:
    """
    止损管理器
    
    支持多种止损策略:
    - 固定百分比止损
    - 跟踪止损
    - ATR动态止损
    - 时间止损
    """
    
    def __init__(
        self,
        default_stop_pct: float = 0.02,      # 默认2%止损
        trailing_activation: float = 0.01,    # 盈利1%后启动跟踪
        trailing_distance: float = 0.015,     # 跟踪距离1.5%
        max_holding_hours: int = 48           # 最大持仓48小时
    ):
        self.default_stop_pct = default_stop_pct
        self.trailing_activation = trailing_activation
        self.trailing_distance = trailing_distance
        self.max_holding_hours = max_holding_hours
        
        # 持仓跟踪
        self.positions: Dict[str, Dict] = {}
    
    def register_position(
        self,
        symbol: str,
        entry_price: float,
        direction: str,  # "long" or "short"
        stop_type: StopType = StopType.TRAILING,
        custom_stop_pct: Optional[float] = None
    ):
        """
        注册新持仓
        
        Args:
            symbol: 交易对
            entry_price: 入场价格
            direction: 方向 (long/short)
            stop_type: 止损类型
            custom_stop_pct: 自定义止损百分比
        """
        stop_pct = custom_stop_pct or self.default_stop_pct
        
        if direction == "long":
            initial_stop = entry_price * (1 - stop_pct)
        else:
            initial_stop = entry_price * (1 + stop_pct)
        
        self.positions[symbol] = {
            "entry_price": entry_price,
            "direction": direction,
            "stop_type": stop_type,
            "initial_stop": initial_stop,
            "current_stop": initial_stop,
            "highest_price": entry_price,  # 用于跟踪止损
            "lowest_price": entry_price,
            "entry_time": datetime.now(),
            "stop_pct": stop_pct,
            "trailing_activated": False,
        }
    
    def check_stop(
        self,
        symbol: str,
        current_price: float,
        current_atr: Optional[float] = None
    ) -> StopLossResult:
        """
        检查是否触发止损
        
        Args:
            symbol: 交易对
            current_price: 当前价格
            current_atr: 当前ATR (用于ATR止损)
            
        Returns:
            StopLossResult
        """
        if symbol not in self.positions:
            return StopLossResult(
                should_exit=False,
                exit_price=current_price,
                stop_type=StopType.FIXED,
                reason="未持仓",
                pnl_pct=0.0,
                stop_price=0.0,
                initial_stop=0.0,
                current_distance_pct=0.0
            )
        
        pos = self.positions[symbol]
        direction = pos["direction"]
        entry_price = pos["entry_price"]
        
        # 计算当前盈亏
        if direction == "long":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        # 更新最高/最低价
        if direction == "long":
            pos["highest_price"] = max(pos["highest_price"], current_price)
        else:
            pos["lowest_price"] = min(pos["lowest_price"], current_price)
        
        # 根据止损类型检查
        stop_type = pos["stop_type"]
        should_exit = False
        reason = ""
        
        if stop_type == StopType.FIXED:
            should_exit, reason = self._check_fixed_stop(pos, current_price)
        
        elif stop_type == StopType.TRAILING:
            should_exit, reason = self._check_trailing_stop(pos, current_price)
        
        elif stop_type == StopType.ATR_BASED and current_atr:
            should_exit, reason = self._check_atr_stop(pos, current_price, current_atr)
        
        # 时间止损检查
        if not should_exit:
            should_exit, reason = self._check_time_stop(pos)
        
        # 计算当前止损距离
        if direction == "long":
            distance_pct = (current_price - pos["current_stop"]) / current_price
        else:
            distance_pct = (pos["current_stop"] - current_price) / current_price
        
        return StopLossResult(
            should_exit=should_exit,
            exit_price=current_price,
            stop_type=stop_type,
            reason=reason,
            pnl_pct=pnl_pct,
            stop_price=pos["current_stop"],
            initial_stop=pos["initial_stop"],
            current_distance_pct=distance_pct
        )
    
    def _check_fixed_stop(self, pos: Dict, current_price: float) -> tuple:
        """检查固定止损"""
        direction = pos["direction"]
        stop_price = pos["current_stop"]
        
        if direction == "long" and current_price <= stop_price:
            return True, f"触发固定止损(多): {stop_price:.2f}"
        elif direction == "short" and current_price >= stop_price:
            return True, f"触发固定止损(空): {stop_price:.2f}"
        
        return False, ""
    
    def _check_trailing_stop(self, pos: Dict, current_price: float) -> tuple:
        """检查跟踪止损"""
        direction = pos["direction"]
        entry_price = pos["entry_price"]
        
        if direction == "long":
            # 计算当前盈利
            profit_pct = (current_price - entry_price) / entry_price
            
            # 激活跟踪止损
            if profit_pct >= self.trailing_activation and not pos["trailing_activated"]:
                pos["trailing_activated"] = True
            
            if pos["trailing_activated"]:
                # 更新止损价
                new_stop = pos["highest_price"] * (1 - self.trailing_distance)
                if new_stop > pos["current_stop"]:
                    pos["current_stop"] = new_stop
                
                # 检查触发
                if current_price <= pos["current_stop"]:
                    return True, f"触发跟踪止损: {pos['current_stop']:.2f}"
        
        else:  # short
            profit_pct = (entry_price - current_price) / entry_price
            
            if profit_pct >= self.trailing_activation and not pos["trailing_activated"]:
                pos["trailing_activated"] = True
            
            if pos["trailing_activated"]:
                new_stop = pos["lowest_price"] * (1 + self.trailing_distance)
                if new_stop < pos["current_stop"]:
                    pos["current_stop"] = new_stop
                
                if current_price >= pos["current_stop"]:
                    return True, f"触发跟踪止损: {pos['current_stop']:.2f}"
        
        return False, ""
    
    def _check_atr_stop(
        self,
        pos: Dict,
        current_price: float,
        atr: float,
        multiplier: float = 2.0
    ) -> tuple:
        """检查ATR止损"""
        direction = pos["direction"]
        
        # 动态更新止损
        if direction == "long":
            new_stop = current_price - atr * multiplier
            if new_stop > pos["current_stop"]:
                pos["current_stop"] = new_stop
            
            if current_price <= pos["current_stop"]:
                return True, f"触发ATR止损: {pos['current_stop']:.2f}"
        
        else:
            new_stop = current_price + atr * multiplier
            if new_stop < pos["current_stop"]:
                pos["current_stop"] = new_stop
            
            if current_price >= pos["current_stop"]:
                return True, f"触发ATR止损: {pos['current_stop']:.2f}"
        
        return False, ""
    
    def _check_time_stop(self, pos: Dict) -> tuple:
        """检查时间止损"""
        entry_time = pos["entry_time"]
        elapsed = (datetime.now() - entry_time).total_seconds() / 3600
        
        if elapsed > self.max_holding_hours:
            return True, f"触发时间止损(持仓{elapsed:.1f}小时)"
        
        return False, ""
    
    def update_stop(
        self,
        symbol: str,
        new_stop_price: float
    ):
        """手动更新止损价"""
        if symbol in self.positions:
            self.positions[symbol]["current_stop"] = new_stop_price
    
    def close_position(self, symbol: str):
        """平仓并清理"""
        if symbol in self.positions:
            del self.positions[symbol]
    
    def get_position_info(self, symbol: str) -> Optional[Dict]:
        """获取持仓信息"""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> Dict[str, Dict]:
        """获取所有持仓"""
        return self.positions.copy()


# 全局实例
stop_loss_manager = StopLossManager()
