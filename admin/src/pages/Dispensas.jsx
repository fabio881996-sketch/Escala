import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Badge, Button, Input, Select } from '../components/ui'

const TIPOS = ['Convalescença','Licença','Outras Licenças','Diligência','Tribunal','Instrução','FCAA CTer','Folga Complementar']
const COR = { 'Convalescença':'amber','Licença':'blue','Outras Licenças':'blue','Diligência':'slate','Tribunal':'slate','Instrução':'navy','FCAA CTer':'red','Folga Complementar':'green' }

export default function Dispensas() {
  const qc = useQueryClient()
  const [form, setForm] = useState({ id:'', tipo:TIPOS[0], inicio:'', fim:'', obs:'' })
  const [mostrarForm, setMostrarForm] = useState(false)
  const [filtro, setFiltro] = useState('')
  const [msg, setMsg] = useState('')

  const { data, isLoading, error } = useQuery({ queryKey:['dispensas'], queryFn:api.dispensas, staleTime:60*1000 })
  const { data: util } = useQuery({ queryKey:['utilizadores'], queryFn:api.utilizadores, staleTime:5*60*1000 })

  const addMut = useMutation({
    mutationFn: api.adicionarDispensa,
    onSuccess: () => { qc.invalidateQueries(['dispensas']); setMostrarForm(false); setForm({id:'',tipo:TIPOS[0],inicio:'',fim:'',obs:''}); setMsg('✅ Dispensa registada!'); setTimeout(()=>setMsg(''),3000) },
    onError: e => { setMsg('❌ '+e.message); setTimeout(()=>setMsg(''),4000) },
  })
  const delMut = useMutation({
    mutationFn: api.removerDispensa,
    onSuccess: () => { qc.invalidateQueries(['dispensas']); setMsg('✅ Removida!'); setTimeout(()=>setMsg(''),3000) },
  })

  const militares = util?.utilizadores || []
  const all = (data?.dispensas || []).filter(d => !filtro || (d.nome||'').toLowerCase().includes(filtro.toLowerCase()) || (d.tipo||'').toLowerCase().includes(filtro.toLowerCase()))
  const activas = all.filter(d => d.activa !== false)
  const passadas = all.filter(d => d.activa === false)

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'#f8f9fa' }}>
      <PageHeader icon="🏥" title="Dispensas" subtitle={`${activas.length} activas`}
        actions={<Button onClick={()=>setMostrarForm(!mostrarForm)}>{mostrarForm?'✕ Cancelar':'➕ Nova'}</Button>} />
      <div style={{ flex:1, overflowY:'auto', padding:24 }}>
        {msg && <div style={{ marginBottom:16, padding:'10px 16px', borderRadius:8, fontSize:13, background:msg.startsWith('✅')?'#ebfbee':'#fff5f5', color:msg.startsWith('✅')?'#2f9e44':'#c92a2a', border:`1px solid ${msg.startsWith('✅')?'#b2f2bb':'#ffc9c9'}` }}>{msg}</div>}

        {mostrarForm && (
          <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, padding:20, marginBottom:16 }}>
            <div style={{ fontFamily:"'Syne',sans-serif", fontWeight:700, color:'#0f2540', marginBottom:16 }}>Nova Dispensa</div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12 }}>
              <Select label="Militar" value={form.id} onChange={e=>setForm(f=>({...f,id:e.target.value}))}>
                <option value="">Selecionar...</option>
                {militares.map(m=><option key={m.id} value={m.id}>{m.posto} {m.nome}</option>)}
              </Select>
              <Select label="Tipo" value={form.tipo} onChange={e=>setForm(f=>({...f,tipo:e.target.value}))}>
                {TIPOS.map(t=><option key={t}>{t}</option>)}
              </Select>
              <Input label="Início" type="date" value={form.inicio} onChange={e=>setForm(f=>({...f,inicio:e.target.value}))} />
              <Input label="Fim" type="date" value={form.fim} onChange={e=>setForm(f=>({...f,fim:e.target.value}))} />
              <div style={{ gridColumn:'span 2' }}>
                <Input label="Observações" value={form.obs} onChange={e=>setForm(f=>({...f,obs:e.target.value}))} placeholder="Opcional" />
              </div>
            </div>
            <div style={{ display:'flex', justifyContent:'flex-end', gap:8, marginTop:16 }}>
              <Button variant="secondary" onClick={()=>setMostrarForm(false)}>Cancelar</Button>
              <Button onClick={()=>addMut.mutate(form)} loading={addMut.isPending} disabled={!form.id||!form.inicio}>Guardar</Button>
            </div>
          </div>
        )}

        <div style={{ marginBottom:12 }}>
          <input value={filtro} onChange={e=>setFiltro(e.target.value)} placeholder="Filtrar..." style={{ width:'100%', padding:'8px 12px', border:'1px solid #dee2e6', borderRadius:6, fontSize:13, outline:'none', boxSizing:'border-box' }} />
        </div>

        {isLoading && <Loading />}
        {error && <ErrorBox message={error.message} />}

        {activas.length > 0 && (
          <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, overflow:'hidden', marginBottom:16 }}>
            <div style={{ padding:'10px 20px', background:'#fffbeb', borderBottom:'1px solid #fef3c7' }}>
              <span style={{ fontSize:11, fontWeight:700, color:'#92400e', textTransform:'uppercase', letterSpacing:'0.06em' }}>Activas ({activas.length})</span>
            </div>
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
              <thead><tr style={{ background:'#f8f9fa', borderBottom:'1px solid #dee2e6' }}>
                {['Militar','Tipo','Início','Fim','Obs',''].map(h=><th key={h} style={{ textAlign:'left', padding:'8px 16px', fontSize:11, fontWeight:600, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.05em' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {activas.map(d=>(
                  <tr key={d.__row} style={{ borderBottom:'1px solid #f8f9fa' }}>
                    <td style={{ padding:'10px 16px', fontWeight:500, color:'#0f2540' }}>{d.nome}</td>
                    <td style={{ padding:'10px 16px' }}><Badge color={COR[d.tipo]||'slate'}>{d.tipo}</Badge></td>
                    <td style={{ padding:'10px 16px', fontFamily:'monospace', fontSize:12, color:'#495057' }}>{d.inicio}</td>
                    <td style={{ padding:'10px 16px', fontFamily:'monospace', fontSize:12, color:'#495057' }}>{d.fim||'—'}</td>
                    <td style={{ padding:'10px 16px', fontSize:12, color:'#adb5bd' }}>{d.obs}</td>
                    <td style={{ padding:'10px 16px', textAlign:'right' }}>
                      <button onClick={()=>{if(confirm('Remover?'))delMut.mutate(d.__row)}} style={{ background:'none', border:'none', cursor:'pointer', color:'#adb5bd', fontSize:16 }}>🗑️</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {passadas.length > 0 && (
          <details>
            <summary style={{ cursor:'pointer', fontSize:13, color:'#6c757d', padding:'8px 0', userSelect:'none' }}>📋 Histórico ({passadas.length})</summary>
            <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, overflow:'hidden', marginTop:8 }}>
              <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
                <tbody>
                  {passadas.map(d=>(
                    <tr key={d.__row} style={{ borderBottom:'1px solid #f8f9fa', opacity:.6 }}>
                      <td style={{ padding:'8px 16px', fontWeight:500 }}>{d.nome}</td>
                      <td style={{ padding:'8px 16px' }}><Badge color="slate">{d.tipo}</Badge></td>
                      <td style={{ padding:'8px 16px', fontFamily:'monospace', fontSize:12 }}>{d.inicio} → {d.fim}</td>
                      <td style={{ padding:'8px 16px', textAlign:'right' }}>
                        <button onClick={()=>{if(confirm('Remover?'))delMut.mutate(d.__row)}} style={{ background:'none', border:'none', cursor:'pointer', color:'#adb5bd' }}>🗑️</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}

        {!isLoading && all.length === 0 && (
          <div style={{ textAlign:'center', padding:'60px 0', color:'#adb5bd' }}>
            <div style={{ fontSize:40, marginBottom:12 }}>🏥</div>
            <p style={{ fontWeight:600 }}>Sem dispensas registadas</p>
          </div>
        )}
      </div>
    </div>
  )
}
