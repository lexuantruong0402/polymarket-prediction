# Implementation Plan: Polymarket Prediction Bot Frontend

This plan outlines the creation of a web-based frontend for the Polymarket prediction bot, allowing users to input a market URL and see the evaluation process in real-time.

## Proposed Changes

### Backend (Python/FastAPI)

#### [NEW] [api.py](file:///home/truonglx1/polymarket-prediction/src/predict_market_bot/api.py)
- Implement a FastAPI server with an endpoint `/process`.
- The endpoint will parse the Polymarket URL/slug.
- Use Server-Sent Events (SSE) to stream pipeline progress (Stage 1-6).

#### [MODIFY] [orchestrator.py](file:///home/truonglx1/polymarket-prediction/src/predict_market_bot/orchestrator.py)
- Refactor `run()` to accept an optional `market_id` or `slug`.
- Add callback support to report progress to the API layer.

#### [MODIFY] [scanner.py](file:///home/truonglx1/polymarket-prediction/src/predict_market_bot/pipeline/scanner.py)
- Add `fetch_by_slug(slug: str)` to retrieve a specific market.

---

### Frontend (HTML/CSS/JS)

#### [NEW] [index.html](file:///home/truonglx1/polymarket-prediction/frontend/index.html)
- Main landing page with a premium, glassmorphism design.
- URL input field and "Process" button.
- Progress timeline visualization.
- Results display area.

#### [NEW] [style.css](file:///home/truonglx1/polymarket-prediction/frontend/style.css)
- Custom Vanilla CSS design system.
- Dark mode, gradients, and micro-animations.

#### [NEW] [app.js](file:///home/truonglx1/polymarket-prediction/frontend/app.js)
- Handle form submission and SSE connection.
- Update UI states based on pipeline progress.

## Verification Plan

### Automated Tests
- Create unit tests for the new `fetch_by_slug` method in `scanner.py`.
- Run: `pytest tests/test_scanner.py`

### Manual Verification
1. Start the backend: `python -m predict_market_bot.api`
2. Open the frontend in a browser.
3. Input a valid Polymarket URL (e.g., `https://polymarket.com/event/will-the-fed-cut-rates-in-march`).
4. Click "Process" and verify:
   - Progress updates are displayed sequentially.
   - Final results are rendered correctly in the UI.
