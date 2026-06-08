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

  function handleLogout() {
    logout()
    navigate('/')
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#F8FAFC]">
      {/* Sidebar */}
      <aside className="w-60 bg-[#0B1929] flex flex-col shrink-0">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#2E7FD4] to-[#1A3A5C] flex items-center justify-center text-lg shadow-lg">
              🚓
            </div>
            <div>
              <div className="text-white font-display font-bold text-sm leading-tight">Portal Admin</div>
              <div className="text-[#C9A84C] text-[10px] font-medium tracking-wider uppercase">GNR Famalicão</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-0.5">
          {NAV.map(({ to, icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 group
                ${isActive
                  ? 'bg-[#2E7FD4] text-white font-medium shadow-lg shadow-[#2E7FD4]/20'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
                }`
              }
            >
              <span className="text-base w-5 text-center">{icon}</span>
              <span className="font-display">{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* User */}
        <div className="px-3 py-4 border-t border-white/5">
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/5">
            <div className="w-7 h-7 rounded-full bg-[#2E7FD4]/20 flex items-center justify-center text-[#2E7FD4] text-xs font-bold">
              {user?.nome?.charAt(0) || 'A'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-white text-xs font-medium truncate">{user?.nome || 'Admin'}</div>
              <div className="text-slate-500 text-[10px]">Administrador</div>
            </div>
            <button
              onClick={handleLogout}
              className="text-slate-500 hover:text-red-400 transition-colors text-sm"
              title="Sair"
            >
              ⏻
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
