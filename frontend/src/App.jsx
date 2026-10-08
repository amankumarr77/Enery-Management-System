import { useState, useEffect } from 'react'
import axios from 'axios'
import Plot from 'react-plotly.js'
import { Activity, Battery, DollarSign, Zap, Play, Settings, Database, BarChart3, TrendingUp, RefreshCw, Download, Target, Clock, PieChart, AlertTriangle } from 'lucide-react'
import Navbar from './components/Navbar'
import TradingPanel from './components/TradingPanel'
import LiveChart from './components/LiveChart'
import OrderBook from './components/OrderBook'
import PositionTracker from './components/PositionTracker'
import RiskPanel from './components/RiskPanel'
import { useMarketData } from './hooks/useMarketData'
import { useTrading } from './hooks/useTrading'
import './App.css'

const API = 'http://127.0.0.1:8000'

function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('emsjb-theme') || 'dark')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('emsjb-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark')
  const [activeTab, setActiveTab] = useState('trading')

  // Market data hook
  const {
    currentPrice,
    priceHistory,
    priceDirection,
    stats,
    forecast,
    isConnected: marketConnected,
  } = useMarketData()

  // Trading hook
  const {
    orders,
    trades,
    position,
    tradingStatus,
    riskLimits,
    alerts,
    isConnected: tradingConnected,
    placeOrder,
    cancelOrder,
    startTrading,
    stopTrading,
    dismissAlert,
  } = useTrading()

  // ── Analytics tab state (preserved original) ──
  const [config, setConfig] = useState(null)
  const [dataSummary, setDataSummary] = useState(null)
  const [simulationData, setSimulationData] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [baseline, setBaseline] = useState(null)
  const [forecastAcc, setForecastAcc] = useState(null)
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const [error, setError] = useState(null)
  const [steps, setSteps] = useState(168)
  const [configEditing, setConfigEditing] = useState(false)
  const [configDraft, setConfigDraft] = useState({})

  useEffect(() => {
    fetchConfig()
    fetchDataSummary()
    fetchHistory()
    fetchForecastAccuracy()
  }, [])

  const fetchConfig = async () => {
    try { const res = await axios.get(`${API}/api/config`); setConfig(res.data); setConfigDraft(res.data) } catch (err) { console.error(err) }
  }
  const fetchDataSummary = async () => {
    try { const res = await axios.get(`${API}/api/data/summary`); setDataSummary(res.data) } catch (err) { console.error(err) }
  }
  const fetchHistory = async () => {
    try { const res = await axios.get(`${API}/api/simulation/history`); setHistory(res.data) } catch (err) { console.error(err) }
  }
  const fetchForecastAccuracy = async () => {
    try { const res = await axios.get(`${API}/api/forecast/accuracy`); setForecastAcc(res.data) } catch (err) { console.error(err) }
  }

  const runSimulation = async () => {
    setLoading(true); setError(null)
    try {
      const res = await axios.get(`${API}/api/simulation/run?steps=${steps}`)
      setSimulationData(res.data)
      const [metricsRes, baselineRes] = await Promise.all([
        axios.get(`${API}/api/simulation/${res.data.id}/metrics`),
        axios.get(`${API}/api/simulation/${res.data.id}/baseline`),
      ])
      setMetrics(metricsRes.data); setBaseline(baselineRes.data); fetchHistory()
    } catch (err) { setError("Simulation failed.") }
    setLoading(false)
  }

  const loadRun = async (runId) => {
    setLoading(true); setError(null)
    try {
      const [simRes, metricsRes, baselineRes] = await Promise.all([
        axios.get(`${API}/api/simulation/${runId}`),
        axios.get(`${API}/api/simulation/${runId}/metrics`),
        axios.get(`${API}/api/simulation/${runId}/baseline`),
      ])
      setSimulationData(simRes.data); setMetrics(metricsRes.data); setBaseline(baselineRes.data)
    } catch (err) { setError("Failed to load run.") }
    setLoading(false)
  }

  const exportCSV = async (runId) => {
    try {
      const res = await axios.get(`${API}/api/simulation/${runId}/export`, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url; link.setAttribute('download', `simulation_run_${runId}.csv`)
      document.body.appendChild(link); link.click(); link.remove()
    } catch (err) { console.error(err) }
  }

  const saveConfig = async () => {
    try {
      const res = await axios.post(`${API}/api/config`, configDraft)
      setConfig(res.data); setConfigEditing(false)
    } catch (err) { console.error(err) }
  }

  const inr = (v) => '₹' + Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 })
  const pct = (v) => (v * 100).toFixed(1) + '%'

  // -- Theme-aware chart config --
  const isDark = theme === 'dark'
  const chartColors = {
    grid: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)',
    tick: isDark ? '#8694a8' : '#4b5c72',
    line: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
    font: isDark ? '#8694a8' : '#4b5c72',
  }

  const buildHeatmapData = () => {
    if (!simulationData?.steps?.length) return null
    const grid = Array.from({ length: 7 }, () => Array(24).fill(null))
    const counts = Array.from({ length: 7 }, () => Array(24).fill(0))
    simulationData.steps.forEach((s, i) => {
      const hour = i % 24, day = Math.floor(i / 24) % 7
      if (grid[day][hour] === null) grid[day][hour] = 0
      grid[day][hour] += s.profit; counts[day][hour] += 1
    })
    for (let d = 0; d < 7; d++) for (let h = 0; h < 24; h++) if (counts[d][h] > 0) grid[d][h] /= counts[d][h]
    return { z: grid, x: Array.from({ length: 24 }, (_, i) => `${i}:00`), y: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], type: 'heatmap', colorscale: [[0, '#c94444'], [0.5, isDark ? '#141b27' : '#e8eaee'], [1, '#3a9e6e']], hoverongaps: false }
  }

  // -- Plotly layout helper --
  const darkLayout = (extra = {}) => ({
    autosize: true,
    plot_bgcolor: 'transparent',
    paper_bgcolor: 'transparent',
    font: { family: 'Inter', size: 11, color: chartColors.font },
    xaxis: { gridcolor: chartColors.grid, tickfont: { color: chartColors.tick }, linecolor: chartColors.line, ...extra.xaxis },
    yaxis: { gridcolor: chartColors.grid, tickfont: { color: chartColors.tick }, linecolor: chartColors.line, ...extra.yaxis },
    margin: { l: 55, r: 20, t: 10, b: 45 },
    ...extra,
  })

  return (
    <div className="app-container">
      <Navbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        marketConnected={marketConnected}
        tradingConnected={tradingConnected}
        currentPrice={currentPrice}
        priceDirection={priceDirection}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      <main className="app-main">
        {/* ═══════════ TRADING TAB ═══════════ */}
        {activeTab === 'trading' && (
          <div className="trading-layout">
            {/* Left: Trading Panel */}
            <div className="trading-left">
              <TradingPanel
                currentPrice={currentPrice}
                priceDirection={priceDirection}
                tradingStatus={tradingStatus}
                position={position}
                onPlaceOrder={placeOrder}
                onStartTrading={startTrading}
                onStopTrading={stopTrading}
              />
            </div>

            {/* Center: Chart + Orders */}
            <div className="trading-center">
              <LiveChart priceHistory={priceHistory} forecast={forecast} theme={theme} />
              <OrderBook orders={orders} onCancel={cancelOrder} />
            </div>

            {/* Right: Position + Risk */}
            <div className="trading-right">
              <PositionTracker position={position} trades={trades} />
              <RiskPanel riskLimits={riskLimits} alerts={alerts} onDismissAlert={dismissAlert} />
            </div>
          </div>
        )}

        {/* ═══════════ ANALYTICS TAB ═══════════ */}
        {activeTab === 'analytics' && (
          <div className="analytics-content">
            {/* Controls */}
            <div className="controls-section">
              <select className="step-select" value={steps} onChange={e => setSteps(Number(e.target.value))}>
                <option value={24}>1 Day (24h)</option>
                <option value={168}>1 Week (168h)</option>
                <option value={336}>2 Weeks (336h)</option>
                <option value={720}>1 Month (720h)</option>
              </select>
              <button className="btn-primary" onClick={runSimulation} disabled={loading}>
                {loading ? <><RefreshCw size={16} className="spinner-inline" /> Running...</> : <><Play size={16} /> Run Simulation</>}
              </button>
              {simulationData && (
                <button className="btn-export" onClick={() => exportCSV(simulationData.id)}>
                  <Download size={16} /> Export CSV
                </button>
              )}
            </div>

            {error && <div className="error-toast"><AlertTriangle size={14} /> {error}</div>}

            {/* System Overview */}
            <div className="section-title">System Overview</div>
            <div className="info-grid">
              <div className="info-card">
                <div className="info-card-header">
                  <div className="info-card-icon blue"><Settings size={18} /></div>
                  <h2>Battery Configuration</h2>
                  <button className="btn-mini" onClick={() => { setConfigEditing(!configEditing); setConfigDraft(config) }}>
                    {configEditing ? 'Cancel' : 'Edit'}
                  </button>
                </div>
                {configEditing ? (
                  <div className="config-editor">
                    <div className="config-field"><label>Power (kW)</label><input type="number" value={configDraft.battery_power_kw || ''} onChange={e => setConfigDraft({ ...configDraft, battery_power_kw: parseFloat(e.target.value) })} /></div>
                    <div className="config-field"><label>Energy (kWh)</label><input type="number" value={configDraft.battery_energy_kwh || ''} onChange={e => setConfigDraft({ ...configDraft, battery_energy_kwh: parseFloat(e.target.value) })} /></div>
                    <div className="config-field"><label>Round-trip Eff.</label><input type="number" step="0.01" min="0" max="1" value={configDraft.round_trip_efficiency || ''} onChange={e => setConfigDraft({ ...configDraft, round_trip_efficiency: parseFloat(e.target.value) })} /></div>
                    <div className="config-field"><label>Cycle Life</label><input type="number" value={configDraft.cycle_life || ''} onChange={e => setConfigDraft({ ...configDraft, cycle_life: parseInt(e.target.value) })} /></div>
                    <div className="config-field"><label>CVaR α</label><input type="number" step="0.01" value={configDraft.cvar_alpha || ''} onChange={e => setConfigDraft({ ...configDraft, cvar_alpha: parseFloat(e.target.value) })} /></div>
                    <div className="config-field"><label>CVaR λ</label><input type="number" step="0.05" value={configDraft.cvar_lambda || ''} onChange={e => setConfigDraft({ ...configDraft, cvar_lambda: parseFloat(e.target.value) })} /></div>
                    <div className="config-field"><label>Horizon (hrs)</label><input type="number" value={configDraft.planning_horizon_hours || ''} onChange={e => setConfigDraft({ ...configDraft, planning_horizon_hours: parseInt(e.target.value) })} /></div>
                    <div className="config-field"><label>Scenarios</label><input type="number" value={configDraft.scenarios || ''} onChange={e => setConfigDraft({ ...configDraft, scenarios: parseInt(e.target.value) })} /></div>
                    <button className="btn-save" onClick={saveConfig}>Save & Apply</button>
                  </div>
                ) : config ? (
                  <div className="info-grid-inner">
                    <div className="info-item"><span className="label">Power</span><span className="value">{config.battery_power_kw.toLocaleString()} kW</span></div>
                    <div className="info-item"><span className="label">Energy</span><span className="value">{config.battery_energy_kwh.toLocaleString()} kWh</span></div>
                    <div className="info-item"><span className="label">Efficiency</span><span className="value">{(config.round_trip_efficiency * 100).toFixed(0)}%</span></div>
                    <div className="info-item"><span className="label">Cycle Life</span><span className="value">{config.cycle_life.toLocaleString()}</span></div>
                    <div className="info-item"><span className="label">CAPEX</span><span className="value">{inr(config.capex_inr)}</span></div>
                    <div className="info-item"><span className="label">OPEX/yr</span><span className="value">{inr(config.opex_per_year_inr)}</span></div>
                    <div className="info-item"><span className="label">CVaR α</span><span className="value">{config.cvar_alpha}</span></div>
                    <div className="info-item"><span className="label">CVaR λ</span><span className="value">{config.cvar_lambda}</span></div>
                  </div>
                ) : <p className="loading-text">Loading...</p>}
              </div>

              <div className="info-card">
                <div className="info-card-header">
                  <div className="info-card-icon green"><Database size={18} /></div>
                  <h2>Dataset Overview</h2>
                </div>
                {dataSummary ? (
                  <div className="info-grid-inner">
                    <div className="info-item"><span className="label">Total Hours</span><span className="value">{dataSummary.total_hours.toLocaleString()}</span></div>
                    <div className="info-item"><span className="label">Date Range</span><span className="value" style={{fontSize:'0.75rem'}}>{dataSummary.date_start.split(' ')[0]} → {dataSummary.date_end.split(' ')[0]}</span></div>
                    <div className="info-item"><span className="label">Mean Price</span><span className="value">₹{dataSummary.price_mean}/kWh</span></div>
                    <div className="info-item"><span className="label">Std Dev</span><span className="value">₹{dataSummary.price_std}/kWh</span></div>
                    <div className="info-item"><span className="label">Min</span><span className="value">₹{dataSummary.price_min}/kWh</span></div>
                    <div className="info-item"><span className="label">Max</span><span className="value">₹{dataSummary.price_max}/kWh</span></div>
                    {forecastAcc && <div className="info-item"><span className="label">MAPE</span><span className="value">{forecastAcc.train_mape}%</span></div>}
                  </div>
                ) : <p className="loading-text">Loading...</p>}
              </div>
            </div>

            {loading && <div className="loading-overlay"><div className="spinner"></div><p className="loading-text">Running CVaR optimization for {steps} hours...</p></div>}

            {/* KPIs */}
            {metrics && !loading && (<>
              <div className="section-title">Key Performance Indicators</div>
              <div className="kpi-grid">
                <div className="kpi-card"><div className="kpi-icon profit"><DollarSign size={22} /></div><div className="kpi-content"><h3>Total Profit</h3><p className="kpi-value">{inr(metrics.total_profit)}</p><p className="kpi-sub">over {steps} hours</p></div></div>
                <div className="kpi-card"><div className="kpi-icon daily"><TrendingUp size={22} /></div><div className="kpi-content"><h3>Avg Daily Profit</h3><p className="kpi-value">{inr(metrics.avg_daily_profit)}</p><p className="kpi-sub">per day</p></div></div>
                <div className="kpi-card"><div className="kpi-icon cycles"><Battery size={22} /></div><div className="kpi-content"><h3>Total Cycles</h3><p className="kpi-value">{metrics.total_cycles.toFixed(1)}</p><p className="kpi-sub">{inr(metrics.profit_per_cycle)} per cycle</p></div></div>
                <div className="kpi-card"><div className="kpi-icon util"><Activity size={22} /></div><div className="kpi-content"><h3>Utilization</h3><p className="kpi-value">{pct(metrics.utilization_rate)}</p><p className="kpi-sub">active hours</p></div></div>
                <div className="kpi-card"><div className="kpi-icon payback"><Clock size={22} /></div><div className="kpi-content"><h3>Payback</h3><p className="kpi-value">{metrics.payback_years > 99 ? '—' : metrics.payback_years.toFixed(1) + ' yrs'}</p><p className="kpi-sub">CAPEX recovery</p></div></div>
                <div className="kpi-card"><div className="kpi-icon roi"><PieChart size={22} /></div><div className="kpi-content"><h3>Annual ROI</h3><p className="kpi-value">{metrics.roi_annual_pct.toFixed(1)}%</p><p className="kpi-sub">return on investment</p></div></div>
              </div>
            </>)}

            {/* Charts */}
            {simulationData?.steps?.length > 0 && !loading && (<>
              <div className="section-title">Simulation Charts</div>
              <div className="charts-grid">
                <div className="chart-card full-width">
                  <h2>Market Price & Battery Operation</h2>
                  <Plot data={[
                    { x: simulationData.steps.map(s => s.step_index), y: simulationData.steps.map(s => s.price), type: 'scatter', mode: 'lines', name: 'Actual Price', line: { color: '#5b8abe', width: 1.5 } },
                    { x: simulationData.steps.map(s => s.step_index), y: simulationData.steps.map(s => s.forecast_price), type: 'scatter', mode: 'lines', name: 'Forecast', line: { color: '#c9952a', width: 1.5, dash: 'dash' } },
                    { x: simulationData.steps.map(s => s.step_index), y: simulationData.steps.map(s => s.soc), type: 'scatter', mode: 'lines', name: 'SOC', yaxis: 'y2', line: { color: '#3a9e6e', width: 2, dash: 'dot' } },
                    { x: simulationData.steps.map(s => s.step_index), y: simulationData.steps.map(s => s.battery_power), type: 'bar', name: 'Power', yaxis: 'y2', marker: { color: simulationData.steps.map(s => s.battery_power >= 0 ? 'rgba(201,68,68,0.5)' : 'rgba(58,158,110,0.5)') } },
                  ]} layout={darkLayout({ height: 420, yaxis: { title: 'Price (₹/kWh)', gridcolor: chartColors.grid, tickfont: { color: chartColors.tick } }, yaxis2: { title: 'Power/SOC', overlaying: 'y', side: 'right', gridcolor: chartColors.grid, tickfont: { color: chartColors.tick } }, legend: { orientation: 'h', y: 1.12, font: { color: chartColors.font } }, margin: { l: 55, r: 55, t: 20, b: 45 } })} useResizeHandler={true} style={{ width: "100%", height: "100%" }} config={{ displayModeBar: false }} />
                </div>

                <div className="chart-card">
                  <h2>Cumulative Profit</h2>
                  <Plot data={[{ x: simulationData.steps.map(s => s.step_index), y: simulationData.steps.reduce((acc, s) => { acc.push((acc.length > 0 ? acc[acc.length-1] : 0) + s.profit); return acc }, []), type: 'scatter', mode: 'lines', fill: 'tozeroy', name: 'Cum. Profit', line: { color: '#3a9e6e', width: 2 }, fillcolor: 'rgba(58,158,110,0.08)' }]} layout={darkLayout({ height: 300, yaxis: { title: 'Profit (₹)', gridcolor: chartColors.grid, tickfont: { color: chartColors.tick } }, xaxis: { title: 'Hour', gridcolor: chartColors.grid, tickfont: { color: chartColors.tick } }, margin: { l: 60, r: 20, t: 10, b: 45 } })} useResizeHandler={true} style={{ width: "100%", height: "100%" }} config={{ displayModeBar: false }} />
                </div>

                {metrics && (
                  <div className="chart-card">
                    <h2>Revenue Breakdown</h2>
                    <Plot data={[{ values: [Math.abs(metrics.total_energy_revenue || 0), Math.abs(metrics.total_degradation_cost || 0), Math.abs(metrics.total_deviation_penalty || 0)], labels: ['Energy Revenue', 'Degradation', 'Deviation Penalty'], type: 'pie', hole: 0.45, marker: { colors: ['#3a9e6e', '#c94444', '#c9952a'] }, textinfo: 'label+percent', textposition: 'outside', textfont: { color: chartColors.font } }]} layout={{ autosize: true, height: 300, margin: { l: 20, r: 20, t: 10, b: 10 }, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', font: { family: 'Inter', size: 11, color: chartColors.font }, showlegend: false }} useResizeHandler={true} style={{ width: "100%", height: "100%" }} config={{ displayModeBar: false }} />
                  </div>
                )}

                {buildHeatmapData() && (
                  <div className="chart-card full-width">
                    <h2>Profit Heatmap (Day × Hour)</h2>
                    <Plot data={[buildHeatmapData()]} layout={darkLayout({ height: 280, xaxis: { title: 'Hour of Day', dtick: 1, gridcolor: chartColors.grid, tickfont: { color: chartColors.tick } }, yaxis: { title: '', gridcolor: chartColors.grid, tickfont: { color: chartColors.tick } }, margin: { l: 60, r: 20, t: 10, b: 50 } })} useResizeHandler={true} style={{ width: "100%", height: "100%" }} config={{ displayModeBar: false }} />
                  </div>
                )}
              </div>
            </>)}

            {/* Baseline */}
            {baseline && !loading && (<>
              <div className="section-title">Strategy Comparison</div>
              <div className="baseline-grid">
                {[{ data: baseline.optimized, cls: 'optimized' }, { data: baseline.naive, cls: '' }, { data: baseline.no_storage, cls: '' }].map(({ data, cls }) => (
                  <div className={`baseline-card ${cls}`} key={data.strategy}>
                    <h3>{data.strategy}</h3>
                    <p className={`baseline-profit ${data.total_profit > 0 ? 'positive' : data.total_profit < 0 ? 'negative' : 'zero'}`}>{inr(data.total_profit)}</p>
                    <div className="baseline-stats">
                      <div className="baseline-stat"><span className="label">Cycles</span><span className="value">{data.total_cycles.toFixed(1)}</span></div>
                      <div className="baseline-stat"><span className="label">Sharpe</span><span className="value">{data.sharpe_ratio.toFixed(3)}</span></div>
                      <div className="baseline-stat"><span className="label">Util.</span><span className="value">{pct(data.utilization_rate)}</span></div>
                    </div>
                  </div>
                ))}
              </div>
            </>)}
          </div>
        )}

        {/* ═══════════ HISTORY TAB ═══════════ */}
        {activeTab === 'history' && (
          <div className="history-content">
            <div className="section-title">Trade Execution History</div>
            <div className="history-card">
              {trades.length > 0 ? (
                <table className="history-table">
                  <thead>
                    <tr><th>Order ID</th><th>Side</th><th>Qty (kWh)</th><th>Price (₹/kWh)</th><th>Fees</th><th>Net (₹)</th><th>Time</th></tr>
                  </thead>
                  <tbody>
                    {trades.map(t => (
                      <tr key={t.id} className={(t.side||'').toLowerCase()}>
                        <td>#{t.order_id}</td>
                        <td><span className={`ob-side ${(t.side||'').toLowerCase()}`}>{t.side}</span></td>
                        <td>{(t.quantity_kwh||0).toFixed(0)}</td>
                        <td>₹{(t.price_inr||0).toFixed(4)}</td>
                        <td>₹{(t.fees_inr||0).toFixed(2)}</td>
                        <td className={(t.net_amount_inr||0) >= 0 ? 'profit-positive' : 'profit-negative'}>
                          {(t.net_amount_inr||0) >= 0 ? '+' : ''}₹{(t.net_amount_inr||0).toFixed(2)}
                        </td>
                        <td>{t.executed_at ? new Date(t.executed_at).toLocaleString() : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <div className="empty-state"><BarChart3 size={36} /><p>No trades executed yet.</p></div>}
            </div>

            <div className="section-title">Simulation History</div>
            <div className="history-card">
              {history.length > 0 ? (
                <table className="history-table">
                  <thead><tr><th>Run #</th><th>Date</th><th>Profit</th><th>Steps</th><th></th></tr></thead>
                  <tbody>
                    {history.map(run => (
                      <tr key={run.id}>
                        <td>#{run.id}</td>
                        <td>{new Date(run.timestamp).toLocaleString()}</td>
                        <td className={run.total_profit >= 0 ? 'profit-positive' : 'profit-negative'}>{inr(run.total_profit)}</td>
                        <td>{run.steps_count || run.steps?.length || '—'}</td>
                        <td>
                          <button className="btn-view" onClick={() => { loadRun(run.id); setActiveTab('analytics') }}>View</button>
                          <button className="btn-export-sm" onClick={() => exportCSV(run.id)}>CSV</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <div className="empty-state"><BarChart3 size={36} /><p>No simulations yet.</p></div>}
            </div>
          </div>
        )}

        {/* ═══════════ SETTINGS TAB ═══════════ */}
        {activeTab === 'settings' && (
          <div className="settings-content">
            <div className="section-title">Platform Configuration</div>
            <div className="info-grid">
              <div className="info-card">
                <div className="info-card-header">
                  <div className="info-card-icon blue"><Settings size={18} /></div>
                  <h2>Trading Parameters</h2>
                </div>
                <div className="info-grid-inner">
                  <div className="info-item"><span className="label">Trading Mode</span><span className="value">SIMULATED</span></div>
                  <div className="info-item"><span className="label">Speed</span><span className="value">{tradingStatus?.speed_multiplier || 60}x</span></div>
                  <div className="info-item"><span className="label">Max Order</span><span className="value">{riskLimits?.max_order_size_kwh || 1000} kWh</span></div>
                  <div className="info-item"><span className="label">Daily Loss Limit</span><span className="value">₹{(riskLimits?.daily_loss_limit_inr || 50000).toLocaleString()}</span></div>
                  <div className="info-item"><span className="label">Auto-Halting</span><span className="value">Enabled</span></div>
                  <div className="info-item"><span className="label">Default Admin</span><span className="value">admin / admin123</span></div>
                </div>
              </div>
              <div className="info-card">
                <div className="info-card-header">
                  <div className="info-card-icon green"><Database size={18} /></div>
                  <h2>System Status</h2>
                </div>
                <div className="info-grid-inner">
                  <div className="info-item"><span className="label">Market Feed</span><span className="value"><span className="status-indicator"><span className={`status-dot ${marketConnected ? 'active' : 'inactive'}`}></span>{marketConnected ? 'Connected' : 'Disconnected'}</span></span></div>
                  <div className="info-item"><span className="label">Trading WS</span><span className="value"><span className="status-indicator"><span className={`status-dot ${tradingConnected ? 'active' : 'inactive'}`}></span>{tradingConnected ? 'Connected' : 'Disconnected'}</span></span></div>
                  <div className="info-item"><span className="label">Auto-Trading</span><span className="value"><span className="status-indicator"><span className={`status-dot ${tradingStatus?.is_active ? 'active' : 'stopped'}`}></span>{tradingStatus?.is_active ? 'Active' : 'Stopped'}</span></span></div>
                  <div className="info-item"><span className="label">Database</span><span className="value">SQLite</span></div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
