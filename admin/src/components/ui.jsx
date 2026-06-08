const H = { background:'#fff', borderBottom:'1px solid #dee2e6', padding:'14px 28px', display:'flex', alignItems:'center', justifyContent:'space-between' }
const HDR_TXT = { fontFamily:"'Syne',sans-serif", fontSize:20, fontWeight:700, color:'#0f2540', margin:0 }
const SUB_TXT = { fontSize:13, color:'#6c757d', margin:'2px 0 0' }

export function PageHeader({ icon, title, subtitle, actions }) {
  return (
    <div style={H}>
      <div style={{ display:'flex', alignItems:'center', gap:14 }}>
        <div style={{ width:40, height:40, borderRadius:10, background:'#f1f3f5', display:'flex', alignItems:'center', justifyContent:'center', fontSize:20 }}>{icon}</div>
        <div>
          <h1 style={HDR_TXT}>{title}</h1>
          {subtitle && <p style={SUB_TXT}>{subtitle}</p>}
        </div>
      </div>
      {actions && <div style={{ display:'flex', alignItems:'center', gap:8 }}>{actions}</div>}
    </div>
  )
}

export function Loading({ text = 'A carregar...' }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', padding:'80px 0', gap:12, color:'#6c757d' }}>
      <svg style={{ animation:'spin 1s linear infinite', width:28, height:28 }} viewBox="0 0 24 24" fill="none">
        <style>{'@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}'}</style>
        <circle cx="12" cy="12" r="10" stroke="#dee2e6" strokeWidth="3"/>
        <path fill="#2e7fd4" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
      <span style={{ fontSize:13 }}>{text}</span>
    </div>
  )
}

export function ErrorBox({ message }) {
  return (
    <div style={{ margin:'16px 24px', display:'flex', alignItems:'center', gap:10, padding:'12px 16px', background:'#fff5f5', border:'1px solid #ffc9c9', borderRadius:8, color:'#c92a2a', fontSize:13 }}>
      ⚠️ {message}
    </div>
  )
}

export function Card({ children, className, style = {} }) {
  return (
    <div style={{ background:'#fff', borderRadius:8, border:'1px solid #dee2e6', ...style }}>
      {children}
    </div>
  )
}

export function Badge({ children, color = 'blue' }) {
  const colors = {
    blue:  { bg:'#e7f5ff', color:'#1971c2', border:'#a5d8ff' },
    green: { bg:'#ebfbee', color:'#2f9e44', border:'#b2f2bb' },
    red:   { bg:'#fff5f5', color:'#c92a2a', border:'#ffc9c9' },
    amber: { bg:'#fff9db', color:'#e67700', border:'#ffec99' },
    slate: { bg:'#f1f3f5', color:'#495057', border:'#dee2e6' },
    navy:  { bg:'#e7f5ff', color:'#0f2540', border:'#a5d8ff' },
  }
  const c = colors[color] || colors.slate
  return (
    <span style={{ display:'inline-flex', alignItems:'center', padding:'2px 8px', borderRadius:4, fontSize:11, fontWeight:600, background:c.bg, color:c.color, border:`1px solid ${c.border}` }}>
      {children}
    </span>
  )
}

export function Button({ children, onClick, variant = 'primary', size = 'md', disabled, loading, type = 'button', className, style: extraStyle = {} }) {
  const variants = {
    primary: { background:'#2e7fd4', color:'#fff', border:'1px solid #2e7fd4' },
    secondary: { background:'#fff', color:'#495057', border:'1px solid #dee2e6' },
    danger: { background:'#c92a2a', color:'#fff', border:'1px solid #c92a2a' },
    success: { background:'#2f9e44', color:'#fff', border:'1px solid #2f9e44' },
    ghost: { background:'transparent', color:'#6c757d', border:'1px solid transparent' },
  }
  const sizes = { sm: { padding:'5px 12px', fontSize:12 }, md: { padding:'7px 16px', fontSize:13 }, lg: { padding:'9px 20px', fontSize:14 } }
  return (
    <button type={type} onClick={onClick} disabled={disabled || loading} style={{
      display:'inline-flex', alignItems:'center', justifyContent:'center', gap:6,
      fontFamily:"'Syne',sans-serif", fontWeight:600, borderRadius:6, cursor:'pointer',
      transition:'all 0.1s', opacity: (disabled||loading) ? .5 : 1,
      ...variants[variant], ...sizes[size], ...extraStyle
    }}>
      {loading && <svg style={{ animation:'spin 1s linear infinite', width:12, height:12 }} viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.4)" strokeWidth="4"/><path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>}
      {children}
    </button>
  )
}

export function Input({ label, ...props }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
      {label && <label style={{ fontSize:11, fontWeight:600, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.06em' }}>{label}</label>}
      <input {...props} style={{ padding:'7px 10px', border:'1px solid #dee2e6', borderRadius:6, fontSize:13, color:'#212529', background:'#fff', outline:'none', ...props.style }} />
    </div>
  )
}

export function Select({ label, children, ...props }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
      {label && <label style={{ fontSize:11, fontWeight:600, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.06em' }}>{label}</label>}
      <select {...props} style={{ padding:'7px 10px', border:'1px solid #dee2e6', borderRadius:6, fontSize:13, color:'#212529', background:'#fff', outline:'none', ...props.style }}>
        {children}
      </select>
    </div>
  )
}

export function StatCard({ icon, label, value, sub, color = 'blue' }) {
  const colors = {
    blue:  { bg:'#e7f5ff', border:'#a5d8ff', val:'#1971c2' },
    green: { bg:'#ebfbee', border:'#b2f2bb', val:'#2f9e44' },
    amber: { bg:'#fff9db', border:'#ffec99', val:'#e67700' },
    navy:  { bg:'#e9ecef', border:'#ced4da', val:'#0f2540' },
  }
  const c = colors[color] || colors.blue
  return (
    <div style={{ background:c.bg, border:`1px solid ${c.border}`, borderRadius:8, padding:'16px 20px' }}>
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between' }}>
        <div>
          <p style={{ fontSize:11, fontWeight:600, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.06em', margin:'0 0 6px' }}>{label}</p>
          <p style={{ fontFamily:"'Syne',sans-serif", fontSize:26, fontWeight:700, color:c.val, margin:0 }}>{value}</p>
          {sub && <p style={{ fontSize:11, color:'#6c757d', margin:'4px 0 0' }}>{sub}</p>}
        </div>
        <span style={{ fontSize:24, opacity:.7 }}>{icon}</span>
      </div>
    </div>
  )
}

export function Empty({ icon = '📭', title, subtitle }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', padding:'60px 0', gap:12, opacity:.5 }}>
      <span style={{ fontSize:40 }}>{icon}</span>
      <div style={{ textAlign:'center' }}>
        <p style={{ fontFamily:"'Syne',sans-serif", fontWeight:600, color:'#495057', margin:0 }}>{title}</p>
        {subtitle && <p style={{ fontSize:13, color:'#6c757d', margin:'4px 0 0' }}>{subtitle}</p>}
      </div>
    </div>
  )
}
