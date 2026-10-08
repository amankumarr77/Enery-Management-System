import { TrendingUp, TrendingDown, Battery, DollarSign, ArrowUpRight, ArrowDownRight } from 'lucide-react'

export default function PositionTracker({ position, trades }) {
  if (!position) {
    return (
      <div className="position-card">
        <h2>Position & P&L</h2>
        <div className="pos-empty">No position data yet.</div>
      </div>
    )
  }

  const pnl = position.total_pnl_inr || 0
  const realizedPnl = position.realized_pnl_inr || 0
  const unrealizedPnl = position.unrealized_pnl_inr || 0
  const isProfitable = pnl >= 0

  // Recent trades for mini-feed
  const recentTrades = (trades || []).slice(0, 8)

  return (
    <div className="position-card">
      <h2>Position & P&L</h2>

      {/* Total P&L Hero */}
      <div className={`pos-pnl-hero ${isProfitable ? 'profit' : 'loss'}`}>
        <div className="pos-pnl-label">Total P&L</div>
        <div className="pos-pnl-value">
          {isProfitable ? <ArrowUpRight size={24} /> : <ArrowDownRight size={24} />}
          <span>{isProfitable ? '' : '-'}₹{Math.abs(pnl).toFixed(2)}</span>
        </div>
      </div>

      {/* P&L Breakdown */}
      <div className="pos-stats-grid">
        <div className="pos-stat">
          <span className="pos-stat-label">Realized</span>
          <span className={`pos-stat-value ${realizedPnl >= 0 ? 'positive' : 'negative'}`}>
            ₹{realizedPnl.toFixed(2)}
          </span>
        </div>
        <div className="pos-stat">
          <span className="pos-stat-label">Unrealized</span>
          <span className={`pos-stat-value ${unrealizedPnl >= 0 ? 'positive' : 'negative'}`}>
            ₹{unrealizedPnl.toFixed(2)}
          </span>
        </div>
        <div className="pos-stat">
          <span className="pos-stat-label">Degradation</span>
          <span className="pos-stat-value negative">-₹{(position.degradation_cost_inr || 0).toFixed(2)}</span>
        </div>
        <div className="pos-stat">
          <span className="pos-stat-label">Avg Buy</span>
          <span className="pos-stat-value">₹{(position.avg_buy_price || 0).toFixed(4)}</span>
        </div>
        <div className="pos-stat">
          <span className="pos-stat-label">Avg Sell</span>
          <span className="pos-stat-value">₹{(position.avg_sell_price || 0).toFixed(4)}</span>
        </div>
        <div className="pos-stat">
          <span className="pos-stat-label">SOC</span>
          <span className="pos-stat-value">{(position.soc_pct || 0).toFixed(1)}%</span>
        </div>
      </div>

      {/* Volume Summary */}
      <div className="pos-volume">
        <div className="pos-vol-item buy">
          <TrendingDown size={14} />
          <span>Bought: {(position.total_bought_kwh || 0).toFixed(0)} kWh</span>
          <span className="pos-vol-val">₹{(position.total_bought_value_inr || 0).toFixed(2)}</span>
        </div>
        <div className="pos-vol-item sell">
          <TrendingUp size={14} />
          <span>Sold: {(position.total_sold_kwh || 0).toFixed(0)} kWh</span>
          <span className="pos-vol-val">₹{(position.total_sold_value_inr || 0).toFixed(2)}</span>
        </div>
      </div>

      {/* Recent Trades Feed */}
      {recentTrades.length > 0 && (
        <div className="pos-trades-feed">
          <h3>Recent Trades</h3>
          {recentTrades.map((t, i) => (
            <div key={t.id || i} className={`pos-trade-item ${(t.side || '').toLowerCase()}`}>
              <span className={`pos-trade-side ${(t.side || '').toLowerCase()}`}>{t.side}</span>
              <span>{(t.quantity_kwh || 0).toFixed(0)} kWh</span>
              <span>@ ₹{(t.price_inr || 0).toFixed(4)}</span>
              <span className={`pos-trade-net ${(t.net_amount_inr || 0) >= 0 ? 'positive' : 'negative'}`}>
                {(t.net_amount_inr || 0) >= 0 ? '+' : ''}₹{(t.net_amount_inr || 0).toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
