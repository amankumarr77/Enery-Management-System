import { Zap, Wifi, WifiOff, Sun, Moon, ChevronUp, ChevronDown } from 'lucide-react'

export default function Navbar({ activeTab, onTabChange, marketConnected, tradingConnected, currentPrice, priceDirection, theme, onToggleTheme }) {
  const tabs = [
    { id: 'trading', label: 'Live Trading' },
    { id: 'analytics', label: 'Analytics' },
    { id: 'history', label: 'Order History' },
    { id: 'settings', label: 'Settings' },
  ]

  return (
    <header className="navbar">
      <div className="nav-left">
        <div className="nav-logo">
          <div className="nav-logo-icon"><Zap size={20} /></div>
          <div className="nav-logo-text">
            <span className="nav-brand">EMSJB</span>
            <span className="nav-subtitle">Energy Trading Platform</span>
          </div>
        </div>

        <nav className="nav-tabs">
          {tabs.map(tab => (
            <button
              key={tab.id}
              className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => onTabChange(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="nav-right">
        {/* Live Price Ticker */}
        {currentPrice && (
          <div className={`nav-price-ticker ${priceDirection || ''}`}>
            <span className="nav-price-label">IEX RTM</span>
            <span className="nav-price-value">
              {'\u20B9'}{currentPrice.price_inr_kwh?.toFixed(4)}
            </span>
            <span className={`nav-price-change ${(currentPrice.change_pct || 0) >= 0 ? 'up' : 'down'}`}>
              {(currentPrice.change_pct || 0) >= 0 ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              {Math.abs(currentPrice.change_pct || 0).toFixed(2)}%
            </span>
          </div>
        )}

        {/* Connection Status */}
        <div className="nav-status-group">
          <div className={`nav-status-pill ${marketConnected ? 'connected' : 'disconnected'}`}>
            {marketConnected ? <Wifi size={12} /> : <WifiOff size={12} />}
            <span>Market</span>
          </div>
          <div className={`nav-status-pill ${tradingConnected ? 'connected' : 'disconnected'}`}>
            {tradingConnected ? <Wifi size={12} /> : <WifiOff size={12} />}
            <span>Trading</span>
          </div>
        </div>

        {/* Mode Badge */}
        <div className="nav-mode-badge">
          <span className="mode-dot"></span>
          SIMULATED
        </div>

        {/* Theme Toggle */}
        <button className="theme-toggle" onClick={onToggleTheme} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
    </header>
  )
}
