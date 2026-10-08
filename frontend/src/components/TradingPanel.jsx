import { useState } from 'react'
import { ShoppingCart, TrendingUp, TrendingDown, Power, PowerOff, Zap } from 'lucide-react'

export default function TradingPanel({ currentPrice, priceDirection, tradingStatus, position, onPlaceOrder, onStartTrading, onStopTrading }) {
  const [side, setSide] = useState('BUY')
  const [quantity, setQuantity] = useState(500)
  const [orderType, setOrderType] = useState('MARKET') // MARKET or LIMIT
  const [limitPrice, setLimitPrice] = useState('')

  const price = currentPrice?.price_inr_kwh || 0
  const isAutoTrading = tradingStatus?.is_active || false

  const handleSubmit = async () => {
    const orderData = {
      side,
      market: 'RTM',
      quantity_kwh: quantity,
      limit_price_inr: orderType === 'LIMIT' ? parseFloat(limitPrice) : null,
      strategy: 'MANUAL',
    }
    const res = await onPlaceOrder(orderData)
    if (res && res.status === 'REJECTED') {
      alert(`Order Rejected: ${res.notes}`)
    }
  }

  const estimatedCost = quantity * price
  const socPct = position?.soc_pct || 0

  return (
    <div className="trading-panel">
      {/* Live Price Display */}
      <div className="tp-price-display">
        <div className="tp-price-header">
          <span className="tp-market-label">IEX Real-Time Market</span>
          <span className={`tp-live-dot ${currentPrice ? 'active' : ''}`}></span>
        </div>
        <div className={`tp-current-price ${priceDirection || ''}`}>
          <span className="tp-currency">₹</span>
          <span className="tp-price-value">{price.toFixed(4)}</span>
          <span className="tp-price-unit">/kWh</span>
        </div>
        {currentPrice && (
          <div className={`tp-price-change ${(currentPrice.change_pct || 0) >= 0 ? 'positive' : 'negative'}`}>
            {(currentPrice.change_pct || 0) >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            <span>{Math.abs(currentPrice.change_pct || 0).toFixed(2)}%</span>
          </div>
        )}
      </div>

      {/* Auto-Trading Toggle */}
      <div className="tp-auto-section">
        <div className="tp-auto-header">
          <Zap size={16} />
          <span>Auto-Trading (CVaR)</span>
        </div>
        <button
          className={`tp-auto-toggle ${isAutoTrading ? 'active' : ''}`}
          onClick={() => isAutoTrading ? onStopTrading() : onStartTrading()}
        >
          {isAutoTrading ? <PowerOff size={16} /> : <Power size={16} />}
          {isAutoTrading ? 'STOP' : 'START'}
        </button>
        {isAutoTrading && tradingStatus && (
          <div className="tp-auto-stats">
            <div className="tp-auto-stat">
              <span>Orders</span>
              <span className="value">{tradingStatus.total_orders}</span>
            </div>
            <div className="tp-auto-stat">
              <span>Trades</span>
              <span className="value">{tradingStatus.total_trades}</span>
            </div>
            <div className="tp-auto-stat">
              <span>P&L</span>
              <span className={`value ${(tradingStatus.session_pnl_inr || 0) >= 0 ? 'positive' : 'negative'}`}>
                {(tradingStatus.session_pnl_inr || 0) >= 0 ? '' : '-'}₹{Math.abs(tradingStatus.session_pnl_inr || 0).toFixed(2)}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Manual Order Entry */}
      <div className="tp-order-section">
        <div className="tp-side-toggle">
          <button
            className={`tp-side-btn buy ${side === 'BUY' ? 'active' : ''}`}
            onClick={() => setSide('BUY')}
          >
            BUY (Charge)
          </button>
          <button
            className={`tp-side-btn sell ${side === 'SELL' ? 'active' : ''}`}
            onClick={() => setSide('SELL')}
          >
            SELL (Discharge)
          </button>
        </div>

        <div className="tp-order-type">
          <button
            className={`tp-type-btn ${orderType === 'MARKET' ? 'active' : ''}`}
            onClick={() => setOrderType('MARKET')}
          >
            Market
          </button>
          <button
            className={`tp-type-btn ${orderType === 'LIMIT' ? 'active' : ''}`}
            onClick={() => setOrderType('LIMIT')}
          >
            Limit
          </button>
        </div>

        <div className="tp-field">
          <label>Quantity (kWh)</label>
          <div className="tp-qty-input">
            <input
              type="number"
              value={quantity}
              onChange={e => setQuantity(Math.max(0, parseFloat(e.target.value) || 0))}
              min="0"
              max="1000"
              step="50"
            />
            <div className="tp-qty-presets">
              {[100, 250, 500, 1000].map(v => (
                <button key={v} onClick={() => setQuantity(v)} className={quantity === v ? 'active' : ''}>{v}</button>
              ))}
            </div>
          </div>
        </div>

        {orderType === 'LIMIT' && (
          <div className="tp-field">
            <label>Limit Price (₹/kWh)</label>
            <input
              type="number"
              value={limitPrice}
              onChange={e => setLimitPrice(e.target.value)}
              step="0.001"
              placeholder={price.toFixed(4)}
              className="tp-limit-input"
            />
          </div>
        )}

        <div className="tp-estimate">
          <span>Est. Value</span>
          <span className="tp-estimate-value">₹{estimatedCost.toFixed(2)}</span>
        </div>

        <button
          className={`tp-submit-btn ${side.toLowerCase()}`}
          onClick={handleSubmit}
          disabled={quantity <= 0}
        >
          <ShoppingCart size={16} />
          {side === 'BUY' ? 'BUY' : 'SELL'} {quantity} kWh
        </button>
      </div>

      {/* Battery SOC Gauge */}
      <div className="tp-soc-section">
        <div className="tp-soc-header">
          <span>Battery SOC</span>
          <span className="tp-soc-value">{socPct.toFixed(1)}%</span>
        </div>
        <div className="tp-soc-bar">
          <div
            className="tp-soc-fill"
            style={{ width: `${Math.min(100, socPct)}%` }}
          />
        </div>
        <div className="tp-soc-labels">
          <span>0 kWh</span>
          <span>{position?.soc_kwh?.toFixed(0) || 0} kWh</span>
          <span>4000 kWh</span>
        </div>
      </div>
    </div>
  )
}
