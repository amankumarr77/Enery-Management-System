import { X } from 'lucide-react'

export default function OrderBook({ orders, onCancel }) {
  if (!orders || orders.length === 0) {
    return (
      <div className="order-book-card">
        <h2>Order Book</h2>
        <div className="ob-empty">No orders yet. Place one from the trading panel.</div>
      </div>
    )
  }

  const statusColors = {
    PENDING: 'status-pending',
    FILLED: 'status-filled',
    PARTIAL: 'status-partial',
    CANCELLED: 'status-cancelled',
    REJECTED: 'status-rejected',
  }

  // Show most recent first, limit to 30
  const visible = orders.slice(0, 30)

  return (
    <div className="order-book-card">
      <div className="ob-header">
        <h2>Order Book</h2>
        <span className="ob-count">{orders.length} orders</span>
      </div>
      <div className="ob-table-wrap">
        <table className="ob-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Side</th>
              <th>Qty (kWh)</th>
              <th>Price</th>
              <th>Status</th>
              <th>Filled</th>
              <th>Strategy</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visible.map(order => (
              <tr key={order.id} className={`ob-row ${order.side?.toLowerCase()}`}>
                <td className="ob-id">#{order.id}</td>
                <td>
                  <span className={`ob-side ${order.side?.toLowerCase()}`}>
                    {order.side}
                  </span>
                </td>
                <td>{order.quantity_kwh?.toFixed(0)}</td>
                <td>
                  {order.limit_price_inr
                    ? `₹${order.limit_price_inr.toFixed(4)}`
                    : <span className="ob-market">MKT</span>
                  }
                </td>
                <td>
                  <span className={`ob-status ${statusColors[order.status] || ''}`}>
                    {order.status}
                  </span>
                </td>
                <td>
                  {order.filled_quantity_kwh > 0
                    ? `${order.filled_quantity_kwh.toFixed(0)} @ ₹${order.filled_avg_price?.toFixed(4)}`
                    : '—'
                  }
                </td>
                <td className="ob-strategy">{order.strategy?.replace('AUTO_', '')}</td>
                <td>
                  {order.status === 'PENDING' && (
                    <button className="ob-cancel-btn" onClick={() => onCancel(order.id)} title="Cancel">
                      <X size={14} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
