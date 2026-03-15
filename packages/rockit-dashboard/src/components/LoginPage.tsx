import { useState } from 'react'
import { LayoutDashboard } from 'lucide-react'
import { api } from '../api/client'
import { useAuthStore } from '../store'

export function LoginPage() {
  const [isRegister, setIsRegister] = useState(false)
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const login = useAuthStore(s => s.login)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = isRegister
        ? await api.register({ username, email, password })
        : await api.login({ username, password })
      login(res.access_token, res.user)
    } catch (err: any) {
      setError(err.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="p-3 bg-accent rounded-2xl shadow-[0_0_30px_var(--accent-glow)]">
            <LayoutDashboard className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-black tracking-tighter text-content uppercase">
              ROCKIT <span className="text-accent">ENGINE</span>
            </h1>
            <p className="text-xs text-content-muted tracking-widest uppercase">Live Trading Dashboard</p>
          </div>
        </div>

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="bg-surface border border-border rounded-3xl p-8 shadow-2xl space-y-5"
        >
          <div>
            <label className="block text-[10px] font-bold text-content-muted uppercase tracking-widest mb-2">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="w-full bg-background border border-border rounded-xl px-4 py-3 text-sm font-mono text-content focus:outline-none focus:border-accent transition-colors"
              required
              autoFocus
            />
          </div>

          {isRegister && (
            <div className="animate-fade-in">
              <label className="block text-[10px] font-bold text-content-muted uppercase tracking-widest mb-2">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full bg-background border border-border rounded-xl px-4 py-3 text-sm font-mono text-content focus:outline-none focus:border-accent transition-colors"
                required
              />
            </div>
          )}

          <div>
            <label className="block text-[10px] font-bold text-content-muted uppercase tracking-widest mb-2">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full bg-background border border-border rounded-xl px-4 py-3 text-sm font-mono text-content focus:outline-none focus:border-accent transition-colors"
              required
              minLength={6}
            />
          </div>

          {error && (
            <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl px-4 py-3 text-sm text-rose-400">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-accent text-white font-bold py-3 rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 uppercase tracking-wider text-sm"
          >
            {loading ? 'Loading...' : isRegister ? 'Create Account' : 'Sign In'}
          </button>

          <button
            type="button"
            onClick={() => { setIsRegister(!isRegister); setError('') }}
            className="w-full text-center text-xs text-content-muted hover:text-accent transition-colors py-2"
          >
            {isRegister ? 'Already have an account? Sign in' : 'Need an account? Register'}
          </button>
        </form>
      </div>
    </div>
  )
}
