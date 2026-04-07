# BTC资金数据采集规范实现报告

## 完成内容

### 1. 资金数据API实现 (`core/connectors/binance_rest.py`)

新增以下资金数据获取方法：

| 数据类型 | API端点 | 轮询方法 | 回调方法 |
|---------|---------|---------|---------|
| 资金费率 | `/fapi/v1/fundingRate` | `_poll_funding_rates()` | `_on_binance_funding_rate()` |
| 持仓量 | `/fapi/v1/openInterest` | `_poll_open_interest()` | `_on_binance_open_interest()` |
| 多空比 | `/fapi/v1/topLongShortAccountRatio` | `_poll_long_short_ratio()` | `_on_binance_long_short_ratio()` |

#### 新增方法：
- `subscribe_funding_rate(symbol, callback)` - 订阅资金费率
- `subscribe_open_interest(symbol, callback)` - 订阅持仓量
- `subscribe_long_short_ratio(symbol, callback)` - 订阅多空比
- `start_funding_polling(interval=300)` - 启动资金数据轮询（默认5分钟）
- `_get_fapi(endpoint, params)` - 合约API请求封装

#### 数据转换函数：
- `convert_funding_rate_to_standard(symbol, data)`
- `convert_open_interest_to_standard(symbol, data)`
- `convert_long_short_ratio_to_standard(symbol, data)`

### 2. Agent采集器更新 (`agents/agent1_harvester/main.py`)

- 导入新的资金数据转换函数
- 在 `_start_binance()` 中添加资金数据订阅
- 新增回调函数：
  - `_on_binance_funding_rate()`
  - `_on_binance_open_interest()`
  - `_on_binance_long_short_ratio()`
- 启动资金数据轮询任务（每5分钟）

### 3. 模型更新 (`core/models.py`)

- 在 `MarketType` 枚举中添加 `CRYPTO = "CRYPTO"` 作为加密货币统一标识

### 4. 统一数据输出格式

所有资金数据输出遵循统一格式：

```json
{
  "symbol": "BTCUSDT",
  "market": "CRYPTO",
  "timestamp": 1712553600000,
  "data_type": "funding_rate|open_interest|long_short_ratio",
  "payload": {
    // 具体数据字段
  }
}
```

#### 各类型payload字段：

**funding_rate:**
```json
{
  "funding_rate": 0.0001,
  "funding_time": 1712553600000,
  "collection_time": 1712553600000
}
```

**open_interest:**
```json
{
  "open_interest": 123456.789,
  "quote_volume": 9876543210.0,
  "collection_time": 1712553600000
}
```

**long_short_ratio:**
```json
{
  "long_account_ratio": 0.55,
  "short_account_ratio": 0.45,
  "long_short_ratio": 1.22,
  "collection_time": 1712553600000
}
```

## 验收验证

### 代码语法检查 ✓
```bash
python3 -m py_compile core/connectors/binance_rest.py  # OK
python3 -m py_compile agents/agent1_harvester/main.py  # OK
python3 -m py_compile core/models.py                   # OK
```

### 数据格式测试 ✓
运行 `test_funding_data.py` 验证：
- ✓ Funding Rate format validation PASSED
- ✓ Open Interest format validation PASSED
- ✓ Long/Short Ratio format validation PASSED
- ✓ KLine format validation PASSED (兼容性)

### 发布目标
- Topic: `am-hk-raw-market-data`
- Key: 交易对符号 (如 "BTCUSDT")
- Value: 标准格式JSON数据

## 使用方式

```python
# 在 agent1_harvester 启动时自动订阅
harvester = MarketHarvester()
asyncio.run(harvester.start())
# 资金数据将自动每5分钟采集并发布到Kafka
```

## 日志输出示例

```
[INFO] Subscribed funding rate: BTCUSDT
[INFO] Subscribed open interest: BTCUSDT
[INFO] Subscribed long/short ratio: BTCUSDT
[INFO] Binance funding data polling started (interval: 300s)
[INFO] Funding data collection complete, sleeping 300s...
[DEBUG] Published funding rate for BTCUSDT: 0.0001
[DEBUG] Published open interest for BTCUSDT: 123456.789
[DEBUG] Published L/S ratio for BTCUSDT: 1.22
```

## 文件变更清单

1. `/am-hk/core/connectors/binance_rest.py` - 添加资金数据API方法和转换函数
2. `/am-hk/agents/agent1_harvester/main.py` - 添加资金数据订阅和回调
3. `/am-hk/core/models.py` - 添加CRYPTO市场类型
4. `/am-hk/test_funding_data.py` - 新增测试脚本（可选）
