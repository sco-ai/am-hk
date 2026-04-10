"""
应用配置管理 - Enhanced v2.03
"""
import os
from typing import Dict, List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # 应用信息
    APP_NAME: str = "AM-HK"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False

    # API 配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8020

    # 数据库配置
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5452
    POSTGRES_DB: str = "alphamind_hk"
    POSTGRES_USER: str = "am_hk_user"
    POSTGRES_PASSWORD: str = "changeme"

    # Redis 配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6399
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # Kafka 配置
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9112"
    KAFKA_ZOOKEEPER: str = "localhost:2201"
    KAFKA_PORT: int = 9112
    ZOOKEEPER_PORT: int = 2201
    KAFKA_UI_PORT: int = 8100

    # ============================================
    # 模型配置 (v2.03)
    # ============================================
    LIGHTGBM_MODEL_PATH: str = "./models/lightgbm_model.pkl"
    XGBOOST_MODEL_PATH: str = "./models/xgboost_model.pkl"
    RL_MODEL_PATH: str = "./models/ppo_position_model.pkl"
    
    MODEL_UPDATE_INTERVAL: int = 3600
    MODEL_CACHE_TTL: int = 300
    MODEL_PREDICTION_THRESHOLD: float = 0.65
    
    # 模型融合权重
    ENSEMBLE_LGB_WEIGHT: float = 0.45
    ENSEMBLE_XGB_WEIGHT: float = 0.35
    ENSEMBLE_RL_WEIGHT: float = 0.20

    # ============================================
    # 风控配置 (v2.03)
    # ============================================
    # 仓位限制
    MAX_POSITION_PCT: float = 0.30
    MAX_SINGLE_POSITION_PCT: float = 0.15
    MAX_TOTAL_EXPOSURE_PCT: float = 1.0
    
    # 风险阈值
    MAX_DAILY_LOSS_PCT: float = 0.05
    MAX_DRAWDOWN_PCT: float = 0.15
    MAX_RISK_PER_TRADE_PCT: float = 0.02
    ACCOUNT_RISK_LIMIT_PCT: float = 0.06
    VAR_LIMIT_PCT: float = 0.03
    
    # 止损设置
    DEFAULT_STOP_LOSS_PCT: float = 0.02
    TRAILING_STOP_ACTIVATION_PCT: float = 0.01
    TRAILING_STOP_DISTANCE_PCT: float = 0.015
    MAX_HOLDING_HOURS: int = 48

    # ============================================
    # 市场状态配置 (v2.03)
    # ============================================
    TREND_DETECTION_PERIOD: int = 20
    MARKET_STATE_WINDOW: int = 100
    
    # 波动率阈值
    VOL_VERY_LOW_THRESHOLD: float = 5.0
    VOL_LOW_THRESHOLD: float = 15.0
    VOL_NORMAL_THRESHOLD: float = 35.0
    VOL_HIGH_THRESHOLD: float = 60.0
    
    # 自适应权重
    ADAPTIVE_WEIGHT_UPDATE_INTERVAL: int = 3600
    WEIGHT_ADJUSTMENT_SPEED: float = 0.1

    # ============================================
    # 加密货币专属配置 (v2.03)
    # ============================================
    CRYPTO_PAIRS: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
    
    FUNDING_RATE_THRESHOLD: float = 0.001
    FUNDING_RATE_EXTREME: float = 0.003
    
    OI_CHANGE_ALERT_THRESHOLD: float = 10.0
    OI_MONITORING_WINDOW: int = 24
    
    LIQUIDATION_ALERT_THRESHOLD: float = 0.7
    CASCADE_RISK_THRESHOLD: float = 0.8

    # ============================================
    # AI 模型配置
    # ============================================
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"

    QWEN_API_KEY: str = ""
    QWEN_API_URL: str = "https://api.openai.com/v1"

    KIMI_API_KEY: str = ""
    KIMI_API_URL: str = "https://api.moonshot.cn/v1"

    INFORMER_API_URL: str = ""
    INFORMER_API_KEY: str = ""

    NHITS_API_URL: str = ""
    NHITS_API_KEY: str = ""

    RL_API_URL: str = ""
    RL_API_KEY: str = ""

    GNN_API_URL: str = ""
    GNN_API_KEY: str = ""

    FINBERT_API_URL: str = ""
    FINBERT_API_KEY: str = ""

    # ============================================
    # 新闻 API 配置
    # ============================================
    NEWSAPI_KEY: str = "ca67cb343dd04a2581cded62f2964fd4"
    TWITTER_BEARER_TOKEN: str = ""
    REDDIT_CLIENT_ID: str = ""
    REDDIT_SECRET: str = ""

    # ============================================
    # 交易 API 配置
    # ============================================
    BINANCE_API_KEY: str = ""
    BINANCE_SECRET: str = ""
    BINANCE_TESTNET: bool = False

    ALPHAVANTAGE_API_KEY: str = ""
    ALPHAVANTAGE_ENABLED: bool = False

    # Tiger Securities - DISABLED
    TIGER_ENABLED: bool = False
    TIGER_ID: str = ""
    TIGER_ACCOUNT: str = ""
    TIGER_LICENSE: str = ""
    TIGER_ENV: str = "PROD"
    TIGER_PRIVATE_KEY: str = ""
    TIGER_ENABLE_PAPER: bool = True

    # ============================================
    # 数据采集配置
    # ============================================
    DATA_COLLECTION_INTERVAL: int = 60
    MARKETS: List[str] = ["crypto"]  # 禁用美股和港股

    # ============================================
    # 旧风控配置 (兼容)
    # ============================================
    MAX_POSITION_SIZE: float = 0.1
    MAX_DAILY_LOSS: float = 0.05
    STOP_LOSS_PCT: float = 0.02
    TAKE_PROFIT_PCT: float = 0.05

    # ============================================
    # 其他配置
    # ============================================
    MODEL_UPDATE_INTERVAL_LEGACY: int = 3600
    PREDICTION_TIMEFRAMES: List[str] = ["5min", "15min", "1h"]

    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    FEISHU_WEBHOOK_URL: str = ""

    HTTP_PROXY: str = "http://127.0.0.1:2080"
    HTTPS_PROXY: str = ""

    SECRET_KEY: str = "generate_a_strong_secret_key_here"

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    @property
    def database_url(self) -> str:
        """PostgreSQL 连接字符串"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def redis_url(self) -> str:
        """Redis 连接字符串"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def model_weights(self) -> Dict[str, float]:
        """获取模型融合权重"""
        return {
            "lightgbm": self.ENSEMBLE_LGB_WEIGHT,
            "xgboost": self.ENSEMBLE_XGB_WEIGHT,
            "rl": self.ENSEMBLE_RL_WEIGHT,
        }
    
    @property
    def risk_limits(self) -> Dict[str, float]:
        """获取风险限制"""
        return {
            "max_position_pct": self.MAX_POSITION_PCT,
            "max_single_position_pct": self.MAX_SINGLE_POSITION_PCT,
            "max_total_exposure_pct": self.MAX_TOTAL_EXPOSURE_PCT,
            "max_daily_loss_pct": self.MAX_DAILY_LOSS_PCT,
            "max_drawdown_pct": self.MAX_DRAWDOWN_PCT,
            "max_risk_per_trade_pct": self.MAX_RISK_PER_TRADE_PCT,
            "account_risk_limit_pct": self.ACCOUNT_RISK_LIMIT_PCT,
            "var_limit_pct": self.VAR_LIMIT_PCT,
        }
    
    @property
    def stop_loss_config(self) -> Dict[str, any]:
        """获取止损配置"""
        return {
            "default_stop_pct": self.DEFAULT_STOP_LOSS_PCT,
            "trailing_activation_pct": self.TRAILING_STOP_ACTIVATION_PCT,
            "trailing_distance_pct": self.TRAILING_STOP_DISTANCE_PCT,
            "max_holding_hours": self.MAX_HOLDING_HOURS,
        }

    def ai_model_enabled(self, model_name: str) -> bool:
        """检查AI模型是否已配置"""
        config_map = {
            "openai": bool(self.OPENAI_API_KEY),
            "deepseek": bool(self.DEEPSEEK_API_KEY),
            "qwen": bool(self.QWEN_API_KEY),
            "kimi": bool(self.KIMI_API_KEY),
            "informer": bool(self.INFORMER_API_URL),
            "n-hits": bool(self.NHITS_API_URL),
            "rl": bool(self.RL_API_URL),
            "gnn": bool(self.GNN_API_URL),
            "finbert": bool(self.FINBERT_API_URL),
        }
        return config_map.get(model_name.lower(), False)


# 全局配置实例
settings = Settings()
