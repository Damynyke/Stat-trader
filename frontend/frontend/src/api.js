// API service for backend communication
const API_BASE = 'http://localhost:8000'

export async function fetchPlayers() {
  const res = await fetch(`${API_BASE}/players`)
  if (!res.ok) throw new Error('Failed to fetch players')
  return res.json()
}

export async function fetchWallet(userId) {
  const res = await fetch(`${API_BASE}/wallet/${userId}`)
  if (!res.ok) throw new Error('Failed to fetch wallet')
  return res.json()
}

export async function executeTrade({ user_id, player_id, action, shares }) {
  const res = await fetch(`${API_BASE}/trade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id, player_id, action, shares }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Trade failed')
  return data
}

export async function initializePayment({ user_id, amount, email }) {
  const res = await fetch(`${API_BASE}/payment/initialize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id, amount, email }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Payment initialization failed')
  return data
}
