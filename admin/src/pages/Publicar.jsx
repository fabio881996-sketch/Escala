import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Button, Badge } from '../components/ui'

const DIAS_PT = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb']
const MESES_PT = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

function toAba(d) {
  return `${String(d.getDate()).padStart(2,'0')}-${String(d.getMonth()+1).padStart(2,'0')}`
}

export default function Publicar() {
  const qc = useQueryClient()
  const [msg, setMsg] = useState('')

  const { data: pubData, isLoading } = useQuery({
    queryKey: ['dias-publicados'],
    queryFn: () => api.get('/api/escala/publicados'),
    staleTime: 30*1000,
  })
  const { data: abasData } = useQuery({
    queryKey: ['lista-abas'],
    queryFn: () => api.get('/admin/api/lista-abas'),
    staleTime: 60*1000,
  })

  const pubMut = useMutation({
    mutationFn: aba => api.post(`/api/escala/publicar/${aba}`, {}),
    onSuccess: (_, aba) => { qc.invalidateQueries(['dias-publicados']); setMsg(`✅ ${aba} publicado!`); setTimeout(()=>setMsg(''),3000) },
    onError: e => { setMsg('❌ '+e.message); setTimeout(()=>setMsg(''),4000) },
  })
  const despubMut = useMutation({
    mutationFn: aba => api.post(`/admin/api/despublicar/${aba}`, {}),
    onSuccess: (_, aba) => { qc.invalidateQueries(['dias-publicados']); setMsg(`✅ ${aba} despublicado!`); setTimeout(()=>setMsg(''),3000) },
    onError: e => { setMsg('❌ '+e.message); setTimeout(()=>setMsg(''),4000) },
  })

  const diasPub = pubData?.dias || []
  const todasAbas = abasData?.abas || []
  const hoje = new Date()

  const proximos = Array.from({length:30},(_,i) => {
    const d = new Date(hoje); d.setDate(d.getDate()+i); return d
  })

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'#f8f9fa' }}>
      <PageHeader icon="📢" title="Publicar Escala" subtitle={`${diasPub.length} dias publicados`} />
      <div style={{ flex:1, overflowY:'auto', padding:24 }}>
        {msg && <div style={{ marginBottom:16, padding:'10px 16px', borderRadius:8, background: msg.startsWith('✅')?'#ebfbee':'#fff5f5', border:`1px solid ${msg.startsWith('✅')?'#b2f2bb':'#ffc9c9'}`, color: msg.startsWith('✅')?'#2f9e44':'#c92a2a', fontSize:13 }}>{msg}</div>}
        <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, overflow:'hidden' }}>
          <div style={{ padding:'12px 20px', borderBottom:'1px solid #f1f3f5', background:'#f8f9fa' }}>
            <span style={{ fontSize:11, fontWeight:700, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.06em' }}>Próximos 30 dias</span>
          </div>
          {proximos.map(d => {
            const aba = toAba(d)
            const pub = diasPub.includes(aba)
            const temEsc = todasAbas.includes(aba)
            const fds = d.getDay()===0||d.getDay()===6
            const isHoje = d.toDateString()===hoje.toDateString()
            return (
              <div key={aba} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'10px 20px', borderBottom:'1px solid #f8f9fa', background: fds?'#f8f9ff':'#fff' }}>
                <div style={{ display:'flex', alignItems:'center', gap:16 }}>
                  <div style={{ width:48, textAlign:'center' }}>
                    <div style={{ fontSize:10, fontWeight:700, color: fds?'#2563eb':'#adb5bd', textTransform:'uppercase' }}>{DIAS_PT[d.getDay()]}</div>
                    <div style={{ fontSize:15, fontWeight:700, color:'#0f2540' }}>{String(d.getDate()).padStart(2,'0')}</div>
                    <div style={{ fontSize:10, color:'#adb5bd' }}>{MESES_PT[d.getMonth()]}</div>
                  </div>
                  <div style={{ display:'flex', gap:6, alignItems:'center' }}>
                    {isHoje && <Badge color="green">Hoje</Badge>}
                    {pub && <Badge color="green">Publicado</Badge>}
                    {!pub && temEsc && <Badge color="amber">Com escala</Badge>}
                    {!temEsc && <Badge color="slate">Sem escala</Badge>}
                  </div>
                </div>
                <div style={{ display:'flex', gap:8 }}>
                  {!pub && temEsc && <Button size="sm" onClick={()=>pubMut.mutate(aba)} loading={pubMut.isPending&&pubMut.variables===aba}>📢 Publicar</Button>}
                  {pub && <Button size="sm" variant="danger" onClick={()=>{if(confirm(`Despublicar ${aba}?`))despubMut.mutate(aba)}} loading={despubMut.isPending&&despubMut.variables===aba}>Despublicar</Button>}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
