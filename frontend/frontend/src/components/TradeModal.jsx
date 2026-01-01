import { useState } from 'react'

export function TradeModal({ player, action, onClose, onTrade, formatPrice }) {
  const [shares, setShares] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const totalCost = shares * player.price

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await onTrade({
        player_id: player.id,
        action,
        shares,
      })
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{action === 'buy' ? 'Buy' : 'Sell'} Shares</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        
        <div className="modal-body">
          <div className="player-info">
            <h3>{player.name}</h3>
            <p className="current-price">Current Price: {formatPrice(player.price)}</p>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="shares">Number of Shares</label>
              <input
                type="number"
                id="shares"
                min="1"
                max="1000"
                value={shares}
                onChange={(e) => setShares(Math.max(1, parseInt(e.target.value) || 1))}
              />
            </div>

            <div className="trade-summary">
              <div className="summary-row">
                <span>Price per share</span>
                <span>{formatPrice(player.price)}</span>
              </div>
              <div className="summary-row">
                <span>Shares</span>
                <span>×{shares}</span>
              </div>
              <div className="summary-row total">
                <span>Total {action === 'buy' ? 'Cost' : 'Value'}</span>
                <span>{formatPrice(totalCost)}</span>
              </div>
            </div>

            {error && <div className="error-message">{error}</div>}

            <div className="modal-actions">
              <button type="button" className="btn btn-cancel" onClick={onClose}>
                Cancel
              </button>
              <button
                type="submit"
                className={`btn ${action === 'buy' ? 'btn-buy' : 'btn-sell'}`}
                disabled={loading}
              >
                {loading ? 'Processing...' : `Confirm ${action === 'buy' ? 'Buy' : 'Sell'}`}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
