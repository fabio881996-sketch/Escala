const BASE = import.meta.env.VITE_API_URL || ''

function getToken() {
  return localStorage.getItem('gnr_admin_token')
}

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    ...options.headers,
  }
  const res = await fetch(BASE + path, { ...options, headers })
  if (res.status === 401) {
    localStorage.removeItem('gnr_admin_token')
    window.location.href = '/admin/'
    return
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Erro desconhecido')
  }
  return res.json()
}

export const api = {
  get:    (path)       => request(path),
  post:   (path, body) => request(path, { method: 'POST',   body: JSON.stringify(body) }),
  put:    (path, body) => request(path, { method: 'PUT',    body: JSON.stringify(body) }),
  delete: (path)       => request(path, { method: 'DELETE' }),

  // Auth
  login: async (pin) => {
    const form = new URLSearchParams()
    form.append('username', 'pin')
    form.append('password', pin)
    const res = await fetch('/api/auth/login', { method: 'POST', body: form })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || 'PIN incorreto')
    }
    return res.json()
  },

  // Admin
  utilizadores:         ()          => request('/admin/api/utilizadores'),
  updateUtilizador:     (id, body)  => request(`/admin/api/utilizadores/${id}`, { method: 'PUT',  body: JSON.stringify(body) }),
  efetivo:              ()          => request('/admin/api/efetivo'),
  giros:                ()          => request('/admin/api/giros'),
  alertas:              (aba)       => request(`/admin/api/alertas?aba=${aba}`),
  estatisticas:         (id, ano)   => request(`/admin/api/estatisticas?id=${id}&ano=${ano}`),
  ferias:               (ano)       => request(`/admin/api/ferias?ano=${ano}`),
  dispensas:            ()          => request('/admin/api/dispensas'),
  adicionarDispensa:    (body)      => request('/admin/api/dispensas', { method: 'POST', body: JSON.stringify(body) }),
  removerDispensa:      (id)        => request(`/admin/api/dispensas/${id}`, { method: 'DELETE' }),
  gerarEscala:          (body)      => request('/admin/api/gerar-escala',       { method: 'POST', body: JSON.stringify(body) }),
  guardarEscala:        (body)      => request('/admin/api/guardar-escala',      { method: 'POST', body: JSON.stringify(body) }),
  calcularRemunerados:  (body)      => request('/admin/api/remunerados/calcular', { method: 'POST', body: JSON.stringify(body) }),
  confirmarRemunerados: (body)      => request('/admin/api/remunerados/confirmar',{ method: 'POST', body: JSON.stringify(body) }),
}
