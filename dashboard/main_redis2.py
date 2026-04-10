"""
AM-HK Dashboard - Redis 版本
支持: 币安(加密) + Redis Pub/Sub 数据流
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
from datetime import datetime

import redis
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.utils import setup_logging

logger = setup_logging("dashboard")

app = FastAPI(title="AM-HK Dashboard", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_client = redis.from_url(settings.redis_url)

HTML_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <title>AM-HK Dashboard v3.0</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0a0e27; color: #fff; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; }
        .header h1 { font-size: 2em; margin-bottom: 10px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .card { background: #1a1f3a; border-radius: 10px; padding: 20px; border: 1px solid #2a3050; }
        .card h2 { font-size: 1.2em; margin-bottom: 15px; color: #667eea; display: flex; align-items: center; gap: 10px; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; background: #00d084; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .price-up { color: #00d084; } .price-down { color: #ff4757; }
        .metric { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #2a3050; }
        .metric-label { color: #8892b0; font-size: 0.9em; } .metric-value { font-weight: bold; }
        .log-container { background: #0d1117; border-radius: 5px; padding: 15px; font-family: monospace; font-size: 0.85em; max-height: 300px; overflow-y: auto; }
        .log-time { color: #6b7280; } .log-success { color: #34d399; } .log-error { color: #f87171; }
        .section-title { background: #2a3050; padding: 5px 10px; border-radius: 5px; margin: 15px 0 10px 0; font-size: 0.9em; color: #8892b0; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75em; margin-left: 5px; }
        .badge-crypto { background: #8b5cf6; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 AM-HK Dashboard v3.0</h1>
        <p>Agent1 (MarketHarvester) 实时数据采集监控</p>
        <p style="margin-top: 10px; font-size: 0.9em;">数据源: 币安(BTC/ETH/SOL/XRP/DOGE) | 状态: <span id="conn-status">连接中...</span></p>
    </div>
    
    <div class="grid">
        <div class="card"><h2><span class="status-dot"></span> 实时价格 <span class="badge badge-crypto">币安</span></h2><div id="prices"><p style="color: #8892b0; text-align: center;">等待数据...</p></div></div>
        <div class="card"><h2>📈 最近成交 <span class="badge badge-crypto">币安</span></h2><div id="trades"><p style="color: #8892b0; text-align: center;">等待数据...</p></div></div>
    </div>
    
    <div class="grid">
        <div class="card"><h2>📚 订单簿 (Top 5) <span class="badge badge-crypto">币安</span></h2><div id="orderbook"><p style="color: #8892b0; text-align: center;">等待数据...</p></div></div>
        <div class="card">
            <h2>💰 资金费率 <span class="badge badge-crypto">币安</span></h2>
            <div id="funding"><p style="color: #8892b0; text-align: center;">等待数据...</p></div>
            <div class="section-title">多空比</div>
            <div id="lsratio"><p style="color: #8892b0; text-align: center;">等待数据...</p></div>
        </div>
    </div>
    
    <div class="grid">
        <div class="card"><h2>📝 采集日志</h2><div id="logs" class="log-container"><div class="log-entry"><span class="log-time">--:--:--</span> 等待连接...</div></div></div>
    </div>
    
    <script>
        const ws = new WebSocket("ws://" + window.location.host + "/ws");
        const prices = {}; const trades = []; const logs = [];
        
        function addLog(msg, type="info") {
            const time = new Date().toLocaleTimeString();
            logs.unshift({time, msg, type});
            if (logs.length > 50) logs.pop();
            document.getElementById("logs").innerHTML = logs.map(l => 
                `<div class="log-entry"><span class="log-time">${l.time}</span> <span class="log-${l.type}">${l.msg}</span></div>`
            ).join("");
        }
        
        ws.onopen = () => { document.getElementById("conn-status").textContent = "已连接"; addLog("WebSocket 已连接", "success"); };
        ws.onclose = () => { document.getElementById("conn-status").textContent = "已断开"; addLog("WebSocket 已断开", "error"); };
        ws.onerror = (e) => { addLog("WebSocket 错误", "error"); };
        
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === "price") {
                const d = msg.data; prices[d.symbol] = d;
                document.getElementById("prices").innerHTML = Object.values(prices).map(p => {
                    const changeClass = p.change_pct >= 0 ? "price-up" : "price-down";
                    const changeIcon = p.change_pct >= 0 ? "▲" : "▼";
                    return `<div class="metric"><span class="metric-label">${p.symbol}</span><span class="metric-value ${changeClass}">${changeIcon} $${Number(p.price).toLocaleString()} (${p.change_pct.toFixed(2)}%)</span></div>`;
                }).join("");
            } else if (msg.type === "trade") {
                const d = msg.data; trades.unshift(d); if (trades.length > 10) trades.pop();
                document.getElementById("trades").innerHTML = trades.map(t => 
                    `<div class="metric"><span class="metric-label">${t.symbol}</span><span class="metric-value">$${t.price} | ${t.amount}</span></div>`
                ).join("");
            } else if (msg.type === "orderbook") {
                const ob = msg.data;
                let html = "<div style=\"display: flex; gap: 20px;\"><div style=\"flex: 1;\"><h4>买盘</h4>";
                if (ob.bids) ob.bids.slice(0, 5).forEach(b => html += `<div style="color: #00d084;">${b[0]} | ${b[1]}</div>`);
                html += "</div><div style=\"flex: 1;\"><h4>卖盘</h4>";
                if (ob.asks) ob.asks.slice(0, 5).forEach(a => html += `<div style="color: #ff4757;">${a[0]} | ${a[1]}</div>`);
                html += "</div></div>";
                document.getElementById("orderbook").innerHTML = html;
            } else if (msg.type === "funding_rate") {
                const d = msg.data;
                document.getElementById("funding").innerHTML = `<div class="metric"><span class="metric-label">${d.symbol}</span><span class="metric-value">${(d.funding_rate * 100).toFixed(4)}%</span></div>`;
            } else if (msg.type === "long_short_ratio") {
                const d = msg.data;
                document.getElementById("lsratio").innerHTML = `<div class="metric"><span class="metric-label">${d.symbol}</span><span class="metric-value">${d.long_short_ratio.toFixed(2)}</span></div>`;
            } else if (msg.type === "log") {
                addLog(msg.message, msg.level || "info");
            }
        };
    </script>
</body>
</html>'''

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=HTML_TEMPLATE)

@app.get("/health")
async def health():
    return {"status": "healthy", "backend": "redis"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Dashboard WebSocket client connected")
    await websocket.send_json({"type": "log", "message": "已连接到 Redis 数据流", "level": "success"})
    
    try:
        pubsub = redis_client.pubsub()
        pubsub.subscribe("am-hk-raw-market-data")
        
        for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    msg_data = data.get("value", data)
                    data_type = msg_data.get("data_type", "unknown")
                    
                    if data_type == "kline":
                        payload = msg_data.get("payload", {})
                        await websocket.send_json({"type": "price", "data": {
                            "symbol": msg_data.get("symbol", "UNKNOWN"),
                            "price": payload.get("close", 0),
                            "change_pct": payload.get("change", 0),
                            "volume": payload.get("volume", 0),
                            "timestamp": msg_data.get("timestamp", datetime.now().isoformat()),
                        }})
                    elif data_type == "trade":
                        payload = msg_data.get("payload", {})
                        await websocket.send_json({"type": "trade", "data": {
                            "symbol": msg_data.get("symbol", "UNKNOWN"),
                            "price": payload.get("price", 0),
                            "amount": payload.get("amount", 0),
                            "timestamp": msg_data.get("timestamp", datetime.now().isoformat()),
                        }})
                    elif data_type == "orderbook":
                        await websocket.send_json({"type": "orderbook", "data": msg_data.get("payload", {})})
                    elif data_type == "funding_rate":
                        payload = msg_data.get("payload", {})
                        await websocket.send_json({"type": "funding_rate", "data": {
                            "symbol": msg_data.get("symbol", "UNKNOWN"),
                            "funding_rate": payload.get("funding_rate", 0),
                            "countdown": payload.get("countdown", ""),
                        }})
                    elif data_type == "long_short_ratio":
                        payload = msg_data.get("payload", {})
                        await websocket.send_json({"type": "long_short_ratio", "data": {
                            "symbol": msg_data.get("symbol", "UNKNOWN"),
                            "long_short_ratio": payload.get("long_short_ratio", 0),
                        }})
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        pubsub.close()
        logger.info("Dashboard client disconnected")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5020)
