# 配置项参考

## 概述

所有配置通过环境变量管理，前缀 `PAPER_TRADING_`，由 pydantic-settings 自动加载 `.env` 文件。

## 环境变量完整列表

### 应用基础

| 环境变量 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `PAPER_TRADING_APP_NAME` | str | Paper Trading Project | 应用名称，用于日志和报告 |
| `PAPER_TRADING_VERSION` | str | 0.1.0 | 版本号 |
| `PAPER_TRADING_ENVIRONMENT` | str | development | 运行环境：development / staging / production |
| `PAPER_TRADING_DEBUG` | bool | true | 调试模式，开启后输出更详细的日志 |

### Azure OpenAI（LLM Agent 必需）

| 环境变量 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `PAPER_TRADING_AZURE_OPENAI_ENDPOINT` | str | https://hkust.azure-api.net/ | Azure OpenAI API 端点 URL |
| `PAPER_TRADING_AZURE_OPENAI_API_KEY` | str | (空) | API 密钥，**必填** |
| `PAPER_TRADING_AZURE_OPENAI_API_VERSION` | str | 2025-02-01-preview | API 版本 |
| `PAPER_TRADING_AZURE_OPENAI_DEPLOYMENT` | str | gpt-4o | 模型部署名称 |

### Alpaca Paper Trading（实盘交易必需）

| 环境变量 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `PAPER_TRADING_ALPACA_API_KEY` | str | (空) | Alpaca API Key ID，**实盘必填** |
| `PAPER_TRADING_ALPACA_SECRET_KEY` | str | (空) | Alpaca Secret Key，**实盘必填** |
| `PAPER_TRADING_ALPACA_BASE_URL` | str | https://paper-api.alpaca.markets | Paper Trading API 地址 |

### 交易参数

| 环境变量 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `PAPER_TRADING_LOOKBACK_DAYS` | int | 20 | 技术指标回溯天数 |
| `PAPER_TRADING_BACKTEST_START` | str | 2022-01-01 | 数据下载起始日期 |
| `PAPER_TRADING_INITIAL_CAPITAL` | int | 100000 | 默认初始资金 (USD) |
| `PAPER_TRADING_TAKE_PROFIT_PCT` | float | 0.15 | 默认止盈比例 (15%) |
| `PAPER_TRADING_STOP_LOSS_PCT` | float | 0.08 | 默认止损比例 (8%) |
| `PAPER_TRADING_TRAILING_STOP_PCT` | float | 0.05 | 移动止损比例 (5%，代码中定义但未在 CLI 中使用) |
| `PAPER_TRADING_RISK_FREE_RATE` | float | 0.04 | 无风险利率 (4%)，用于 Sharpe/Sortino 计算 |

### 组合配置

| 环境变量 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `PAPER_TRADING_PORTFOLIO_TICKERS` | str | AAPL,MSFT,JPM,JNJ,XOM,AMZN,NVDA,UNH,BAC,PG | 默认股票池，逗号分隔 |

## 配置类代码映射

```python
# src/paper_trading/config.py
class Settings(BaseSettings):
    model_config = {"env_prefix": "PAPER_TRADING_", "env_file": ".env"}
```

配置通过 `from paper_trading.config import settings` 全局单例访问。**禁止硬编码任何密钥或端点。**

## Azure OpenAI 客户端

```python
from paper_trading.config import get_azure_client

client = get_azure_client()  # 单例，使用 lru_cache 缓存
```

`get_azure_client()` 是惰性初始化，仅在首次 LLM 调用时创建连接。所有 Agent 通过 `BaseAgent.call_llm()` 统一使用此客户端。

## .env 文件模板

参考 `.env.example`，复制为 `.env` 并填入实际值：

```bash
cp .env.example .env
# 编辑 .env，替换 your-azure-key-here 和 your-alpaca-key-here
```

**必填项**：
- `PAPER_TRADING_AZURE_OPENAI_API_KEY` — LLM Agent 功能必需
- `PAPER_TRADING_ALPACA_API_KEY` + `PAPER_TRADING_ALPACA_SECRET_KEY` — 实盘交易必需

**LLM 和 Alpaca 均可降级运行**：
- 无 LLM → Agent 返回启发式 fallback 值，策略规则交易不受影响
- 无 Alpaca → 回测、信号分析、Dry Run 正常，真实订单被跳过
