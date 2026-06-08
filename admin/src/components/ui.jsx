// ── Page Header ──────────────────────────────────────────────
export function PageHeader({ icon, title, subtitle, actions }) {
  return (
    <div className="flex items-start justify-between px-8 py-6 border-b border-slate-200 bg-white">
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-xl bg-[#0B1929]/5 flex items-center justify-center text-xl">
          {icon}
        </div>
        <div>
          <h1 className="font-display text-xl font-bold text-[#0B1929]">{title}</h1>
          {subtitle && <p className="text-sm text-slate-500 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

// ── Loading ───────────────────────────────────────────────────
export function Loading({ text = 'A carregar...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-3">
      <svg className="animate-spin h-8 w-8 text-[#2E7FD4]" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
      <span className="text-sm text-slate-500">{text}</span>
    </div>
  )
}

// ── Error ─────────────────────────────────────────────────────
export function ErrorBox({ message }) {
  return (
    <div className="mx-8 mt-6 flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
      <span className="text-lg">⚠️</span>
      <span>{message}</span>
    </div>
  )
}

// ── Card ──────────────────────────────────────────────────────
export function Card({ children, className = '' }) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-sm ${className}`}>
      {children}
    </div>
  )
}

// ── Badge ─────────────────────────────────────────────────────
export function Badge({ children, color = 'blue' }) {
  const colors = {
    blue:   'bg-blue-50 text-blue-700 border-blue-200',
    green:  'bg-green-50 text-green-700 border-green-200',
    red:    'bg-red-50 text-red-700 border-red-200',
    amber:  'bg-amber-50 text-amber-700 border-amber-200',
    slate:  'bg-slate-100 text-slate-600 border-slate-200',
    navy:   'bg-[#0B1929]/5 text-[#0B1929] border-[#0B1929]/10',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${colors[color]}`}>
      {children}
    </span>
  )
}

// ── Button ────────────────────────────────────────────────────
export function Button({ children, onClick, variant = 'primary', size = 'md', disabled, loading, className = '' }) {
  const variants = {
    primary:   'bg-[#2E7FD4] hover:bg-[#1A6BC4] text-white shadow-sm shadow-[#2E7FD4]/20',
    secondary: 'bg-white hover:bg-slate-50 text-slate-700 border border-slate-200',
    danger:    'bg-red-600 hover:bg-red-700 text-white',
    ghost:     'hover:bg-slate-100 text-slate-600',
    success:   'bg-green-600 hover:bg-green-700 text-white',
  }
  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-5 py-2.5 text-base',
  }
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed font-display
        ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {loading && (
        <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      )}
      {children}
    </button>
  )
}

// ── Input ─────────────────────────────────────────────────────
export function Input({ label, ...props }) {
  return (
    <div className="space-y-1">
      {label && <label className="block text-xs font-medium text-slate-600 tracking-wide uppercase">{label}</label>}
      <input
        {...props}
        className={`w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-800 
          focus:outline-none focus:border-[#2E7FD4] focus:ring-2 focus:ring-[#2E7FD4]/10 transition-all
          ${props.className || ''}`}
      />
    </div>
  )
}

// ── Select ────────────────────────────────────────────────────
export function Select({ label, children, ...props }) {
  return (
    <div className="space-y-1">
      {label && <label className="block text-xs font-medium text-slate-600 tracking-wide uppercase">{label}</label>}
      <select
        {...props}
        className={`w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-800 
          focus:outline-none focus:border-[#2E7FD4] focus:ring-2 focus:ring-[#2E7FD4]/10 transition-all
          ${props.className || ''}`}
      >
        {children}
      </select>
    </div>
  )
}

// ── Stat Card ─────────────────────────────────────────────────
export function StatCard({ icon, label, value, sub, color = 'blue' }) {
  const colors = {
    blue:  'from-[#2E7FD4]/10 to-[#2E7FD4]/5 border-[#2E7FD4]/20',
    green: 'from-green-50 to-green-50/50 border-green-200',
    amber: 'from-amber-50 to-amber-50/50 border-amber-200',
    navy:  'from-[#0B1929]/5 to-[#0B1929]/3 border-[#0B1929]/10',
  }
  return (
    <div className={`bg-gradient-to-br ${colors[color]} border rounded-xl p-5`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-display font-bold text-[#0B1929] mt-1">{value}</p>
          {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
        </div>
        <span className="text-2xl">{icon}</span>
      </div>
    </div>
  )
}

// ── Empty State ───────────────────────────────────────────────
export function Empty({ icon = '📭', title, subtitle }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
      <span className="text-4xl opacity-50">{icon}</span>
      <div>
        <p className="font-display font-semibold text-slate-600">{title}</p>
        {subtitle && <p className="text-sm text-slate-400 mt-1">{subtitle}</p>}
      </div>
    </div>
  )
}
