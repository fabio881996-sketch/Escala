import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'

const NAV = [
  { to: '/dashboard',     icon: '📊', label: 'Estatísticas' },
  { to: '/escala-geral',  icon: '📅', label: 'Escala Geral' },
  { to: '/gerar-escala',  icon: '⚙️', label: 'Gerar Escala' },
  { to: '/publicar',      icon: '📢', label: 'Publicar' },
  { to: '/ferias',        icon: '🏖️', label: 'Férias' },
  { to: '/dispensas',     icon: '🏥', label: 'Dispensas' },
  { to: '/remunerados',   icon: '💶', label: 'Remunerados' },
  { to: '/alertas',       icon: '🚨', label: 'Alertas' },
  { to: '/giros',         icon: '🔄', label: 'Giros' },
  { to: '/efetivo',       icon: '👥', label: 'Efetivo' },
  { to: '/utilizadores',  icon: '👤', label: 'Utilizadores' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div style={{ display:'flex', height:'100vh', overflow:'hidden', background:'#f8f9fa' }}>
      {/* Sidebar */}
      <aside style={{
        width:220, background:'#0f2540', display:'flex', flexDirection:'column',
        flexShrink:0, borderRight:'1px solid #1a3a5c'
      }}>
        {/* Logo */}
        <div style={{ padding:'20px 16px 16px', borderBottom:'1px solid rgba(255,255,255,0.07)' }}>
          <div style={{ display:'flex', alignItems:'center', gap:10 }}>
            <div style={{
              width:36, height:36, borderRadius:8, background:'rgba(46,127,212,0.25)',
              display:'flex', alignItems:'center', justifyContent:'center', fontSize:18
            }}>🚓</div>
            <div>
              <div style={{ color:'#fff', fontFamily:"'Syne',sans-serif", fontWeight:700, fontSize:13, lineHeight:1.2 }}>Portal Admin</div>
              <div style={{ color:'#c9a84c', fontSize:10, fontWeight:600, letterSpacing:'0.06em', textTransform:'uppercase' }}>GNR Famalicão</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex:1, overflowY:'auto', padding:'10px 8px' }}>
          {NAV.map(({ to, icon, label }) => (
            <NavLink key={to} to={to} style={({ isActive }) => ({
              display:'flex', alignItems:'center', gap:10,
              padding:'8px 10px', borderRadius:6, marginBottom:2,
              textDecoration:'none', fontSize:13, transition:'all 0.1s',
              background: isActive ? '#2e7fd4' : 'transparent',
              color: isActive ? '#fff' : 'rgba(255,255,255,0.6)',
              fontWeight: isActive ? 600 : 400,
            })}>
              <span style={{ fontSize:15, width:20, textAlign:'center' }}>{icon}</span>
              <span style={{ fontFamily:"'Syne',sans-serif" }}>{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* User */}
        <div style={{ padding:'12px 8px', borderTop:'1px solid rgba(255,255,255,0.07)' }}>
          <div style={{
            display:'flex', alignItems:'center', gap:10, padding:'8px 10px',
            borderRadius:6, background:'rgba(255,255,255,0.05)'
          }}>
            <div style={{
              width:28, height:28, borderRadius:'50%', background:'rgba(46,127,212,0.3)',
              display:'flex', alignItems:'center', justifyContent:'center',
              color:'#7bb8f0', fontSize:11, fontWeight:700
            }}>
              {user?.nome?.charAt(0) || 'A'}
            </div>
            <div style={{ flex:1, minWidth:0 }}>
              <div style={{ color:'#fff', fontSize:12, fontWeight:500, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
                {user?.nome?.split(' ')[0] || 'Admin'}
              </div>
              <div style={{ color:'rgba(255,255,255,0.4)', fontSize:10 }}>Administrador</div>
            </div>
            <button onClick={() => { logout(); navigate('/') }} style={{
              background:'none', border:'none', cursor:'pointer',
              color:'rgba(255,255,255,0.35)', fontSize:16, padding:4,
              borderRadius:4, transition:'color 0.1s'
            }} title="Sair">⏻</button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex:1, overflowY:'auto', display:'flex', flexDirection:'column' }}>
        <Outlet />
      </main>
    </div>
  )
}
