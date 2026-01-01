import { useState, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { TradeModal } from './components/TradeModal'
import { executeTrade, fetchWallet } from './api'

const USER_ID = 'demo-user-1'

function App() {
  const [players, setPlayers] = useState({})
  const [priceChanges, setPriceChanges] = useState({})
  const [wallet, setWallet] = useState({ balance: 10000, holdings: {} })
  const [tradeModal, setTradeModal] = useState(null)
  const [notification, setNotification] = useState(null)

  const { isConnected, lastMessage, error } = useWebSocket('ws://localhost:8000/ws/prices')

  useEffect(() => {
    fetchWallet(USER_ID).then(setWallet).catch(() => setWallet({ balance: 10000, holdings: {} }))
  }, [])

  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.type === 'snapshot' && lastMessage.prices) {
      const initialPlayers = {}
      Object.entries(lastMessage.prices).forEach(([id, price]) => {
        initialPlayers[id] = { id, name: 'Player ' + id, price, goals: 0, assists: 0, minutes: 0 }
      })
      setPlayers(initialPlayers)
    }
    if (lastMessage.type === 'update' || lastMessage.player_id) {
      const playerId = lastMessage.player_id
      const newPrice = lastMessage.new_price || lastMessage.price
      setPlayers(prev => {
        const oldPrice = prev[playerId]?.price || newPrice
        const change = newPrice - oldPrice
        if (change !== 0) {
          setPriceChanges(pc => ({ ...pc, [playerId]: { change, timestamp: Date.now() } }))
        }
        return {
          ...prev,
          [playerId]: {
            ...prev[playerId], id: playerId, name: prev[playerId]?.name || 'Player ' + playerId,
            price: newPrice, goals: lastMessage.goals ?? prev[playerId]?.goals ?? 0,
            assists: lastMessage.assists ?? prev[playerId]?.assists ?? 0,
            minutes: lastMessage.minutes ?? prev[playerId]?.minutes ?? 0,
          }
        }
      })
    }
  }, [lastMessage])

  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now()
      setPriceChanges(prev => {
        const updated = {}
        Object.entries(prev).forEach(([id, data]) => { if (now - data.timestamp < 2000) updated[id] = data })
        return updated
      })
    }, 500)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (notification) { const timer = setTimeout(() => setNotification(null), 3000); return () => clearTimeout(timer) }
  }, [notification])

  const handleTrade = async ({ player_id, action, shares }) => {
    const result = await executeTrade({ user_id: USER_ID, player_id, action, shares })
    setWallet(prev => ({
      ...prev, balance: result.new_balance ?? prev.balance,
      holdings: { ...prev.holdings, [player_id]: (prev.holdings[player_id] || 0) + (action === 'buy' ? shares : -shares) }
    }))
    setNotification({ type: 'success', message: 'Successfully ' + (action === 'buy' ? 'bought' : 'sold') + ' ' + shares + ' share(s)' })
  }

  const openTradeModal = (player, action) => setTradeModal({ player, action })
  const formatPrice = (price) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(price)
  const playerList = Object.values(players)

  return (
    <div className="app">
      <header>
        <h1>Stat Trader</h1>
        <p style={{ color: '#888', marginTop: '8px' }}>Real-time player trading platform</p>
        <div className="header-info">
          <div className={'status ' + (isConnected ? 'connected' : 'disconnected')}>
            <span className="status-dot"></span>
            {isConnected ? 'Live' : 'Connecting...'}
          </div>
          <div className="wallet-info">{formatPrice(wallet.balance)}</div>
        </div>
      </header>

      {notification && <div className={'notification ' + notification.type}>{notification.message}</div>}

      {error && (
        <div className="error">
          <p>{error}</p>
          <p style={{ marginTop: '10px', fontSize: '0.9rem' }}>Make sure the backend server is running on port 8000</p>
        </div>
      )}

      {!error && playerList.length === 0 && (
        <div className="loading">
          <p>Waiting for player data...</p>
          <p style={{ marginTop: '10px', fontSize: '0.9rem', color: '#666' }}>Prices update in real-time based on live performance</p>
        </div>
      )}

      <div className="players-grid">
        {playerList.map(player => {
          const priceChange = priceChanges[player.id]
          const holdings = wallet.holdings[player.id] || 0
          return (
            <div key={player.id} className="player-card">
              <h3>{player.name}</h3>
              <div className="price">
                {formatPrice(player.price)}
                {priceChange && (
                  <span className={'price-change ' + (priceChange.change > 0 ? 'up' : 'down')}>
                    {priceChange.change > 0 ? '+' : ''}{formatPrice(priceChange.change)}
                  </span>
                )}
              </div>
              {holdings > 0 && <div className="holdings">You own: {holdings} share(s) ({formatPrice(holdings * player.price)})</div>}
              <div className="stats">
                <div className="stat-item"><span>Goals</span><span className="stat-value">{player.goals}</span></div>
                <div className="stat-item"><span>Assists</span><span className="stat-value">{player.assists}</span></div>
                <div className="stat-item"><span>Minutes</span><span className="stat-value">{player.minutes}</span></div>
                <div className="stat-item"><span>Status</span><span className="stat-value" style={{ color: '#00ff88' }}>Active</span></div>
              </div>
              <div className="actions">
                <button className="btn btn-buy" onClick={() => openTradeModal(player, 'buy')}>Buy</button>
                <button className="btn btn-sell" onClick={() => openTradeModal(player, 'sell')} disabled={holdings === 0}>Sell</button>
              </div>
            </div>
          )
        })}
      </div>

      {tradeModal && (
        <TradeModal player={tradeModal.player} action={tradeModal.action} onClose={() => setTradeModal(null)} onTrade={handleTrade} formatPrice={formatPrice} />
      )}
    </div>
  )
}

export default App
