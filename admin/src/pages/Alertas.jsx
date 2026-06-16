import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Badge } from '../components/ui'

function toAba(d) { return `${String(d.getDate()).padStart(2,'0')}-${String(d.getMonth()+1).padStart(2,'0')}` }

export default function Alertas() {
  const hoje = new Date()
  const [data, setData] = useState(hoje.toISOString().slice(0,10))
  const aba = toAba(new Date(data+'T00:00:00'))

  const { data: res, isLoading, error } = useQuery({
    queryKey: ['alertas', aba],
    queryFn: () => api.get(`/admin/api/alertas?aba=${aba}`),
    staleTime: 60*1000,
  })
  const alertas = res?.alertas || []

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'#f8f9fa' }}>
      <PageHeader icon="🚨" title="Alertas" subtitle={alertas.length > 0 ? `${alertas.length} alertas` : 'Sem alertas'}
        actions={<input type="date" value={data} onChange={e=>setData(e.target.value)} style={{ padding:'5px 10px', border:'1px solid #dee2e6', borderRadius:6, fontSize:13, outline:'none' }} />} />
      <div style={{ flex:1, overflowY:'auto', padding:24 }}>
        {isLoading && <Loading />}
        {error && <ErrorBox message={error.message} />}
        {!isLoading && !error && alertas.length === 0 && (
          <div style={{ textAlign:'center', paddingTop:80, opacity:.5 }}>
            <div style={{ fontSize:48 }}>✅</div>
            <p style={{ fontWeight:600, color:'#495057' }}>Sem alertas para {aba}</p>
          </div>
        )}
        {alertas.length > 0 && (
          <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, overflow:'hidden' }}>
            {alertas.map((a,i)=>(
              <div key={i} style={{ display:'flex', alignItems:'flex-start', gap:12, padding:'14px 20px', borderBottom:'1px solid #f8f9fa' }}>
                <span style={{ fontSize:20 }}>{a.tipo==='duplicado'?'⚠️':a.tipo==='consecutivo'?'🔄':'❗'}</span>
                <div style={{ flex:1 }}>
                  <div style={{ fontWeight:500, color:'#0f2540', fontSize:13 }}>{a.militar}</div>
                  <div style={{ fontSize:12, color:'#6c757d', marginTop:2 }}>{a.mensagem}</div>
                </div>
                <Badge color={a.tipo==='duplicado'?'red':'amber'}>{a.tipo}</Badge>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
