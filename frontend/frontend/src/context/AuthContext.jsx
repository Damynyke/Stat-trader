import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)

const API_BASE = 'http://localhost:8000'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(localStorage.getItem('token'))
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (token) {
      fetchUser()
    } else {
      setLoading(false)
    }
  }, [token])

  const fetchUser = async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        const userData = await res.json()
        setUser(userData)
      } else {
        logout()
      }
    } catch (err) {
      console.error('Failed to fetch user:', err)
      logout()
    } finally {
      setLoading(false)
    }
  }

  const login = async (username, password) => {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)

    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData
    })

    if (!res.ok) {
      const error = await res.json()
      throw new Error(error.detail || 'Login failed')
    }

    const data = await res.json()
    localStorage.setItem('token', data.access_token)
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }

  const register = async (email, username, password) => {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, username, password })
    })

    if (!res.ok) {
      const error = await res.json()
      throw new Error(error.detail || 'Registration failed')
    }

    const userData = await res.json()
    // Auto-login after registration
    await login(username, password)
    return userData
  }

  const logout = () => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
  }

  const value = {
    user,
    token,
    loading,
    login,
    register,
    logout,
    isAuthenticated: !!user
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
