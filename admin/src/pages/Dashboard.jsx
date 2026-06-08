import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useAuth } from '../store/auth'
import { useNavigate } from 'react-router-dom'

const ACESSO = [
  { to:'/escala-geral',  icon:'📅', label:'Escala Geral',    desc:'Ver e navegar a escala diária' },
  { to:'/gerar-escala',  icon:'⚙️', label:'Gerar Escala',    desc:'Gerar escalas automaticamente' },
  { to:'/publicar',      icon:'📢', label:'Publicar',         desc:'Publicar dias para os militares' },
  { to:'/dispensas',     icon:'🏥', label:'Dispensas',        desc:'Gerir dispensas e licenças' },
  { to:'/remunerados',   icon:'💶', label:'Remunerados',      desc:'Nomear para serviços remunerados' },
  { to:'/alertas',       icon:'🚨', label:'Alertas',          desc:'Verificar alertas da escala' },
  { to:'/ferias',        icon:'🏖️', label:'Férias',           desc:'Plano de férias do efectivo' },
  { to:'/utilizadores',  icon:'👤', label:'Utilizadores',     desc:'Gerir PINs e acessos' },
]

const MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const ano = new Date().getFullYear()
  const hora = new Date().getHours()
  const saudacao = hora < 12 ? 'Bom dia' : hora < 19 ? 'Boa tarde' : 'Boa noite'

  const { data: util } = useQuery({ queryKey:['utilizadores'], queryFn:api.utilizadores, staleTime:5*60*1000 })
  const { data: disp } = useQuery({ queryKey:['dispensas'], queryFn:api.dispensas, staleTime:60*1000 })
  const { data: pub  } = useQuery({ queryKey:['dias-publicados'], queryFn:()=>api.get('/api/escala/publicados'), staleTime:30*1000 })

  const totalMil = util?.utilizadores?.length || 0
  const hoje = new Date()
  const dispensasActivas = (disp?.dispensas||[]).filter(d=>d.activa).length
  const diasPub = pub?.dias?.length || 0

  // Próximos dias publicados
  const proxPub = (pub?.dias||[])
    .map(aba => {
      const [dd,mm] = aba.split('-')
      const d = new Date(ano, parseInt(mm)-1, parseInt(dd))
      return { aba, date: d, label: `${dd}/${mm}` }
    })
    .filter(x => x.date >= hoje)
    .sort((a,b) => a.date - b.date)
    .slice(0, 7)

  const st = {
    page: { padding:28, background:'#f8f9fa', minHeight:'100%' },
    greeting: { marginBottom:28 },
    greetTitle: { fontFamily:"'Syne',sans-serif", fontSize:24, fontWeight:700, color:'#0f2540', margin:0 },
    greetSub: { fontSize:14, color:'#6c757d', margin:'4px 0 0' },
    statsGrid: { display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:16, marginBottom:28 },
    stat: { background:'#fff', border:'1px solid #dee2e6', borderRadius:10, padding:'18px 22px' },
    statLabel: { fontSize:11, fontWeight:600, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.07em', margin:'0 0 8px' },
    statVal: { fontFamily:"'Syne',sans-serif", fontSize:28, fontWeight:700, color:'#0f2540', margin:0 },
    statSub: { fontSize:12, color:'#adb5bd', margin:'4px 0 0' },
    row: { display:'grid', gridTemplateColumns:'1fr 1fr', gap:20 },
    card: { background:'#fff', border:'1px solid #dee2e6', borderRadius:10, overflow:'hidden' },
    cardHdr: { padding:'14px 20px', borderBottom:'1px solid #f1f3f5', display:'flex', alignItems:'center', justifyContent:'space-between' },
    cardTitle: { fontFamily:"'Syne',sans-serif", fontSize:14, fontWeight:700, color:'#0f2540', margin:0 },
    acessoGrid: { display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:1, background:'#f1f3f5' },
    acessoItem: { background:'#fff', padding:'14px 18px', cursor:'pointer', transition:'background 0.1s', display:'flex', alignItems:'center', gap:12 },
    acessoIcon: { fontSize:20, width:36, height:36, background:'#f8f9fa', borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 },
    acessoLabel: { fontFamily:"'Syne',sans-serif", fontSize:13, fontWeight:600, color:'#0f2540', margin:0 },
    acessoDesc: { fontSize:11, color:'#adb5bd', margin:'2px 0 0' },
    diaItem: { display:'flex', alignItems:'center', justifyContent:'space-between', padding:'9px 20px', borderBottom:'1px solid #f8f9fa' },
  }

  return (
    <div style={st.page}>
      {/* Saudação */}
      <div style={st.greeting}>
        <h1 style={st.greetTitle}>{saudacao}, {user?.nome?.split(' ')[0] || 'Admin'} 👋</h1>
        <p style={st.greetSub}>
          {hoje.getDate()} de {['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'][hoje.getMonth()]} de {ano}
          {' · '}Posto Territorial de Vila Nova de Famalicão
        </p>
      </div>

      {/* Stats */}
      <div style={st.statsGrid}>
        <div style={st.stat}>
          <p style={st.statLabel}>Efectivo</p>
          <p style={st.statVal}>{totalMil}</p>
          <p style={st.statSub}>militares registados</p>
        </div>
        <div style={{...st.stat, borderLeft:'3px solid #ffd43b'}}>
          <p style={st.statLabel}>Dispensas activas</p>
          <p style={{...st.statVal, color: dispensasActivas > 0 ? '#e67700' : '#0f2540'}}>{dispensasActivas}</p>
          <p style={st.statSub}>em vigor hoje</p>
        </div>
        <div style={{...st.stat, borderLeft:'3px solid #51cf66'}}>
          <p style={st.statLabel}>Dias publicados</p>
          <p style={{...st.statVal, color:'#2f9e44'}}>{diasPub}</p>
          <p style={st.statSub}>visíveis para os militares</p>
        </div>
      </div>

      {/* Row: acesso rápido + próximos dias */}
      <div style={st.row}>
        {/* Acesso rápido */}
        <div style={st.card}>
          <div style={st.cardHdr}>
            <p style={st.cardTitle}>Acesso rápido</p>
          </div>
          <div style={st.acessoGrid}>
            {ACESSO.map(({ to, icon, label, desc }) => (
              <div key={to} style={st.acessoItem}
                onClick={() => navigate(to)}
                onMouseEnter={e => e.currentTarget.style.background='#f8f9fa'}
                onMouseLeave={e => e.currentTarget.style.background='#fff'}
              >
                <div style={st.acessoIcon}>{icon}</div>
                <div>
                  <p style={st.acessoLabel}>{label}</p>
                  <p style={st.acessoDesc}>{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Próximos dias publicados */}
        <div style={st.card}>
          <div style={st.cardHdr}>
            <p style={st.cardTitle}>Próximos dias publicados</p>
            <span style={{ fontSize:12, color:'#adb5bd' }}>{proxPub.length} dias</span>
          </div>
          {proxPub.length === 0 ? (
            <div style={{ padding:'32px 20px', textAlign:'center', color:'#adb5bd', fontSize:13 }}>
              Sem dias publicados próximos
            </div>
          ) : (
            <div>
              {proxPub.map(({ aba, date, label }) => {
                const DIAS = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb']
                const diaSem = DIAS[date.getDay()]
                const isFds = date.getDay() === 0 || date.getDay() === 6
                const isHoje = date.toDateString() === hoje.toDateString()
                return (
                  <div key={aba} style={st.diaItem}
                    onClick={() => navigate(`/escala-geral?data=${date.toISOString().slice(0,10)}`)}
                    onMouseEnter={e => e.currentTarget.style.background='#f8f9fa'}
                    onMouseLeave={e => e.currentTarget.style.background='transparent'}
                    style={{...st.diaItem, cursor:'pointer'}}
                  >
                    <div style={{ display:'flex', alignItems:'center', gap:12 }}>
                      <div style={{ width:42, textAlign:'center' }}>
                        <div style={{ fontSize:10, fontWeight:700, color: isFds ? '#2563eb' : '#adb5bd', textTransform:'uppercase' }}>{diaSem}</div>
                        <div style={{ fontFamily:"'Syne',sans-serif", fontSize:16, fontWeight:700, color:'#0f2540' }}>{date.getDate()}</div>
                        <div style={{ fontSize:10, color:'#adb5bd' }}>{MESES[date.getMonth()]}</div>
                      </div>
                      <div>
                        {isHoje && <span style={{ fontSize:10, fontWeight:700, color:'#2f9e44', background:'#ebfbee', padding:'1px 6px', borderRadius:3 }}>HOJE</span>}
                        <div style={{ fontSize:12, color:'#6c757d' }}>Escala publicada</div>
                      </div>
                    </div>
                    <span style={{ color:'#dee2e6', fontSize:14 }}>›</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
