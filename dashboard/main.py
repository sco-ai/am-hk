"""
AM-HK Dashboard - 数据采集展示
简单的 Web 界面展示 Agent1 采集的实时数据
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
from datetime import datetime
from typing import Dict, List

import redis
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.utils import setup_logging

logger = setup_logging("dashboard")

# 创建 FastAPI 应用
app = FastAPI(title="AM-HK Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis 连接
redis_client = redis.from_url(settings.redis_url)

# 存储最近数据
recent_data = {
    "prices": [],
    "trades": [],
    "orderbook": [],
    "news": [],
}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AM-HK Dashboard - Agent1 数据采集</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0e27;
            color: #fff;
            padding: 20px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
        }
        .header h1 { font-size: 2em; margin-bottom: 10px; }
        .header p { opacity: 0.8; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: #1a1f3a;
            border-radius: 10px;
            padding: 20px;
            border: 1px solid #2a3050;
        }
        .card h2 {
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #667eea;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #00d084;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }
        .data-table th {
            text-align: left;
            padding: 10px;
            color: #8892b0;
            border-bottom: 1px solid #2a3050;
        }
        .data-table td {
            padding: 10px;
            border-bottom: 1px solid #1a1f3a;
        }
        .data-table tr:hover {
            background: #252a4a;
        }
        .price-up { color: #00d084; }
        .price-down { color: #ff4757; }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #2a3050;
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #8892b0; }
        .metric-value { font-weight: bold; }
        .log-container {
            background: #0d1117;
            border-radius: 5px;
            padding: 15px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.85em;
            max-height: 300px;
            overflow-y: auto;
        }
        .log-entry {
            padding: 3px 0;
            border-bottom: 1px solid #1a1f3a;
        }
        .log-time { color: #6b7280; }
        .log-info { color: #60a5fa; }
        .log-success { color: #34d399; }
        .log-error { color: #f87171; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 AM-HK Dashboard</h1>
        <p>Agent1 (MarketHarvester) 实时数据采集监控</p>
        <p style="margin-top: 10px; font-size: 0.9em;">
            数据源: Binance Testnet | 状态: <span id="conn-status">连接中...</span>
        </p>
    </div>
    
    <div class="grid">
        <div class="card">
            <h2><span class="status-dot"></span> 实时价格</h2>
            <div id="prices">
                <p style="color: #8892b0; text-align: center; padding: 20px;">等待数据...</p>
            </div>
        </div>
        
        <div class="card">
            <h2>📈 最近成交</h2>
            <div id="trades">
                <p style="color: #8892b0; text-align: center; padding: 20px;">等待数据...</p>
            </div>
        </div>
        
        <div class="card">
            <h2>📚 订单簿 (Top 5)</h2>
            <div id="orderbook">
                <p style="color: #8892b0; text-align: center; padding: 20px;">等待数据...</p>
            </div>
        </div>
        
        <div class="card">
            <h2>📰 最新新闻</h2>
            <div id="news">
                <p style="color: #8892b0; text-align: center; padding: 20px;">等待数据...</p>
            </div>
        </div>
        
        <div class="card" style="grid-column: span 2;">
            <h2>📝 采集日志</h2>
            <div id="logs" class="log-container">
                <div class="log-entry"><span class="log-time">--:--:--</span> 等待连接...</div>
            </div>
        </div>
    </div>
    
    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        const logs = document.getElementById('logs');
        
        function addLog(message, type = 'info') {
            const time = new Date().toLocaleTimeString();
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.innerHTML = `<span class="log-time">${time}</span> <span class="log-${type}">${message}</span>`;
            logs.insertBefore(entry, logs.firstChild);
            if (logs.children.length > 50) {
                logs.removeChild(logs.lastChild);
            }
        }
        
        ws.onopen = () => {
            document.getElementById('conn-status').textContent = '已连接';
            document.getElementById('conn-status').style.color = '#00d084';
            addLog('WebSocket 连接已建立', 'success');
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'price') {
                updatePrices(data.data);
            } else if (data.type === 'trade') {
                updateTrades(data.data);
            } else if (data.type === 'orderbook') {
                updateOrderbook(data.data);
            } else if (data.type === 'news') {
                updateNews(data.data);
            } else if (data.type === 'log') {
                addLog(data.message, data.level);
            }
        };
        
        ws.onclose = () => {
            document.getElementById('conn-status').textContent = '已断开';
            document.getElementById('conn-status').style.color = '#ff4757';
            addLog('WebSocket 连接已断开', 'error');
        };
        
        function updatePrices(data) {
            const container = document.getElementById('prices');
            const change = data.change_pct || 0;
            const changeClass = change >= 0 ? 'price-up' : 'price-down';
            const changeIcon = change >= 0 ? '▲' : '▼';
            
            container.innerHTML = `
                <div class="metric">
                    <span class="metric-label">${data.symbol}</span>
                    <span class="metric-value">$${data.price.toLocaleString()}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">涨跌幅</span>
                    <span class="metric-value ${changeClass}">${changeIcon} ${Math.abs(change).toFixed(2)}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">成交量</span>
                    <span class="metric-value">${(data.volume || 0).toLocaleString()}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">更新时间</span>
                    <span class="metric-value">${new Date(data.timestamp).toLocaleTimeString()}</span>
                </div>
            `;
        }
        
        function updateTrades(data) {
            const container = document.getElementById('trades');
            let html = '<table class="data-table"><tr><th>时间</th><th>价格</th><th>数量</th></tr>';
            
            (data.trades || []).slice(0, 5).forEach(trade => {
                const time = new Date(trade.timestamp).toLocaleTimeString();
                html += `<tr><td>${time}</td><td>$${trade.price}</td><td>${trade.amount}</td></tr>`;
            });
            
            html += '</table>';
            container.innerHTML = html;
        }
        
        function updateOrderbook(data) {
            const container = document.getElementById('orderbook');
            let html = '<table class="data-table"><tr><th>买盘</th><th>价格</th><th>卖盘</th></tr>';
            
            const bids = (data.bids || []).slice(0, 5);
            const asks = (data.asks || []).reverse().slice(0, 5);
            
            for (let i = 0; i < 5; i++) {
                const bid = bids[i] || ['-', '-'];
                const ask = asks[i] || ['-', '-'];
                html += `<tr>
                    <td class="price-up">${bid[1]}</td>
                    <td style="text-align: center;">$${ask[0]}</td>
                    <td class="price-down">${ask[1]}</td>
                </tr>`;
            }
            
            html += '</table>';
            container.innerHTML = html;
        }
        
        function updateNews(data) {
            const container = document.getElementById('news');
            let html = '';
            
            (data.articles || []).slice(0, 3).forEach(article => {
                html += `<div style="padding: 10px 0; border-bottom: 1px solid #2a3050;">
                    <div style="font-weight: bold; margin-bottom: 5px;">${article.title}</div>
                    <div style="font-size: 0.85em; color: #8892b0;">${article.source} • ${new Date(article.published).toLocaleString()}</div>
                </div>`;
            });
            
            container.innerHTML = html || '<p style="color: #8892b0; text-align: center;">暂无新闻</p>';
        }
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Dashboard 主页"""
    return HTMLResponse(content=HTML_TEMPLATE)


@app.get("/api/data")
async def get_data():
    """获取当前数据"""
    return {
        "prices": recent_data["prices"],
        "trades": recent_data["trades"],
        "orderbook": recent_data["orderbook"],
        "news": recent_data["news"],
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    return {
        "total_messages": len(recent_data["prices"]) + len(recent_data["trades"]),
        "symbols_monitored": ["BTCUSDT", "ETHUSDT"],
        "data_sources": ["binance", "newsapi"],
        "status": "running",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时数据推送"""
    await websocket.accept()
    logger.info("Dashboard WebSocket client connected")
    
    try:
        # 订阅 Redis 频道
        pubsub = redis_client.pubsub()
        pubsub.subscribe("am-hk-raw-market-data")
        
        await websocket.send_json({
            "type": "log",
            "message": "已连接到数据流",
            "level": "success"
        })
        
        while True:
            # 非阻塞获取消息
            message = pubsub.get_message(timeout=1)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                
                # 根据数据类型处理
                data_type = data.get("data_type", "unknown")
                
                if data_type == "tick":
                    await websocket.send_json({
                        "type": "price",
                        "data": data.get("payload", {})
                    })
                elif data_type == "trade":
                    await websocket.send_json({
                        "type": "trade",
                        "data": {"trades": [data.get("payload", {})]}
                    })
                elif data_type == "orderbook":
                    await websocket.send_json({
                        "type": "orderbook",
                        "data": data.get("payload", {})
                    })
                elif data_type == "news":
                    await websocket.send_json({
                        "type": "news",
                        "data": {"articles": [data.get("payload", {})]}
                    })
            
            # 检查客户端是否断开
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
            except asyncio.TimeoutError:
                pass
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        pubsub.unsubscribe()
        pubsub.close()
        logger.info("Dashboard WebSocket client disconnected")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5020)
