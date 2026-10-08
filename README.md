# EMSJB — Energy Management System for Battery Storage

A full-stack simulation dashboard for **Battery Energy Storage System (BESS) arbitrage** on the Indian Energy Exchange (IEX) Day-Ahead Market. The system forecasts electricity prices using Machine Learning, then optimizes battery charge/discharge schedules using **CVaR-based stochastic optimization** to maximise trading profit while managing risk.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  React Frontend                 │
│  (Vite + Plotly.js interactive charts)          │
│  Config Panel │ KPIs │ Charts │ History Table   │
└──────────────────────┬──────────────────────────┘
                       │  REST API (JSON)
┌──────────────────────▼──────────────────────────┐
│                 FastAPI Backend                  │
│  /api/config  /api/data/summary                 │
│  /api/simulation/run  /api/simulation/history    │
│  /api/simulation/{id}/metrics                   │
│  /api/simulation/{id}/baseline                  │
└──────────────────────┬──────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
   src/forecast    src/optimizer    src/baseline
   (RandomForest)  (PuLP CVaR LP)  (Naive / None)
       │               │               │
       └───────────────┼───────────────┘
                       ▼
                  SQLite (emsjb.db)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, Vite 7, Plotly.js, Lucide Icons |
| **Backend** | Python 3, FastAPI, Uvicorn |
| **Database** | SQLite via SQLAlchemy |
| **ML Model** | scikit-learn (RandomForestRegressor) |
| **Optimizer** | PuLP (CBC solver) — CVaR linear programme |
| **Data** | IEX DAM hourly prices (Dec 2024 – Dec 2025) |

## Setup & Installation

### Prerequisites
- Python 3.9+
- Node.js 18+

### Backend
```bash
cd EMSJB
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
pip install -r requirements.txt
pip install fastapi uvicorn sqlalchemy
```

### Frontend
```bash
cd frontend
npm install
```

## Running the Application

**Terminal 1 — Backend:**
```bash
source .venv/bin/activate
python -m uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

## Project Structure

```
EMSJB/
├── backend/
│   ├── main.py          # FastAPI app with all endpoints
│   ├── models.py        # SQLAlchemy ORM models
│   ├── schemas.py       # Pydantic request/response schemas
│   └── database.py      # Database engine setup
├── src/
│   ├── config.py        # Battery & simulation parameters
│   ├── data_loader.py   # CSV data loading & preprocessing
│   ├── forecast.py      # RandomForest price forecasting model
│   ├── optimizer.py      # CVaR battery dispatch optimisation (PuLP)
│   ├── simulation.py    # Receding-horizon simulation loop
│   ├── baseline.py      # Naive & no-storage baseline strategies
│   ├── metrics.py       # Performance metrics (Sharpe, drawdown, etc.)
│   └── plotting.py      # Matplotlib plot generation
├── frontend/
│   ├── src/
│   │   ├── App.jsx      # Main dashboard component
│   │   ├── App.css      # Dashboard stylesheet
│   │   └── main.jsx     # React entry point
│   ├── index.html       # HTML template
│   └── package.json     # Node dependencies
├── data/
│   └── iex_dam_hourly_2024_25.csv  # IEX price dataset
├── outputs/             # Generated plots & CSV results
├── main.py              # Standalone CLI simulation runner
├── requirements.txt     # Python dependencies
└── README.md
```

## Configuration Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Battery Power | 1,000 kW | Max charge/discharge rate |
| Battery Energy | 4,000 kWh | Total storage capacity (4-hour system) |
| Round-trip Efficiency | 88% | Energy retained per cycle |
| Cycle Life | 6,000 | Expected lifetime cycles |
| CAPEX | ₹2,01,60,000 | Capital expenditure |
| Forecast Lag | 24 hours | Historical window for ML model |
| Planning Horizon | 24 hours | Optimisation look-ahead |
| CVaR α | 0.95 | Confidence level for risk measure |

## Key Features

1. **ML Price Forecasting** — RandomForest trained on 8,700+ hours of real IEX DAM data with hour-of-day and day-of-week features
2. **CVaR Stochastic Optimization** — Risk-aware battery dispatch using Conditional Value-at-Risk with scenario generation from forecast residuals
3. **Receding Horizon Control** — Rolling 24-hour optimisation window, re-solved every hour
4. **Baseline Comparisons** — Optimised strategy vs. naive peak/off-peak vs. no-storage
5. **Interactive Dashboard** — Real-time charts, KPI cards, strategy comparison, and simulation history
6. **Performance Analytics** — Sharpe ratio, max drawdown, utilization rate, profit per cycle
