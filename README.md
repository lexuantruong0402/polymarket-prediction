# Predict Market Bot

Phân tích, dự báo và thực thi giao dịch trên Prediction Market với kiểm soát rủi ro.

## Kiến trúc Pipeline — 6 Stages

```
Scan → Research → Predict → Risk → Execute → Compound
 │        │          │         │        │         │
 │ Lọc    │ NLP      │ XGBoost │ 5 risk │ CLOB    │ Post-mortem
 │ thị    │ sentiment│ + LLM   │ checks │ on-chain│ analysis
 │ trường │ analysis │ calib.  │ Kelly  │ + hedge │ → knowledge
 └────────┴──────────┴─────────┴────────┴─────────┴──────────────
```

## Cài đặt

```bash
# Clone & setup
cd predict
python -m venv .venv
source .venv/bin/activate

# Install (editable mode + dev deps)
pip install -e ".[dev]"

# Copy config
cp .env.example .env
# → Chỉnh sửa .env theo môi trường của bạn
```

## Chạy Bot

```bash
# CLI entry point
predict-bot

# Hoặc chạy trực tiếp
python -m predict_market_bot.orchestrator
```

## Backtesting (Kiểm thử chiến thuật)

Bot hỗ trợ 2 chế độ backtest để đánh giá hiệu quả trước khi trade thật:

### 1. Mock Backtest (Dữ liệu tĩnh)
Sử dụng dữ liệu mẫu có sẵn trong `data/historical_sample.json`. Chế độ này hữu ích để test logic pipeline và rủi ro nhanh chóng.

```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python3 scripts/run_backtest.py
```

### 2. Real-World Backtest (Dữ liệu thực tế)
Tự động lấy các thị trường đã kết thúc từ Polymarket và tìm kiếm tin tức lịch sử tương ứng qua NewsAPI để mô phỏng điều kiện thực tế.

```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python3 scripts/run_real_backtest.py
```

*Lưu ý: Chế độ Real-World yêu cầu internet và `NEWS_API_KEY` hợp lệ.*

## Chạy Tests

```bash
python -m pytest tests/ -v
```

## Core Formulas

| Formula | Function | Điều kiện |
|---------|----------|-----------|
| Expected Value | `EV = p·b - (1-p)` | — |
| Market Edge | `edge = p_model - p_mkt` | Trade khi `edge > 0.04` |
| Kelly Criterion | `f* = (p·b - q) / b` | — |
| Fractional Kelly | `f = α · f*` | `α ∈ [0.25, 0.5]` |
| VaR (95%) | `VaR = μ - 1.645·σ` | Trong giới hạn ngày |
| Max Drawdown | `MDD = (Peak-Trough)/Peak` | `MDD ≤ 8%` |
| Sharpe Ratio | `SR = (E[R]-Rf) / σ(R)` | Target > 2.0 |
| Profit Factor | `PF = gross_profit/gross_loss` | Target > 1.5 |

## Risk Rules (phải pass trước khi Execute)

1. `edge > 0.04`
2. `size ≤ kelly(f, bankroll)`
3. `exposure + bet ≤ max_exposure`
4. `VaR(95%)` trong giới hạn ngày
5. `MDD ≤ 8%`

## Performance Targets

- Win Rate ≥ 65%
- Sharpe Ratio > 2.0
- Profit Factor > 1.5
- Max Drawdown ≤ 8%

## Cấu trúc thư mục

```
src/predict_market_bot/
├── config/settings.py       # Pydantic Settings
├── core/
│   ├── models.py            # Domain dataclasses
│   └── formulas.py          # 12 trading math functions
├── pipeline/
│   ├── scanner.py           # Stage 1 — quét thị trường
│   ├── researcher.py        # Stage 2 — NLP + social data (hỗ trợ historical)
│   ├── predictor.py         # Stage 3 — XGBoost + LLM
│   ├── risk_manager.py      # Stage 4 — 5 risk checks
│   ├── executor.py          # Stage 5 — CLOB execution (hoặc MockExecutor)
│   ├── compounder.py        # Stage 6 — post-mortem
│   ├── backtester.py        # Điều phối backtest engine
│   ├── fetcher.py           # Nạp dữ liệu Polymarket history
│   └── mocks.py             # Giả lập các Stage cho simulation
├── orchestrator.py           # Pipeline coordinator (hỗ trợ DI)
├── knowledge/store.py        # JSON knowledge base
└── utils/
    ├── logger.py             # Structured logging
    └── metrics.py            # Performance tracker
```

## License

MIT

## State Migration & Portability

If you want to move this project and its current task state to another machine:

1.  **Archived State**: I have copied the current task list, implementation plans, and walkthrough to `.agent/brain/`.
2.  **Migration steps**:
    ```bash
    git init
    git add .
    git commit -m "Initialize project with core modules and task history"
    # Create a new repo on GitHub, then:
    git remote add origin <your-github-repo-url>
    git push -u origin main
    ```
3.  **On the new machine**: Clone the repo and you will have all the context needed to continue.
