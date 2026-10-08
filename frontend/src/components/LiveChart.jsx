import Plot from 'react-plotly.js'

export default function LiveChart({ priceHistory, forecast, theme }) {
  if (!priceHistory || priceHistory.length === 0) {
    return (
      <div className="live-chart-card">
        <h2>Live Market Price</h2>
        <div className="chart-empty">Waiting for market data...</div>
      </div>
    )
  }

  const isDark = theme === 'dark'
  const chartColors = {
    grid: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)',
    tick: isDark ? '#8694a8' : '#4b5c72',
    line: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
    font: isDark ? '#8694a8' : '#4b5c72',
  }

  const timestamps = priceHistory.map(t => t.timestamp)
  const prices = priceHistory.map(t => t.price_inr_kwh)

  // Forecast data
  const forecastTraces = []
  if (forecast && forecast.forecasts && forecast.forecasts.length > 0) {
    const lastTs = timestamps[timestamps.length - 1]
    const baseDate = new Date(lastTs)

    const fTimes = forecast.forecasts.map((f, i) => {
      const d = new Date(baseDate)
      d.setHours(d.getHours() + i + 1)
      return d.toISOString()
    })

    forecastTraces.push({
      x: fTimes,
      y: forecast.forecasts.map(f => f.price_forecast),
      type: 'scatter',
      mode: 'lines',
      name: 'Forecast',
      line: { color: '#c9952a', width: 2, dash: 'dash' },
    })

    // Confidence band
    forecastTraces.push({
      x: [...fTimes, ...fTimes.slice().reverse()],
      y: [
        ...forecast.forecasts.map(f => f.price_upper),
        ...forecast.forecasts.map(f => f.price_lower).reverse(),
      ],
      type: 'scatter',
      fill: 'toself',
      fillcolor: 'rgba(201,149,42,0.06)',
      line: { color: 'transparent' },
      name: '95% Band',
      showlegend: true,
      hoverinfo: 'skip',
    })
  }

  return (
    <div className="live-chart-card">
      <h2>Live Market Price & Forecast</h2>
      <Plot
        data={[
          {
            x: timestamps,
            y: prices,
            type: 'scatter',
            mode: 'lines',
            name: 'Market Price',
            line: { color: '#5b8abe', width: 2 },
            fill: 'tozeroy',
            fillcolor: 'rgba(91,138,190,0.06)',
          },
          ...forecastTraces,
        ]}
        layout={{
          autosize: true,
          height: 380,
          xaxis: {
            gridcolor: chartColors.grid,
            tickcolor: chartColors.tick,
            tickfont: { color: chartColors.tick },
            linecolor: chartColors.line,
          },
          yaxis: {
            title: { text: 'Price (\u20B9/kWh)', font: { color: chartColors.font, size: 11 } },
            gridcolor: chartColors.grid,
            tickcolor: chartColors.tick,
            tickfont: { color: chartColors.tick },
            linecolor: chartColors.line,
          },
          legend: {
            orientation: 'h',
            y: 1.12,
            font: { color: chartColors.font, size: 11 },
          },
          margin: { l: 60, r: 20, t: 10, b: 45 },
          plot_bgcolor: 'transparent',
          paper_bgcolor: 'transparent',
          font: { family: 'Inter', size: 11 },
        }}
        useResizeHandler={true}
        style={{ width: '100%', height: '100%' }}
        config={{ displayModeBar: false }}
      />
    </div>
  )
}
