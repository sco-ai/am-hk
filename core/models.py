"""
AM-HK v3.0 核心消息模型
定义Agent间通信的消息格式
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MarketType(str, Enum):
    """市场类型"""
    BTC = "btc"
    CRYPTO = "CRYPTO"  # 加密货币统一标识
    HK_STOCK = "hk_stock"
    US_STOCK = "us_stock"
    NEWS = "news"


class DataType(str, Enum):
    """数据类型"""
    TICK = "tick"           # 逐笔成交
    KLINE = "kline"         # K线数据
    ORDERBOOK = "orderbook" # 订单簿
    NEWS = "news"           # 新闻
    FACTOR = "factor"       # 因子
    SIGNAL = "signal"       # 交易信号
    ORDER = "order"         # 订单


class AgentType(str, Enum):
    """Agent类型"""
    HARVESTER = "agent1_harvester"
    CURATOR = "agent2_curator"
    SCANNER = "agent3_scanner"
    ORACLE = "agent4_oracle"
    GUARDIAN = "agent5_guardian"
    LEARNING = "agent6_learning"


class ActionType(str, Enum):
    """操作类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    PASS = "pass"


class MarketData(BaseModel):
    """市场数据基类"""
    symbol: str
    market: MarketType
    timestamp: datetime
    data_type: DataType
    payload: Dict[str, Any]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class FactorData(BaseModel):
    """因子数据"""
    symbol: str
    market: MarketType
    timestamp: datetime
    factors: Dict[str, float]  # 30+因子
    raw_data_hash: str


class Signal(BaseModel):
    """交易信号"""
    symbol: str
    market: MarketType
    action: ActionType
    confidence: float = Field(ge=0, le=1)
    predicted_return: float
    timeframe: str  # 5min, 15min, 1h
    reasoning: str
    agent_id: str
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class TradeDecision(BaseModel):
    """交易决策"""
    signal: Signal
    position_size: float  # 仓位比例
    stop_loss: float
    take_profit: float
    risk_score: float = Field(ge=0, le=1)
    approved: bool = False
    approval_reason: str = ""


class AgentMessage(BaseModel):
    """Agent间通信消息"""
    msg_id: str
    msg_type: str
    source_agent: AgentType
    target_agent: Optional[AgentType]
    timestamp: datetime
    payload: Dict[str, Any]
    priority: int = 5  # 1-10, 数字越小优先级越高
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
