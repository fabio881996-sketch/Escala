import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Badge } from '../components/ui'

export default function Efetivo() {
  const [filtro, setFiltro] = useState('')
  const { data, isLoading, error } = useQuery({ queryKey:['utilizadores'], queryFn:api.utilizadores, staleTime:5*60*1000 })
  const militares = (data?.utilizadores || []).filter(m => !filtro || (m.nome||'').toLowerCase().includes(filtro.toLowerCase()) || String(m.id).includes(filtro) || (m.posto||'').toLowerCase().includes(filtro.toLowerCase()))

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'#f8f9fa' }}>
      <PageHeader icon="👥" title="Efectivo" subtitle={`${data?.utilizadores?.length||0} militares`} />
      <div style={{ flex:1, overflowY:'auto', padding:24 }}>
        <div style={{ marginBottom:16 }}>
          <input value={filtro} onChange={e=>setFiltro(e.target.value)} placeholder="Filtrar por nome, ID ou posto..." style={{ width:'100%', padding:'8px 12px', border:'1px solid #dee2e6', borderRadius:6, fontSize:13, outline:'none', boxSizing:'border-box' }} />
        </div>
        {isLoading && <Loading />}
        {error && <ErrorBox message={error.message} />}
        {!isLoading && !error && (
          <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, overflow:'hidden' }}>
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
              <thead><tr style={{ background:'#f8f9fa', borderBottom:'1px solid #dee2e6' }}>
                {['ID','Posto','Nome','Giro','NIM',''].map(h=><th key={h} style={{ textAlign:'left', padding:'10px 16px', fontSize:11, fontWeight:600, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.05em' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {militares.map(m=>(
                  <tr key={m.id} style={{ borderBottom:'1px solid #f8f9fa' }}>
                    <td style={{ padding:'10px 16px', fontFamily:'monospace', fontWeight:700, color:'#2e7fd4' }}>{m.id}</td>
                    <td style={{ padding:'10px 16px', fontSize:12, color:'#6c757d' }}>{m.posto}</td>
                    <td style={{ padding:'10px 16px', fontWeight:500, color:'#0f2540' }}>{m.nome}</td>
                    <td style={{ padding:'10px 16px' }}>{m.giro && <Badge color="slate">Giro {m.giro}</Badge>}</td>
                    <td style={{ padding:'10px 16px', fontSize:12, color:'#adb5bd', fontFamily:'monospace' }}>{m.nim}</td>
                    <td style={{ padding:'10px 16px' }}>{m.tem_pin ? <Badge color="green">PIN ✓</Badge> : <Badge color="red">Sem PIN</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
