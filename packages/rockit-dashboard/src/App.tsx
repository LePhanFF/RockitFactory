import { useEffect } from 'react'
import { useAuthStore } from './store'
import { api } from './api/client'
import { LoginPage } from './components/LoginPage'
import { Layout } from './components/Layout'

export function App() {
  const { isAuthenticated, login, logout } = useAuthStore()

  // Validate token on mount
  useEffect(() => {
    const token = localStorage.getItem('rockit_token')
    if (!token) return
    api.getProfile()
      .then(user => login(token, user))
      .catch(() => logout())
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!isAuthenticated) {
    return <LoginPage />
  }

  return <Layout />
}
