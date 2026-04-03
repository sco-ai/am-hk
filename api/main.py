"""
AM-HK API服务
FastAPI + 飞书集成
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.feishu_commands import FeishuCommandHandler, send_trade_signal
from core.utils import setup_logging

logger = setup_logging("am-hk-api")

# 飞书命令处理器
feishu_handler = FeishuCommandHandler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("API service starting...")
    yield
    # 关闭
    logger.info("API service shutting down...")


app = FastAPI(
    title="AM-HK Trading System",
    description="AlphaMind HK Market Analysis & Trading API",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "AM-HK Trading System",
        "version": "3.0.0",
        "status": "running",
        "features": [
            "multi_market_data",
            "ai_prediction",
            "risk_management",
            "feishu_integration",
        ],
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "agents": ["harvester", "curator", "scanner", "oracle", "guardian", "learning"],
        "services": ["kafka", "redis", "postgres"],
    }


@app.get("/status")
async def system_status():
    """系统状态"""
    return {
        "system": "AM-HK v3.0",
        "status": "running",
        "features": [
            "multi_market_data",
            "factor_calculation",
            "signal_generation",
            "ai_prediction",
            "risk_management",
            "learning_feedback",
            "feishu_integration",
        ],
    }


# === 交易控制接口 ===

@app.post("/trading/start")
async def start_trading():
    """启动交易"""
    from core.kafka import MessageBus
    bus = MessageBus("api")
    
    bus.publish_command("all_agents", {"type": "start"})
    logger.info("Trading start requested via API")
    
    # 发送飞书通知
    from core.feishu_commands import send_system_alert
    await send_system_alert(
        title="🚀 交易已启动",
        message="系统通过API启动，开始采集数据并生成交易信号",
        level="info",
    )
    
    return {"status": "success", "message": "Trading started"}


@app.post("/trading/stop")
async def stop_trading():
    """停止交易"""
    from core.kafka import MessageBus
    bus = MessageBus("api")
    
    bus.publish_command("all_agents", {"type": "stop"})
    logger.info("Trading stop requested via API")
    
    # 发送飞书通知
    from core.feishu_commands import send_system_alert
    await send_system_alert(
        title="🛑 交易已停止",
        message="系统通过API停止，不再生成新的交易信号",
        level="warning",
    )
    
    return {"status": "success", "message": "Trading stopped"}


@app.get("/trading/status")
async def trading_status():
    """交易状态"""
    return {
        "trading_enabled": True,
        "active_agents": 6,
        "last_signal": None,
        "feishu_webhook": "configured" if settings.FEISHU_WEBHOOK_URL else "not_configured",
    }


# === 风控配置接口 ===

@app.post("/risk/config")
async def update_risk_config(config: dict):
    """更新风控配置"""
    from core.kafka import MessageBus
    bus = MessageBus("api")
    
    bus.publish_command("agent5_guardian", {
        "type": "update_config",
        "config": config,
    })
    
    logger.info(f"Risk config update: {config}")
    return {"status": "success", "config": config}


@app.get("/risk/config")
async def get_risk_config():
    """获取风控配置"""
    return {
        "max_position_size": 0.1,
        "max_daily_loss": 0.05,
        "stop_loss": 0.02,
        "take_profit": 0.05,
    }


# === 信号查询接口 ===

@app.get("/signals")
async def get_signals(limit: int = 10):
    """获取最近信号"""
    return {
        "signals": [],  # TODO: 从缓存获取
        "count": 0,
    }


@app.get("/signals/{symbol}")
async def get_symbol_signals(symbol: str):
    """获取特定标的信号"""
    return {
        "symbol": symbol,
        "signals": [],
    }


# === 飞书集成接口 ===

@app.post("/feishu/webhook")
async def feishu_webhook(request: Request):
    """
    飞书Webhook回调
    
    处理飞书机器人消息和卡片回调
    """
    try:
        payload = await request.json()
        logger.debug(f"Feishu webhook received: {payload}")
        
        # 处理URL验证（首次配置Webhook时使用）
        if "challenge" in payload:
            return {"challenge": payload["challenge"]}
        
        # 处理命令
        result = await feishu_handler.handle_webhook(payload)
        return result
    
    except Exception as e:
        logger.error(f"Error handling Feishu webhook: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/feishu/test")
async def test_feishu_notification():
    """测试飞书通知"""
    try:
        success = await send_trade_signal({
            "symbol": "BTCUSDT",
            "action": "BUY",
            "confidence": 0.75,
            "predicted_return": 3.5,
            "reasoning": "BTC突破关键阻力位，趋势向上，建议买入",
            "position_size": 0.05,
            "stop_loss": 0.02,
            "take_profit": 0.05,
            "market": "BTC",
        })
        
        if success:
            return {"status": "success", "message": "Test notification sent"}
        else:
            return {"status": "error", "message": "Failed to send notification"}
    
    except Exception as e:
        logger.error(f"Test notification failed: {e}")
        return {"status": "error", "message": str(e)}


# === 性能指标接口 ===

@app.get("/metrics")
async def get_metrics():
    """获取系统指标"""
    return {
        "total_trades": 0,
        "winning_trades": 0,
        "total_pnl": 0.0,
        "sharpe_ratio": 0.0,
        "max_drawdown": 0.0,
    }


@app.get("/metrics/agents")
async def get_agent_metrics():
    """获取Agent指标"""
    return {
        "harvester": {"status": "running", "messages_processed": 0},
        "curator": {"status": "running", "factors_computed": 0},
        "scanner": {"status": "running", "signals_generated": 0},
        "oracle": {"status": "running", "predictions_made": 0},
        "guardian": {"status": "running", "trades_approved": 0},
        "learning": {"status": "running", "models_trained": 0},
    }


# === 通知测试接口 ===

@app.post("/notify/signal")
async def notify_signal(signal: dict):
    """手动发送交易信号通知"""
    success = await send_trade_signal(signal)
    return {"status": "success" if success else "error"}


async def start_api():
    """启动API服务"""
    import uvicorn
    
    config = uvicorn.Config(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()
