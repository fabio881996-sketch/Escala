import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuth } from './store/auth'
import { api } from './lib/api'

import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import EscalaGeral from './pages/EscalaGeral'
import GerarEscala from './pages/GerarEscala'
import Publicar from './pages/Publicar'
import Ferias from './pages/Ferias'
import Dispensas from './pages/Dispensas'
import Remunerados from './pages/Remunerados'
import Alertas from './pages/Alertas'
import Giros from './pages/Giros'
import Efetivo from './pages/Efetivo'
import Utilizadores from './pages/Utilizadores'
import Estatisticas from './pages/Estatisticas'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

function Login() {
  const { setToken, setUser } = useAuth()
  const [pin, setPin] = [window.__pin||'', v => window.__pin=v]

  async function handleLogin(e) {
    e.preventDefault()
    try {
      const data = await api.login(document.getElementById('pin').value)
      if (!data.is_admin) { alert('Sem permissões de administrador'); return }
      setToken(data.access_token)
      setUser({ nome: data.user_nome, id: data.user_id })
      window.location.reload()
    } catch(e) { alert('PIN incorreto: ' + e.message) }
  }

  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100vh', background:'#0f2540' }}>
      <div style={{ background:'#fff', borderRadius:12, padding:40, width:360, boxShadow:'0 20px 60px rgba(0,0,0,0.3)' }}>
        <div style={{ textAlign:'center', marginBottom:32 }}>
          <div style={{ fontSize:48, marginBottom:8 }}>🚓</div>
          <h1 style={{ fontFamily:"'Syne',sans-serif", fontSize:20, fontWeight:700, color:'#0f2540', margin:0 }}>Portal Admin</h1>
          <p style={{ fontSize:13, color:'#6c757d', margin:'4px 0 0' }}>GNR Famalicão</p>
        </div>
        <form onSubmit={handleLogin} style={{ display:'flex', flexDirection:'column', gap:16 }}>
          <div>
            <label style={{ fontSize:11, fontWeight:600, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.06em', display:'block', marginBottom:6 }}>PIN</label>
            <input id="pin" type="password" placeholder="••••" autoFocus style={{ width:'100%', padding:'10px 14px', border:'2px solid #dee2e6', borderRadius:8, fontSize:16, textAlign:'center', letterSpacing:8, outline:'none', boxSizing:'border-box' }}
              onFocus={e=>e.target.style.borderColor='#2e7fd4'} onBlur={e=>e.target.style.borderColor='#dee2e6'} />
          </div>
          <button type="submit" style={{ padding:'11px', background:'#2e7fd4', color:'#fff', border:'none', borderRadius:8, fontFamily:"'Syne',sans-serif", fontSize:14, fontWeight:700, cursor:'pointer' }}>Entrar</button>
        </form>
      </div>
    </div>
  )
}

function AuthWrapper({ children }) {
  const { token, user, setUser, logout } = useAuth()

  useEffect(() => {
    if (token && !user) {
      api.me().then(data => setUser({ nome: data.nome, id: data.user_id, is_admin: data.is_admin }))
        .catch(() => logout())
    }
  }, [token])

  if (!token) return <Login />
  return children
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter basename="/admin">
        <AuthWrapper>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard"    element={<Dashboard />} />
              <Route path="escala-geral" element={<EscalaGeral />} />
              <Route path="gerar-escala" element={<GerarEscala />} />
              <Route path="publicar"     element={<Publicar />} />
              <Route path="ferias"       element={<Ferias />} />
              <Route path="dispensas"    element={<Dispensas />} />
              <Route path="remunerados"  element={<Remunerados />} />
              <Route path="alertas"      element={<Alertas />} />
              <Route path="giros"        element={<Giros />} />
              <Route path="efetivo"      element={<Efetivo />} />
              <Route path="utilizadores" element={<Utilizadores />} />
              <Route path="estatisticas" element={<Estatisticas />} />
            </Route>
          </Routes>
        </AuthWrapper>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
