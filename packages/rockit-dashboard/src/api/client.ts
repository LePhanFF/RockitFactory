/**
 * API client for rockit-serve.
 * All requests go through the Vite proxy (no hardcoded URLs).
 */

const getToken = () => localStorage.getItem('rockit_token')

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(path, { ...options, headers })
  if (res.status === 401) {
    localStorage.removeItem('rockit_token')
    window.location.reload()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API error ${res.status}: ${body}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  // Auth
  register: (data: { username: string; email: string; password: string; display_name?: string }) =>
    request<{ access_token: string; user: any }>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),

  login: (data: { username: string; password: string }) =>
    request<{ access_token: string; user: any }>('/auth/login', { method: 'POST', body: JSON.stringify(data) }),

  getProfile: () => request<any>('/auth/me'),

  // Strategy Preferences
  getStrategyPrefs: () => request<any[]>('/auth/strategies'),

  updateStrategyPref: (strategyId: string, data: { is_active: boolean; mastery_level: string; notes?: string }) =>
    request<any>(`/auth/strategies/${strategyId}`, {
      method: 'PUT',
      body: JSON.stringify({ strategy_id: strategyId, ...data }),
    }),

  // Trades
  getTrades: (params?: { session_date?: string; strategy_id?: string }) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString()
    return request<any[]>(`/api/v1/trades${qs ? `?${qs}` : ''}`)
  },

  createTrade: (data: any) =>
    request<any>('/api/v1/trades', { method: 'POST', body: JSON.stringify(data) }),

  updateTrade: (id: number, data: any) =>
    request<any>(`/api/v1/trades/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  deleteTrade: (id: number) =>
    request<void>(`/api/v1/trades/${id}`, { method: 'DELETE' }),

  // Journal
  getJournal: (params?: { session_date?: string; entry_type?: string }) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString()
    return request<any[]>(`/api/v1/journal${qs ? `?${qs}` : ''}`)
  },

  createJournalEntry: (data: { session_date: string; entry_type: string; content: string }) =>
    request<any>('/api/v1/journal', { method: 'POST', body: JSON.stringify(data) }),

  updateJournalEntry: (id: number, data: { content: string }) =>
    request<any>(`/api/v1/journal/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  // Bot Keys
  getBotKeys: () => request<any[]>('/auth/bot-keys'),
  createBotKey: (data: { name: string; instruments?: string }) =>
    request<any>('/auth/bot-keys', { method: 'POST', body: JSON.stringify(data) }),
  deleteBotKey: (id: number) =>
    request<void>(`/auth/bot-keys/${id}`, { method: 'DELETE' }),

  // Market
  getMarketContext: () => request<any>('/api/v1/market/context'),
  getStrategyStates: () => request<any>('/api/v1/market/strategies'),
  getResearchStats: () => request<any>('/api/v1/market/research/stats'),
}
