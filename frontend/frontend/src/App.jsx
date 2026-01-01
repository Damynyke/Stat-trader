import { useState, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { TradeModal } from './components/TradeModal'
import { LoginPage, RegisterPage } from './components/AuthPages'
import { useAuth } from './context/AuthContext'
import { executeTrade, fetchWallet } from './api'

function App() {
  const { user, loading, logout, isAuthenticated } = useAuth()
  const [authMode, setAuthMode] = useState('login')
  const [players, setPlayers] = useState({})
  const [priceChanges, setPriceChanges] = useState({})
  const [wallet, setWallet] = useState({ balance: 10000, holdings: {} })
  const [tradeModal, setTradeModal] = useState(null)
  const [notification, setNotification] = useState(null)
  const [liveStatus, setLiveStatus] = useState({ running: false })

  const { isConnected, lastMessage, error } = useWebSocket(
    isAuthenticated ? 'ws://localhost:8000/ws/prices' : null
  )

  useEffect(() => {
    if (isAuthenticated && user) {
      fetchWallet(user.id).then(setWallet).catch(() => setWallet({ balance: 10000, holdings: {} }))
      checkLiveStatus()
    }
  }, [isAuthenticated, user])

  const checkLiveStatus = async () => {
    try {
      const res = await fetch('http://localhost:8000/live/status')
      const data = await res.json()
      setLiveStatus(data)
    } catch (e) { console.error(e) }
  }

  const toggleLiveFeed = async () => {
    try {
      const endpoint = liveStatus.running ? '/live/stop' : '/live/start'
      await fetch('http://localhost:8000' + endpoint, { method: 'POST' })
      setTimeout(checkLiveStatus, 500)
    } catch (e) { console.error(e) }
  }

  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.type === 'snapshot' && lastMessage.players) {
      const initialPlayers = {}
      lastMessage.players.forEach((p) => {
        initialPlayers[p.id] = { id: p.id, name: p.name || 'Player ' + p.id, price: p.price, goals: p.goals || 0, assists: p.assists || 0, minutes: 0 }
      })
      setPlayers(initialPlayers)
    }
    if (lastMessage.type === 'update' || lastMessage.player_id) {
      const playerId = lastMessage.player_id
      const newPrice = lastMessage.new_price || lastMessage.price
      setPlayers(prev => {
        const oldPrice = prev[playerId]?.price || newPrice
        const change = newPrice - oldPrice
        if (change !== 0) setPriceChanges(pc => ({ ...pc, [playerId]: { change, timestamp: Date.now() } }))
        return { ...prev, [playerId]: { ...prev[playerId], id: playerId, name: lastMessage.player_name || prev[playerId]?.name || 'Player ' + playerId, price: newPrice, goals: lastMessage.goals ?? prev[playerId]?.goals ?? 0, assists: lastMessage.assists ?? prev[playerId]?.assists ?? 0, minutes: lastMessage.minutes ?? prev[playerId]?.minutes ?? 0 } }
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
    const result = await executeTrade({ user_id: user.id, player_id, action, shares })
    setWallet(prev => ({ ...prev, balance: result.new_balance ?? prev.balance, holdings: { ...prev.holdings, [player_id]: (prev.holdings[player_id] || 0) + (action === 'buy' ? shares : -shares) } }))
    setNotification({ type: 'success', message: 'Successfully ' + (action === 'buy' ? 'bought' : 'sold') + ' ' + shares + ' share(s)' })
  }

  const openTradeModal = (player, action) => setTradeModal({ player, action })
  const formatPrice = (price) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(price)
  const playerList = Object.values(players)

  if (loading) return <div className="loading-screen"><p>Loading...</p></div>

  if (!isAuthenticated) {
    return authMode === 'login' ? <LoginPage onSwitch={() => setAuthMode('register')} /> : <RegisterPage onSwitch={() => setAuthMode('login')} />
  }

  return (
    <div className="app">
      <header>
        <h1>Stat Trader</h1>
        <p style={{ color: '#888', marginTop: '8px' }}>Welcome, {user.username}</p>
        <div className="header-info">
          <div className={'status ' + (isConnected ? 'connected' : 'disconnected')}><span className="status-dot"></span>{isConnected ? 'Live' : 'Connecting...'}</div>
          <div className="wallet-info">{formatPrice(wallet.balance)}</div>
          <button className={'btn ' + (liveStatus.running ? 'btn-sell' : 'btn-buy')} onClick={toggleLiveFeed} style={{padding: '8px 16px', fontSize: '0.8rem'}}>{liveStatus.running ? 'Stop Feed' : 'Start Live Feed'}</button>
          <button className="btn btn-cancel" onClick={logout} style={{padding: '8px 16px', fontSize: '0.8rem'}}>Logout</button>
        </div>
      </header>

      {notification && <div className={'notification ' + notification.type}>{notification.message}</div>}
      {error && <div className="error"><p>{error}</p><p style={{ marginTop: '10px', fontSize: '0.9rem' }}>Make sure the backend server is running</p></div>}
      {!error && playerList.length === 0 && <div className="loading"><p>Waiting for player data...</p><p style={{ marginTop: '10px', fontSize: '0.9rem', color: '#666' }}>Click "Start Live Feed" to begin streaming data</p></div>}

      <div className="players-grid">
        {playerList.map(player => {
          const priceChange = priceChanges[player.id]
          const holdings = wallet.holdings[player.id] || 0
          return (
            <div key={player.id} className="player-card">
              <h3>{player.name}</h3>
              <div className="price">{formatPrice(player.price)}{priceChange && <span className={'price-change ' + (priceChange.change > 0 ? 'up' : 'down')}>{priceChange.change > 0 ? '+' : ''}{formatPrice(priceChange.change)}</span>}</div>
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

      {tradeModal && <TradeModal player={tradeModal.player} action={tradeModal.action} onClose={() => setTradeModal(null)} onTrade={handleTrade} formatPrice={formatPrice} />}
    </div>
  )
}

export default App
