const TOKEN_KEY = 'gnr_admin_token'

async function request(method, url, body) {
  const token = localStorage.getItem(TOKEN_KEY)
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  }
  const res = await fetch(url, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Erro desconhecido')
  }
  return res.json()
}

export const api = {
  get:  url => request('GET', url),
  post: (url, body) => request('POST', url, body),

  login: async (pin) => {
    const token = localStorage.getItem(TOKEN_KEY)
    const form = new URLSearchParams()
    form.append('username', pin)
    form.append('password', pin)
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || 'PIN incorreto')
    }
    return res.json()
  },
  me:    () => request('GET', '/api/auth/me'),

  utilizadores: () => request('GET', '/admin/api/utilizadores'),
  dispensas:    () => request('GET', '/admin/api/dispensas'),
  ferias:       (ano) => request('GET', `/admin/api/ferias/${ano}`),
  giros:        () => request('GET', '/admin/api/giros'),
  estatisticas: (id, ano) => request('GET', `/admin/api/estatisticas/${id}/${ano}`),
  efetivo:      () => request('GET', '/admin/api/efetivo'),

  adicionarDispensa: (body) => request('POST', '/admin/api/dispensas', body),
  removerDispensa:   (row)  => request('DELETE', `/admin/api/dispensas/${row}`),

  gerarEscala:  (body) => request('POST', '/admin/api/gerar-escala', body),
  guardarEscala:(body) => request('POST', '/admin/api/guardar-escala', body),
}
