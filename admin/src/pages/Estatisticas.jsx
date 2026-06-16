import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Select } from '../components/ui'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const CORES = ['#2e7fd4','#0f2540','#c9a84c','#16a34a','#dc2626','#7c3aed','#0891b2','#d97706']

export default function Estatisticas() {
  const ano = new Date().getFullYear()
  const [milId, setMilId] = useState('')
  const { data: util } = useQuery({ queryKey:['utilizadores'], queryFn:api.utilizadores, staleTime:5*60*1000 })
  const militares = util?.utilizadores || []

  const { data, isLoading, error } = useQuery({
    queryKey: ['estatisticas', milId, ano],
    queryFn: () => api.estatisticas(milId, ano),
    enabled: !!milId,
    staleTime: 5*60*1000,
  })

  const servicos = data?.servicos || []
  const total = data?.total || 0

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'#f8f9fa' }}>
      <PageHeader icon="📊" title="Estatísticas" subtitle={`Ano ${ano}`} />
      <div style={{ flex:1, overflowY:'auto', padding:24 }}>
        <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, padding:20, marginBottom:20 }}>
          <Select label="Militar" value={milId} onChange={e=>setMilId(e.target.value)}>
            <option value="">Selecionar militar...</option>
            {militares.map(m=><option key={m.id} value={m.id}>{m.posto} {m.nome}</option>)}
          </Select>
        </div>

        {!milId && <div style={{ textAlign:'center', paddingTop:60, opacity:.4 }}><div style={{ fontSize:48 }}>📊</div><p style={{ fontWeight:600, color:'#495057' }}>Seleciona um militar</p></div>}
        {milId && isLoading && <Loading />}
        {milId && error && <ErrorBox message={error.message} />}

        {milId && !isLoading && !error && servicos.length > 0 && (
          <>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:16, marginBottom:20 }}>
              {[{l:'Total Serviços',v:total,c:'#2e7fd4'},{l:'Tipos diferentes',v:servicos.length,c:'#16a34a'},{l:'Militar',v:(data?.nome||'').split(' ').pop(),c:'#0f2540'}].map(s=>(
                <div key={s.l} style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, padding:'16px 20px' }}>
                  <p style={{ fontSize:11, fontWeight:600, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.06em', margin:'0 0 8px' }}>{s.l}</p>
                  <p style={{ fontFamily:"'Syne',sans-serif", fontSize:26, fontWeight:700, color:s.c, margin:0 }}>{s.v}</p>
                </div>
              ))}
            </div>

            <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, padding:20, marginBottom:16 }}>
              <div style={{ fontFamily:"'Syne',sans-serif", fontWeight:700, color:'#0f2540', marginBottom:16 }}>Distribuição por Serviço</div>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={servicos.slice(0,12)} margin={{bottom:40}}>
                  <XAxis dataKey="servico" tick={{fontSize:10}} angle={-35} textAnchor="end" interval={0} />
                  <YAxis tick={{fontSize:11}} />
                  <Tooltip formatter={v=>[v,'Serviços']} />
                  <Bar dataKey="total" radius={[4,4,0,0]}>
                    {servicos.slice(0,12).map((_,i)=><Cell key={i} fill={CORES[i%CORES.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, overflow:'hidden' }}>
              <div style={{ padding:'10px 20px', borderBottom:'1px solid #f1f3f5', background:'#f8f9fa' }}>
                <span style={{ fontSize:11, fontWeight:700, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.06em' }}>Detalhe</span>
              </div>
              <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
                <tbody>
                  {servicos.map((s,i)=>(
                    <tr key={i} style={{ borderBottom:'1px solid #f8f9fa' }}>
                      <td style={{ padding:'10px 20px', fontWeight:500, color:'#0f2540' }}>{s.servico}</td>
                      <td style={{ padding:'10px 20px', textAlign:'right' }}>
                        <span style={{ fontFamily:"'Syne',sans-serif", fontWeight:700, color:'#2e7fd4' }}>{s.total}</span>
                        <span style={{ fontSize:11, color:'#adb5bd', marginLeft:4 }}>serv.</span>
                      </td>
                      <td style={{ padding:'10px 20px', width:160 }}>
                        <div style={{ background:'#f1f3f5', borderRadius:99, height:6 }}>
                          <div style={{ background:'#2e7fd4', borderRadius:99, height:6, width:`${Math.round(s.total/total*100)}%` }} />
                        </div>
                      </td>
                      <td style={{ padding:'10px 20px', textAlign:'right', fontSize:12, color:'#6c757d', width:48 }}>{Math.round(s.total/total*100)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
