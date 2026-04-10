"""
AM-HK Dashboard - 完整版 v3.0
支持: 币安(加密) + 老虎证券(美股/港股) + 新闻 + 资金费率
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
from datetime import datetime
from typing import Dict, List

import redis
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from aiokafka import AIOKafkaConsumer

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
        .data-table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
        .data-table th { text-align: left; padding: 8px; color: #8892b0; border-bottom: 1px solid #2a3050; }
        .data-table td { padding: 8px; border-bottom: 1px solid #1a1f3a; }
        .price-up { color: #00d084; } .price-down { color: #ff4757; }
        .metric { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #2a3050; }
        .metric-label { color: #8892b0; font-size: 0.9em; } .metric-value { font-weight: bold; }
        .log-container { background: #0d1117; border-radius: 5px; padding: 15px; font-family: monospace; font-size: 0.85em; max-height: 300px; overflow-y: auto; }
        .log-time { color: #6b7280; } .log-success { color: #34d399; } .log-error { color: #f87171; }
        .section-title { background: #2a3050; padding: 5px 10px; border-radius: 5px; margin: 15px 0 10px 0; font-size: 0.9em; color: #8892b0; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75em; margin-left: 5px; }
        .badge-us { background: #3b82f6; } .badge-hk { background: #f59e0b; } .badge-crypto { background: #8b5cf6; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 AM-HK Dashboard v3.0</h1>
        <p>Agent1 (MarketHarvester) 实时数据采集监控</p>
        <p style="margin-top: 10px; font-size: 0.9em;">数据源: 币安(加密) + 老虎证券(美股/港股) | 状态: <span id="conn-status">连接中...</span></p>
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
        <div class="card"><h2>🇺🇸 美股实时 <span class="badge badge-us">老虎证券</span></h2><div id="us-stocks"><p style="color: #8892b0; text-align: center;">等待数据...</p></div></div>
        <div class="card"><h2>🇭🇰 港股实时 <span class="badge badge-hk">老虎证券</span></h2><div id="hk-stocks"><p style="color: #8892b0; text-align: center;">等待数据...</p></div></div>
    </div>
    
    <div class="grid">
        <div class="card"><h2>💧 港股通资金流向 <span class="badge badge-hk">老虎证券</span></h2><div id="hk-capital"><p style="color: #8892b0; text-align: center;">等待数据...</p></div></div>
        <div class="card"><h2>📰 最新新闻</h2><div id="news"><p style="color: #8892b0; text-align: center;">等待数据...</p></div></div>
    </div>
    
    <div class="grid">
        <div class="card"><h2>📝 采集日志</h2><div id="logs" class="log-container"><div class="log-entry"><span class="log-time">--:--:--</span> 等待连接...</div></div></div>
    </div>
    
    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        const logs = document.getElementById("logs");
        let trades = [], news = [], usStocks = [], hkStocks = [], fundingRates = [];
        
        function addLog(msg, type="info") {
            const time = new Date().toLocaleTimeString();
            logs.insertAdjacentHTML("afterbegin", `<div class="log-entry"><span class="log-time">${time}</span> <span class="log-${type}">${msg}</span></div>`);
            if (logs.children.length > 50) logs.removeChild(logs.lastChild);
        }
        
        ws.onopen = () => { 
            document.getElementById("conn-status").textContent = "已连接"; 
            document.getElementById("conn-status").style.color = "#00d084"; 
            addLog("WebSocket 连接已建立", "success"); 
        };
        
        ws.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.type === "price") updatePrices(data.data);
            else if (data.type === "trade") updateTrades(data.data);
            else if (data.type === "orderbook") updateOrderbook(data.data);
            else if (data.type === "news") updateNews(data.data);
            else if (data.type === "us_stock") updateUSStocks(data.data);
            else if (data.type === "hk_stock") updateHKStocks(data.data);
            else if (data.type === "funding_rate") updateFunding(data.data);
            else if (data.type === "long_short_ratio") updateLSRatio(data.data);
            else if (data.type === "capital_flow") updateCapitalFlow(data.data);
            else if (data.type === "log") addLog(data.message, data.level);
        };
        
        ws.onclose = () => { 
            document.getElementById("conn-status").textContent = "已断开"; 
            document.getElementById("conn-status").style.color = "#ff4757"; 
            addLog("WebSocket 连接已断开", "error"); 
        };
        
        function updatePrices(data) {
            const change = data.change_pct || 0;
            const changeClass = change >= 0 ? "price-up" : "price-down";
            const changeIcon = change >= 0 ? "▲" : "▼";
            document.getElementById("prices").innerHTML = `
                <div class="metric"><span class="metric-label">${data.symbol}</span><span class="metric-value">$${Number(data.price).toFixed(5)}</span></div>
                <div class="metric"><span class="metric-label">涨跌幅</span><span class="metric-value ${changeClass}">${changeIcon} ${Math.abs(change).toFixed(2)}%</span></div>
                <div class="metric"><span class="metric-label">成交量</span><span class="metric-value">${(data.volume || 0).toLocaleString()}</span></div>
                <div class="metric"><span class="metric-label">更新时间</span><span class="metric-value">${new Date(data.timestamp).toLocaleTimeString()}</span></div>`;
        }
        
        function updateTrades(data) {
            trades.unshift(data);
            if (trades.length > 10) trades.pop();
            let html = '<table class="data-table"><tr><th>时间</th><th>标的</th><th>价格</th><th>数量</th></tr>';
            trades.forEach(t => {
                const time = new Date(t.timestamp).toLocaleTimeString();
                html += `<tr><td>${time}</td><td>${t.symbol || '-'}</td><td>$${Number(t.price).toFixed(5)}</td><td>${t.amount}</td></tr>`;
            });
            html += '</table>';
            document.getElementById("trades").innerHTML = html;
        }
        
        function updateOrderbook(data) {
            let html = '<table class="data-table"><tr><th>买盘</th><th>价格</th><th>卖盘</th></tr>';
            const bids = (data.bids || []).slice(0, 5);
            const asks = (data.asks || []).reverse().slice(0, 5);
            for (let i = 0; i < 5; i++) {
                const bid = bids[i] || ['-', '-'];
                const ask = asks[i] || ['-', '-'];
                html += `<tr><td class="price-up">${Number(bid[1]).toFixed(5)}</td><td style="text-align: center;">$${Number(ask[0]).toFixed(5)}</td><td class="price-down">${Number(ask[1]).toFixed(5)}</td></tr>`;
            }
            html += '</table>';
            document.getElementById("orderbook").innerHTML = html;
        }
        
        function updateNews(data) {
            news.unshift(data);
            if (news.length > 5) news.pop();
            let html = '';
            news.forEach(n => {
                html += `<div style="padding: 10px 0; border-bottom: 1px solid #2a3050;">
                    <div style="font-weight: bold; margin-bottom: 5px;">${n.title || '无标题'}</div>
                    <div style="font-size: 0.85em; color: #8892b0;">${n.source || '未知'} • ${new Date(n.published || Date.now()).toLocaleString()}</div>
                </div>`;
            });
            document.getElementById("news").innerHTML = html || '<p style="color: #8892b0; text-align: center;">暂无新闻</p>';
        }
        
        function updateUSStocks(data) {
            usStocks.unshift(data);
            if (usStocks.length > 10) usStocks.pop();
            let html = '<table class="data-table"><tr><th>标的</th><th>价格</th><th>涨跌</th><th>成交量</th></tr>';
            usStocks.forEach(s => {
                const changeClass = (s.change_pct || 0) >= 0 ? "price-up" : "price-down";
                const changeIcon = (s.change_pct || 0) >= 0 ? "▲" : "▼";
                html += `<tr><td>${s.symbol}</td><td>$${s.price}</td><td class="${changeClass}">${changeIcon} ${Math.abs(s.change_pct || 0).toFixed(2)}%</td><td>${(s.volume || 0).toLocaleString()}</td></tr>`;
            });
            html += '</table>';
            document.getElementById("us-stocks").innerHTML = html;
        }
        
        function updateHKStocks(data) {
            hkStocks.unshift(data);
            if (hkStocks.length > 10) hkStocks.pop();
            let html = '<table class="data-table"><tr><th>标的</th><th>价格</th><th>涨跌</th><th>状态</th></tr>';
            hkStocks.forEach(s => {
                const changeClass = (s.change_pct || 0) >= 0 ? "price-up" : "price-down";
                const changeIcon = (s.change_pct || 0) >= 0 ? "▲" : "▼";
                const status = s.is_halted ? '<span style="color: #ff4757;">停牌</span>' : '<span style="color: #00d084;">交易中</span>';
                html += `<tr><td>${s.symbol}</td><td>HK$${s.price}</td><td class="${changeClass}">${changeIcon} ${Math.abs(s.change_pct || 0).toFixed(2)}%</td><td>${status}</td></tr>`;
            });
            html += '</table>';
            document.getElementById("hk-stocks").innerHTML = html;
        }
        
        function updateFunding(data) {
            fundingRates.unshift(data);
            if (fundingRates.length > 5) fundingRates.pop();
            let html = '<table class="data-table"><tr><th>标的</th><th>资金费率</th><th>倒计时</th></tr>';
            fundingRates.forEach(f => {
                const rateClass = (f.funding_rate || 0) >= 0 ? "price-up" : "price-down";
                html += `<tr><td>${f.symbol}</td><td class="${rateClass}">${(f.funding_rate * 100).toFixed(4)}%</td><td>${f.countdown || '-'}</td></tr>`;
            });
            html += '</table>';
            document.getElementById("funding").innerHTML = html;
        }
        
        function updateLSRatio(data) {
            const ratio = data.long_short_ratio || 0;
            const longPct = ratio > 0 ? (ratio / (1 + ratio) * 100).toFixed(1) : 50;
            const shortPct = (100 - longPct).toFixed(1);
            document.getElementById("lsratio").innerHTML = `
                <div class="metric"><span class="metric-label">${data.symbol}</span><span class="metric-value">${ratio.toFixed(2)}</span></div>
                <div class="metric"><span class="metric-label">多头比例</span><span class="metric-value price-up">${longPct}%</span></div>
                <div class="metric"><span class="metric-label">空头比例</span><span class="metric-value price-down">${shortPct}%</span></div>`;
        }
        
        function updateCapitalFlow(data) {
            const netflow = data.northbound_net_inflow || 0;
            const flowClass = netflow >= 0 ? "price-up" : "price-down";
            const flowIcon = netflow >= 0 ? "▲" : "▼";
            document.getElementById("hk-capital").innerHTML = `
                <div class="metric"><span class="metric-label">标的</span><span class="metric-value">${data.symbol}</span></div>
                <div class="metric"><span class="metric-label">北水净流入</span><span class="metric-value ${flowClass}">${flowIcon} HK$${(Math.abs(netflow) / 1e6).toFixed(2)}M</span></div>
                <div class="metric"><span class="metric-label">主力净流入</span><span class="metric-value">HK$${((data.main_force_inflow || 0) / 1e6).toFixed(2)}M</span></div>
                <div class="metric"><span class="metric-label">散户净流入</span><span class="metric-value">HK$${((data.retail_net || 0) / 1e6).toFixed(2)}M</span></div>`;
        }
    </script>
</body>
</html>'''

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=HTML_TEMPLATE)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Dashboard WebSocket client connected")
    
    consumer = None
    connected = True
    
    try:
        consumer = AIOKafkaConsumer(
            'am-hk-raw-market-data',
            bootstrap_servers='localhost:9092',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            group_id='dashboard-ws-v3'
        )
        await consumer.start()
        
        await websocket.send_json({"type": "log", "message": "已连接到 Kafka 数据流", "level": "success"})
        
        async for msg in consumer:
            if not connected:
                break

            try:
                data = msg.value
                data_type = data.get("data_type", "unknown")
                market_type = data.get("market", "")
                
                # 币安加密数据
                if data_type == "kline":
                    payload = data.get("payload", {})
                    await websocket.send_json({"type": "price", "data": {
                        "symbol": data.get("symbol", "UNKNOWN"),
                        "price": payload.get("close", 0),
                        "change_pct": payload.get("change", 0),
                        "volume": payload.get("volume", 0),
                        "timestamp": data.get("timestamp", datetime.now().isoformat()),
                    }})
                elif data_type == "trade":
                    payload = data.get("payload", {})
                    await websocket.send_json({"type": "trade", "data": {
                        "symbol": data.get("symbol", "UNKNOWN"),
                        "price": payload.get("price", 0),
                        "amount": payload.get("amount", 0),
                        "timestamp": data.get("timestamp", datetime.now().isoformat()),
                    }})
                elif data_type == "orderbook":
                    await websocket.send_json({"type": "orderbook", "data": data.get("payload", {})})
                elif data_type == "funding_rate":
                    payload = data.get("payload", {})
                    await websocket.send_json({"type": "funding_rate", "data": {
                        "symbol": data.get("symbol", "UNKNOWN"),
                        "funding_rate": payload.get("funding_rate", 0),
                        "countdown": payload.get("countdown", ""),
                    }})
                elif data_type == "long_short_ratio":
                    payload = data.get("payload", {})
                    await websocket.send_json({"type": "long_short_ratio", "data": {
                        "symbol": data.get("symbol", "UNKNOWN"),
                        "long_short_ratio": payload.get("long_short_ratio", 0),
                    }})
                # 美股数据
                elif market_type == "US" or market_type == "US_STOCK":
                    payload = data.get("payload", {})
                    await websocket.send_json({"type": "us_stock", "data": {
                        "symbol": data.get("symbol", "UNKNOWN"),
                        "price": payload.get("price", 0),
                        "change_pct": payload.get("change_percent", 0),
                        "volume": payload.get("volume", 0),
                    }})
                # 港股数据
                elif market_type == "HK" or market_type == "HK_STOCK":
                    payload = data.get("payload", {})
                    await websocket.send_json({"type": "hk_stock", "data": {
                        "symbol": data.get("symbol", "UNKNOWN"),
                        "price": payload.get("last_price", 0),
                        "change_pct": payload.get("change_percent", 0),
                        "is_halted": payload.get("is_halted", False),
                    }})
                elif data_type == "capital_flow":
                    payload = data.get("payload", {})
                    now = datetime.now()
                    hk_am = 930 <= now.hour * 100 + now.minute <= 1200
                    hk_pm = 1300 <= now.hour * 100 + now.minute <= 1600
                    is_trading = (hk_am or hk_pm) and now.weekday() < 5
                    
                    await websocket.send_json({"type": "capital_flow", "data": {
                        "symbol": data.get("symbol", "UNKNOWN"),
                        "northbound_net_inflow": payload.get("northbound_net_inflow", 0),
                        "main_force_inflow": payload.get("main_force_inflow", 0),
                        "retail_net": payload.get("retail_net", 0),
                        "is_trading": is_trading,
                        "market_status": "交易中" if is_trading else "已闭市"
                    }})
                # 新闻数据
                elif data_type == "news":
                    payload = data.get("payload", {})
                    await websocket.send_json({"type": "news", "data": {
                        "title": payload.get("title", ""),
                        "source": payload.get("source", ""),
                        "published": payload.get("published", datetime.now().isoformat()),
                    }})
            except Exception as e:
                logger.error(f"Error: {e}")
                
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.001)
            except asyncio.TimeoutError:
                pass
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if consumer:
            await consumer.stop()
        logger.info("Dashboard client disconnected")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5020)