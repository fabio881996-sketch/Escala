import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Badge, Button, Input } from '../components/ui'

export default function Utilizadores() {
  const qc = useQueryClient()
  const [filtro, setFiltro] = useState('')
  const [pinForm, setPinForm] = useState({ id:null, pin:'' })
  const [msg, setMsg] = useState('')

  const { data, isLoading, error } = useQuery({ queryKey:['utilizadores'], queryFn:api.utilizadores, staleTime:5*60*1000 })

  const pinMut = useMutation({
    mutationFn: ({ id, pin }) => api.post(`/admin/api/utilizadores/${id}/pin`, { pin }),
    onSuccess: () => { qc.invalidateQueries(['utilizadores']); setPinForm({id:null,pin:''}); setMsg('✅ PIN actualizado!'); setTimeout(()=>setMsg(''),3000) },
    onError: e => { setMsg('❌ '+e.message); setTimeout(()=>setMsg(''),4000) },
  })

  const militares = (data?.utilizadores || []).filter(m => !filtro || (m.nome||'').toLowerCase().includes(filtro.toLowerCase()) || String(m.id).includes(filtro))

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'#f8f9fa' }}>
      <PageHeader icon="👤" title="Utilizadores" subtitle={`${data?.utilizadores?.length||0} militares`} />
      <div style={{ flex:1, overflowY:'auto', padding:24 }}>
        {msg && <div style={{ marginBottom:16, padding:'10px 16px', borderRadius:8, fontSize:13, background:msg.startsWith('✅')?'#ebfbee':'#fff5f5', color:msg.startsWith('✅')?'#2f9e44':'#c92a2a', border:`1px solid ${msg.startsWith('✅')?'#b2f2bb':'#ffc9c9'}` }}>{msg}</div>}
        <div style={{ marginBottom:16 }}>
          <input value={filtro} onChange={e=>setFiltro(e.target.value)} placeholder="Filtrar..." style={{ width:'100%', padding:'8px 12px', border:'1px solid #dee2e6', borderRadius:6, fontSize:13, outline:'none', boxSizing:'border-box' }} />
        </div>
        {isLoading && <Loading />}
        {error && <ErrorBox message={error.message} />}
        {!isLoading && !error && (
          <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, overflow:'hidden' }}>
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
              <thead><tr style={{ background:'#f8f9fa', borderBottom:'1px solid #dee2e6' }}>
                {['ID','Posto / Nome','PIN',''].map(h=><th key={h} style={{ textAlign:'left', padding:'10px 16px', fontSize:11, fontWeight:600, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.05em' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {militares.map(m=>(
                  <tr key={m.id} style={{ borderBottom:'1px solid #f8f9fa' }}>
                    <td style={{ padding:'10px 16px', fontFamily:'monospace', fontWeight:700, color:'#2e7fd4', width:60 }}>{m.id}</td>
                    <td style={{ padding:'10px 16px' }}>
                      <div style={{ fontWeight:500, color:'#0f2540' }}>{m.nome}</div>
                      <div style={{ fontSize:11, color:'#adb5bd' }}>{m.posto}</div>
                    </td>
                    <td style={{ padding:'10px 16px' }}>
                      {pinForm.id === m.id ? (
                        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                          <input type="password" placeholder="Novo PIN" value={pinForm.pin} onChange={e=>setPinForm(f=>({...f,pin:e.target.value}))}
                            style={{ padding:'5px 10px', border:'1px solid #dee2e6', borderRadius:6, fontSize:13, width:120, outline:'none' }} />
                          <Button size="sm" onClick={()=>pinMut.mutate(pinForm)} loading={pinMut.isPending} disabled={pinForm.pin.length < 4}>Guardar</Button>
                          <Button size="sm" variant="secondary" onClick={()=>setPinForm({id:null,pin:''})}>✕</Button>
                        </div>
                      ) : (
                        m.tem_pin ? <Badge color="green">PIN definido</Badge> : <Badge color="red">Sem PIN</Badge>
                      )}
                    </td>
                    <td style={{ padding:'10px 16px', textAlign:'right' }}>
                      {pinForm.id !== m.id && <Button size="sm" variant="secondary" onClick={()=>setPinForm({id:m.id,pin:''})}>🔑 PIN</Button>}
                    </td>
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
