import { Shield, AlertTriangle, Ban } from 'lucide-react'

export default function RiskPanel({ riskLimits, alerts, onDismissAlert }) {
  return (
    <div className="risk-panel-card">
      <h2><Shield size={16} /> Risk Management</h2>

      {/* Risk Limits */}
      {riskLimits && (
        <div className="risk-limits">
          {/* Daily Loss Limit */}
          <div className="risk-limit-item">
            <div className="risk-limit-header">
              <span>Daily Loss Limit</span>
              <span className={`risk-limit-value ${riskLimits.loss_limit_utilization_pct > 80 ? 'danger' : ''}`}>
                {riskLimits.loss_limit_utilization_pct.toFixed(1)}%
              </span>
            </div>
            <div className="risk-bar">
              <div
                className={`risk-bar-fill ${riskLimits.loss_limit_utilization_pct > 80 ? 'danger' : riskLimits.loss_limit_utilization_pct > 50 ? 'warning' : 'safe'}`}
                style={{ width: `${Math.min(100, riskLimits.loss_limit_utilization_pct)}%` }}
              />
            </div>
            <div className="risk-limit-detail">
              Daily P&L: <span className={riskLimits.current_daily_pnl >= 0 ? 'positive' : 'negative'}>
                ₹{riskLimits.current_daily_pnl.toFixed(2)}
              </span>
              / Limit: ₹{riskLimits.daily_loss_limit_inr.toFixed(0)}
            </div>
          </div>

          {/* Position Utilization */}
          <div className="risk-limit-item">
            <div className="risk-limit-header">
              <span>Position Utilization</span>
              <span className="risk-limit-value">{riskLimits.position_utilization_pct.toFixed(1)}%</span>
            </div>
            <div className="risk-bar">
              <div
                className={`risk-bar-fill ${riskLimits.position_utilization_pct > 90 ? 'danger' : 'safe'}`}
                style={{ width: `${Math.min(100, riskLimits.position_utilization_pct)}%` }}
              />
            </div>
            <div className="risk-limit-detail">
              SOC: {riskLimits.current_position_kwh.toFixed(0)} kWh / Max: {riskLimits.max_position_kwh.toFixed(0)} kWh
            </div>
          </div>

          {/* Max Order Size */}
          <div className="risk-limit-item">
            <div className="risk-limit-header">
              <span>Max Order Size</span>
              <span className="risk-limit-value">{riskLimits.max_order_size_kwh.toFixed(0)} kWh</span>
            </div>
          </div>

          {/* Trading Halt */}
          {riskLimits.is_trading_halted && (
            <div className="risk-halt-banner">
              <Ban size={16} />
              <span>Trading HALTED: {riskLimits.halt_reason}</span>
            </div>
          )}
        </div>
      )}

      {/* Alert Feed */}
      {alerts && alerts.length > 0 && (
        <div className="risk-alerts">
          <h3><AlertTriangle size={14} /> Alerts</h3>
          {alerts.slice(0, 5).map(alert => (
            <div key={alert.id} className={`risk-alert ${alert.level || 'info'}`}>
              <div className="risk-alert-content">
                <strong>{alert.title}</strong>
                <p>{alert.message}</p>
              </div>
              <button className="risk-alert-dismiss" onClick={() => onDismissAlert(alert.id)}>×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
