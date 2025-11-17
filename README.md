# ASTER Long-Only Grid Trading Agent

> An AI agent managed quant program built with [VibeTrading.dev](https://vibetrading.dev) that autonomously executes a long-only grid trading strategy for ASTER perpetual futures.

![VibeTrading Agent Screenshot](agent_screenshot.png)

## Overview

This repository demonstrates a production-ready AI agent managed quant program built with **VibeTrading.dev**, an AI-native platform that transforms trading ideas into systematic strategies. The quant program implements a sophisticated long-only grid trading strategy with automated risk management, position sizing, and take-profit mechanisms.

## Live Production Deployment

This AI agent managed quant program is currently running live on **Aster Exchange** and has been actively trading ASTER perpetual futures for **weeks** without interruption.

**On-Chain Address**: `0x8fa6498f83ae574de8cb13f52281a98fc9e92071`  
**VibeTrading.dev Agent**: [View on VibeTrading.dev](https://vibetrading.dev/agent/2025-10-29_09-19-32_8a9b5d2a_0_live)

You can monitor the quant program's live performance and trading activity:
- On **Aster Exchange** using the on-chain address above
- On **VibeTrading.dev** platform with real-time analytics and performance metrics

### Production Code & Logs

This repository contains the **actual production code** that has been running continuously:

- **[`strategy.py`](strategy.py)** - The complete production strategy code (396 lines)
- **[`logs/`](logs/)** - Weeks of execution logs demonstrating continuous operation:
  - Daily service logs from November 4-16, 2025
  - Live trading logs with detailed execution history
  - Backtest logs showing strategy validation
  - Agent event logs tracking all trading activity

The logs show this quant program has been executing trades every 5 minutes, managing positions, and maintaining grid orders consistently for multiple weeks, proving the reliability and stability of AI agent managed quant programs in production.

## Strategy Details

### Core Strategy
- **Type**: Long-only grid trading
- **Asset**: ASTER perpetual futures
- **Leverage**: 5x
- **Grid Spacing**: 0.5% between levels
- **Grid Levels**: 40 levels per side (below center)
- **Take Profit**: 8% gain threshold
- **Execution**: Every 5 minutes

### Key Features

- **Intelligent Grid Placement**: Places buy orders at geometric intervals below current price to accumulate positions during dips
- **15-Minute VWAP Initialization**: Uses volume-weighted average price from 15-minute candles to set grid center
- **Dynamic Position Sizing**: Margin-aware order sizing with 85% margin utilization
- **Automated Take Profit**: Closes 50% of position when 8% profit threshold is reached
- **Hibernation Mode**: Automatically pauses when price moves outside active grid range
- **Self-Healing Order Management**: Automatically cancels misaligned orders and maintains grid integrity


## Code Structure

The complete production code is available in [`strategy.py`](strategy.py). The strategy uses VibeTrading's decorator-based execution model:

```python
@vibe(interval="1m")
def aster_long_only_grid():
    # Main strategy execution
    # - Market data snapshot
    # - Grid initialization
    # - Order management
    # - Position & take profit management
```

See [`strategy.py`](strategy.py) for the full implementation that has been running in production for weeks.

## Configuration

Key parameters can be adjusted in `strategy.py`:

```python
ASSET = "ASTER"
SPACING_PCT = 0.005              # 0.5% grid spacing
GRID_LEVELS_EACH_SIDE = 40       # Grid depth
LEVERAGE = 5                     # Trading leverage
TP_THRESHOLD_PCT = 0.08          # 8% take profit
OHLCV_INTERVAL = "15m"           # Data timeframe
```

## Performance Highlights

Based on live trading data:
- ✅ Stable execution with zero runtime errors
- ✅ Consistent order management (10 active orders maintained)
- ✅ Successful position accumulation (+4,836.74 ASTER)
- ✅ Automatic profit-taking when thresholds are met
- ✅ Adaptive margin management

## About VibeTrading.dev

[VibeTrading.dev](https://vibetrading.dev) is an AI-native trading platform that enables traders to:

- **Generate Strategies**: Transform natural language trading ideas into production-ready code
- **Backtest**: Validate strategies with tick-level precision across historical data
- **Deploy**: Run strategies 24/7 with automated risk management
- **Monitor**: Real-time analytics and performance tracking

This quant program is managed by VibeTrading's AI agent, demonstrating how complex trading logic can be autonomously executed and maintained through AI-driven management.

## Build Your Own Quant Program

Ready to create your own AI agent managed quant program? This repository serves as a reference implementation showing what's possible with **VibeTrading.dev**.

**Get started at [VibeTrading.dev](https://vibetrading.dev)** and transform your trading ideas into production-ready quant programs. Whether you're interested in grid trading, mean reversion, trend following, or custom strategies, VibeTrading's AI agent can help you build, backtest, and deploy your own managed quant programs.
