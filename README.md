# Paper Trading Project

零风险纸面交易模拟平台，支持 LLM 多智能体交易和基于 24 因子的策略回测。

## 功能特性

- 实时市场数据获取（yfinance）
- LLM 多智能体交易流水线（宏观分析 + 选股 + 风控）
- 24 因子规则回测引擎
- 策略配置生成与管理
- Alpaca Paper Trading API 实盘模拟
- 括号订单止盈/止损
- 多策略并行交易与资金分配
- 自然语言意图识别
- 自动最优策略选择

## 安装

```bash
pip install -e ".[dev]"
```

复制 `.env.example` 为 `.env` 并填入 API 密钥。

## 使用方式

```bash
python -m paper_trading                        # 交互式菜单
python -m paper_trading --live                 # LLM 实盘交易（真实订单）
python -m paper_trading --use-strategy 2       # 策略 #2 规则交易（模拟）
python -m paper_trading --backtest             # 回测全部策略
python -m paper_trading --auto-select          # 回测全部，自动选择最优并交易
python -m paper_trading --generate-config      # 重新生成策略配置
python -m paper_trading --summary              # 查看 Alpaca 账户摘要
```

## 开源协议

详见 [LICENSE](LICENSE)。
