import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Badge, Button, Input, Select } from '../components/ui'

export default function Remunerados() {
  const hoje = new Date().toISOString().slice(0,10)
  const [data, setData] = useState(hoje)
  const [slots, setSlots] = useState([{ hor:'', n:2, tab:'A', obs:'' }])
  const [resultado, setResultado] = useState(null)
  const [msg, setMsg] = useState('')

  const calcMut = useMutation({
    mutationFn: body => api.post('/admin/api/remunerados/calcular', body),
    onSuccess: d => { setResultado(d); setMsg('') },
    onError: e => { setMsg('❌ '+e.message); setTimeout(()=>setMsg(''),4000) },
  })
  const confMut = useMutation({
    mutationFn: body => api.post('/admin/api/remunerados/confirmar', body),
    onSuccess: () => { setMsg('✅ Nomeação confirmada!'); setResultado(null); setTimeout(()=>setMsg(''),4000) },
    onError: e => { setMsg('❌ '+e.message); setTimeout(()=>setMsg(''),4000) },
  })

  function addSlot() { setSlots(s=>[...s,{hor:'',n:2,tab:'A',obs:''}]) }
  function rmSlot(i) { setSlots(s=>s.filter((_,j)=>j!==i)) }
  function upSlot(i,k,v) { setSlots(s=>s.map((sl,j)=>j===i?{...sl,[k]:v}:sl)) }

  function calcular() {
    const dt = new Date(data+'T00:00:00')
    const aba = `${String(dt.getDate()).padStart(2,'0')}-${String(dt.getMonth()+1).padStart(2,'0')}`
    const dataFmt = `${String(dt.getDate()).padStart(2,'0')}/${String(dt.getMonth()+1).padStart(2,'0')}/${dt.getFullYear()}`
    calcMut.mutate({ aba, data:dataFmt, slots })
  }

  const corGrupo = g => /Voluntário c\/ serviço|Voluntário disponível/.test(g)?'green':/folga/.test(g)?'blue':/Não voluntário/.test(g)?'amber':'slate'

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'#f8f9fa' }}>
      <PageHeader icon="💶" title="Remunerados" subtitle="Nomeação automática" />
      <div style={{ flex:1, overflowY:'auto', padding:24 }}>
        {msg && <div style={{ marginBottom:16, padding:'10px 16px', borderRadius:8, fontSize:13, background:msg.startsWith('✅')?'#ebfbee':'#fff5f5', color:msg.startsWith('✅')?'#2f9e44':'#c92a2a', border:`1px solid ${msg.startsWith('✅')?'#b2f2bb':'#ffc9c9'}` }}>{msg}</div>}

        <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, padding:20, marginBottom:16 }}>
          <div style={{ marginBottom:16 }}>
            <Input label="Data" type="date" value={data} onChange={e=>setData(e.target.value)} />
          </div>
          <div style={{ fontFamily:"'Syne',sans-serif", fontWeight:600, fontSize:13, color:'#0f2540', marginBottom:12 }}>Remunerados a nomear</div>
          <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
            {slots.map((slot,i)=>(
              <div key={i} style={{ display:'grid', gridTemplateColumns:'1fr 80px 80px 1fr auto', gap:10, alignItems:'end', background:'#f8f9fa', padding:12, borderRadius:8 }}>
                <Input label={`Horário ${i+1}`} value={slot.hor} onChange={e=>upSlot(i,'hor',e.target.value)} placeholder="ex: 08-12" />
                <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
                  <label style={{ fontSize:11, fontWeight:600, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.06em' }}>Nº Mil.</label>
                  <input type="number" min={1} max={10} value={slot.n} onChange={e=>upSlot(i,'n',parseInt(e.target.value))} style={{ padding:'7px 10px', border:'1px solid #dee2e6', borderRadius:6, fontSize:13, outline:'none' }} />
                </div>
                <Select label="Tab." value={slot.tab} onChange={e=>upSlot(i,'tab',e.target.value)}>
                  <option>A</option><option>B</option>
                </Select>
                <Input label="Observação" value={slot.obs} onChange={e=>upSlot(i,'obs',e.target.value)} placeholder="ex: Reg. Trânsito" />
                {i>0 && <button onClick={()=>rmSlot(i)} style={{ background:'none', border:'1px solid #ffc9c9', borderRadius:6, cursor:'pointer', color:'#c92a2a', padding:'7px 10px', alignSelf:'flex-end' }}>🗑️</button>}
              </div>
            ))}
          </div>
          <div style={{ display:'flex', gap:10, marginTop:16 }}>
            <Button variant="secondary" onClick={addSlot}>➕ Adicionar</Button>
            <Button onClick={calcular} loading={calcMut.isPending} disabled={!slots.some(s=>s.hor)}>🔍 Calcular</Button>
          </div>
        </div>

        {calcMut.isPending && <Loading text="A calcular nomeação..." />}

        {resultado && (
          <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, overflow:'hidden' }}>
            <div style={{ background:'#0f2540', padding:'12px 20px', color:'#fff', fontFamily:"'Syne',sans-serif", fontWeight:700 }}>Resultado</div>
            {resultado.resultados?.map((res,i)=>(
              <div key={i} style={{ padding:20, borderBottom:'1px solid #f1f3f5' }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
                  <span style={{ fontFamily:"'Syne',sans-serif", fontWeight:600, color:'#0f2540' }}>Remunerado {i+1} — Tabela {res.slot?.tab} {res.slot?.hor}</span>
                  <Badge color={res.nomeados?.length>=res.slot?.n?'green':'red'}>{res.nomeados?.length}/{res.slot?.n}</Badge>
                </div>
                {res.nomeados?.map((n,j)=>(
                  <div key={j} style={{ display:'flex', justifyContent:'space-between', padding:'8px 12px', background:'#f8f9fa', borderRadius:6, marginBottom:6 }}>
                    <span style={{ fontSize:13, fontWeight:500, color:'#0f2540' }}>{n.nome}</span>
                    <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                      <Badge color={corGrupo(n.grupo)}>{n.grupo}</Badge>
                      <span style={{ fontSize:11, color:'#adb5bd' }}>{n.total}h</span>
                    </div>
                  </div>
                ))}
                {res.avisos?.map((av,j)=>(
                  <div key={j} style={{ marginTop:6, padding:'6px 10px', background:'#fffbeb', border:'1px solid #fef3c7', borderRadius:4, fontSize:12, color:'#92400e' }} dangerouslySetInnerHTML={{__html:av}} />
                ))}
              </div>
            ))}
            {resultado.resultados?.some(r=>r.nomeados?.length>0) && (
              <div style={{ padding:20, background:'#f8f9fa', borderTop:'1px solid #dee2e6' }}>
                <Button onClick={()=>confMut.mutate({resultado})} loading={confMut.isPending} style={{ width:'100%', justifyContent:'center' }}>✅ Confirmar Nomeação</Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
