import { useState, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'

function App() {
  const [players, setPlayers] = useState({})
  const [priceChanges, setPriceChanges] = useState({})
  
  // Connect to WebSocket for live price updates
  const { isConnected, lastMessage, error } = useWebSocket('ws://localhost:8000/ws/prices')

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage) return

    // Handle snapshot (initial data)
    if (lastMessage.type === 'snapshot' && lastMessage.prices) {
      const initialPlayers = {}
      Object.entries(lastMessage.prices).forEach(([id, price]) => {
        initialPlayers[id] = {
          id,
          name: `Player ${id}`,
          price,
          goals: 0,
          assists: 0,
          minutes: 0,
        }
      })
      setPlayers(initialPlayers)
    }

    // Handle price update
    if (lastMessage.type === 'update' || lastMessage.player_id) {
      const playerId = lastMessage.player_id
      const newPrice = lastMessage.new_price || lastMessage.price

      setPlayers(prev => {
        const oldPrice = prev[playerId]?.price || newPrice
        const change = newPrice - oldPrice

        // Track price change for animation
        if (change !== 0) {
          setPriceChanges(pc => ({
            ...pc,
            [playerId]: { change, timestamp: Date.now() }
          }))
        }

        return {
          ...prev,
          [playerId]: {
            ...prev[playerId],
            id: playerId,
            name: prev[playerId]?.name || `Player ${playerId}`,
            price: newPrice,
            goals: lastMessage.goals ?? prev[playerId]?.goals ?? 0,
            assists: lastMessage.assists ?? prev[playerId]?.assists ?? 0,
            minutes: lastMessage.minutes ?? prev[playerId]?.minutes ?? 0,
          }
        }
      })
    }
  }, [lastMessage])

  // Clear price change indicators after 2 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now()
      setPriceChanges(prev => {
        const updated = {}
        Object.entries(prev).forEach(([id, data]) => {
          if (now - data.timestamp < 2000) {
            updated[id] = data
          }
        })
        return updated
      })
    }, 500)
    return () => clearInterval(interval)
  }, [])

  const handleBuy = (playerId) => {
    alert(`Buy shares of Player ${playerId} - Coming soon!`)
  }

  const handleSell = (playerId) => {
    alert(`Sell shares of Player ${playerId} - Coming soon!`)
  }

  const formatPrice = (price) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(price)
  }

  const playerList = Object.values(players)

  return (
    <div className="app">
      <header>
        <h1>⚽ Stat Trader</h1>
        <p style={{ color: '#888', marginTop: '8px' }}>
          Real-time player trading platform
        </p>
        <div className={`status ${isConnected ? 'connected' : 'disconnected'}`}>
          <span className="status-dot"></span>
          {isConnected ? 'Live' : 'Connecting...'}
        </div>
      </header>

      {error && (
        <div className="error">
          <p>⚠️ {error}</p>
          <p style={{ marginTop: '10px', fontSize: '0.9rem' }}>
            Make sure the backend server is running on port 8000
          </p>
        </div>
      )}

      {!error && playerList.length === 0 && (
        <div className="loading">
          <p>Waiting for player data...</p>
          <p style={{ marginTop: '10px', fontSize: '0.9rem', color: '#666' }}>
            Prices update in real-time based on live performance
          </p>
        </div>
      )}

      <div className="players-grid">
        {playerList.map(player => {
          const priceChange = priceChanges[player.id]
          return (
            <div key={player.id} className="player-card">
              <h3>{player.name}</h3>
              <div className="price">
                {formatPrice(player.price)}
                {priceChange && (
                  <span className={`price-change ${priceChange.change > 0 ? 'up' : 'down'}`}>
                    {priceChange.change > 0 ? '▲' : '▼'} {formatPrice(Math.abs(priceChange.change))}
                  </span>
                )}
              </div>
              <div className="stats">
                <div className="stat-item">
                  <span>Goals</span>
                  <span className="stat-value">{player.goals}</span>
                </div>
                <div className="stat-item">
                  <span>Assists</span>
                  <span className="stat-value">{player.assists}</span>
                </div>
                <div className="stat-item">
                  <span>Minutes</span>
                  <span className="stat-value">{player.minutes}</span>
                </div>
                <div className="stat-item">
                  <span>Status</span>
                  <span className="stat-value" style={{ color: '#00ff88' }}>Active</span>
                </div>
              </div>
              <div className="actions">
                <button className="btn btn-buy" onClick={() => handleBuy(player.id)}>
                  Buy
                </button>
                <button className="btn btn-sell" onClick={() => handleSell(player.id)}>
                  Sell
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default App
