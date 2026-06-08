import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Loading, ErrorBox } from '../components/ui'

const DIAS = ['Domingo','Segunda-feira','Terça-feira','Quarta-feira','Quinta-feira','Sexta-feira','Sábado']
const MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
const DIAS_SHORT = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb']

function toAba(d) {
  return `${String(d.getDate()).padStart(2,'0')}-${String(d.getMonth()+1).padStart(2,'0')}`
}

function agrupar(entradas) {
  const g = { ausencias:[], adm:[], atendimento:[], apoio:[], po:[], patrulhas:[], remunerados:[], outros:[] }
  for (const e of entradas) {
    const s = (e.servico||'').toLowerCase()
    if (/ferias|licen|convalesc|folga|fcaa|cter/.test(s)) g.ausencias.push(e)
    else if (/pronto|secretaria|inquer|dilig|tribunal|instrução|instrucao/.test(s)) g.adm.push(e)
    else if (/apoio ao atendimento/.test(s)) g.apoio.push(e)
    else if (/atendimento/.test(s)) g.atendimento.push(e)
    else if (/patrulha ocorr/.test(s)) g.po.push(e)
    else if (/patrulha|ronda/.test(s)) g.patrulhas.push(e)
    else if (/remun|gratif/.test(s)) g.remunerados.push(e)
    else g.outros.push(e)
  }
  return g
}

function porHorario(es) {
  const m = {}
  for (const e of es) { const k = e.horario||'—'; if(!m[k])m[k]=[]; m[k].push(e) }
  return Object.entries(m).sort(([a],[b]) => a.localeCompare(b))
}

function byServico(arr) {
  return arr.reduce((m,e) => { const k=e.servico||'Outro'; if(!m[k])m[k]=[]; m[k].push(e); return m }, {})
}

const s = {
  secHeader: {
    background:'#0f2540',
    color:'#fff',
    padding:'8px 20px',
    fontSize:11,
    fontWeight:700,
    letterSpacing:'0.08em',
    textTransform:'uppercase',
  },
  table: { width:'100%', borderCollapse:'collapse', fontSize:13 },
  thRow: {
    background:'#f8f9fa',
    borderBottom:'1px solid #e9ecef',
  },
  th: {
    textAlign:'left', padding:'7px 20px',
    fontSize:11, fontWeight:600, color:'#6c757d',
    letterSpacing:'0.06em', textTransform:'uppercase',
  },
  tdHor: { padding:'10px 20px', fontFamily:'monospace', fontSize:13, fontWeight:700, color:'#0f2540', whiteSpace:'nowrap', verticalAlign:'top' },
  tdMil: { padding:'10px 20px', verticalAlign:'top' },
  tdInfo: { padding:'10px 20px', fontSize:13, color:'#495057', fontFamily:'monospace', verticalAlign:'top' },
  tr0: { borderBottom:'1px solid #f1f3f5' },
  tr1: { borderBottom:'1px solid #f1f3f5', background:'#fbfcfd' },
}

function NomeMil({ e }) {
  const troca = e.id_disp?.includes('🔄')
  return (
    <span style={{ marginRight:20, color: troca ? '#e67e22' : '#212529', fontWeight: troca ? 600 : 400 }}>
      {e.nome || e.id}
      {troca && <span style={{ fontSize:11, marginLeft:4, opacity:.8 }}>↔</span>}
    </span>
  )
}

function Secao({ titulo, entradas, cols = false }) {
  if (!entradas.length) return null
  return (
    <div style={{ marginBottom:16, border:'1px solid #dee2e6', borderRadius:8, overflow:'hidden' }}>
      <div style={s.secHeader}>{titulo}</div>
      <table style={s.table}>
        <thead>
          <tr style={s.thRow}>
            <th style={{...s.th, width:100}}>Horário</th>
            <th style={s.th}>Militares</th>
            {cols && <th style={{...s.th, width:100}}>Viatura</th>}
            {cols && <th style={{...s.th, width:90}}>Rádio</th>}
            {cols && <th style={{...s.th, width:100}}>Indicativo</th>}
          </tr>
        </thead>
        <tbody>
          {porHorario(entradas).map(([hor, es], i) => (
            <tr key={hor} style={i%2===0 ? s.tr0 : s.tr1}>
              <td style={s.tdHor}>{hor}</td>
              <td style={s.tdMil}>
                <div style={{ display:'flex', flexWrap:'wrap' }}>
                  {es.map((e,j) => <NomeMil key={j} e={e} />)}
                </div>
              </td>
              {cols && <td style={s.tdInfo}>{es[0]?.viatura || <span style={{color:'#ced4da'}}>—</span>}</td>}
              {cols && <td style={s.tdInfo}>{es[0]?.radio || <span style={{color:'#ced4da'}}>—</span>}</td>}
              {cols && <td style={s.tdInfo}>{es[0]?.indicativo || <span style={{color:'#ced4da'}}>—</span>}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SecaoAus({ aus, adm }) {
  if (!aus.length && !adm.length) return null
  const ausG = byServico(aus)
  const admG = byServico(adm)
  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginBottom:16 }}>
      {[['AUSÊNCIAS', ausG], ['ADM / OUTRAS', admG]].map(([titulo, grupos]) => (
        <div key={titulo} style={{ border:'1px solid #dee2e6', borderRadius:8, overflow:'hidden' }}>
          <div style={s.secHeader}>{titulo}</div>
          <div style={{ padding:'12px 16px', background:'#fff' }}>
            {Object.entries(grupos).map(([serv, es]) => (
              <div key={serv} style={{ marginBottom:10 }}>
                <div style={{ fontSize:12, fontWeight:700, color:'#212529', marginBottom:3 }}>{serv}</div>
                <div style={{ fontSize:12, color:'#6c757d', lineHeight:1.6 }}>
                  {es.map(e => e.nome || e.id).join(', ')}
                </div>
              </div>
            ))}
            {!Object.keys(grupos).length && <p style={{ fontSize:12, color:'#adb5bd', fontStyle:'italic', margin:0 }}>Sem registos</p>}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function EscalaGeral() {
  const hoje = new Date()
  const [data, setData] = useState(hoje.toISOString().slice(0,10))
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfCompletoLoading, setPdfCompletoLoading] = useState(false)

  const dataObj = new Date(data + 'T00:00:00')
  const aba = toAba(dataObj)
  const isFds = dataObj.getDay() === 0 || dataObj.getDay() === 6

  const { data: res, isLoading, error, isFetching } = useQuery({
    queryKey: ['escala-geral', aba],
    queryFn: () => api.get(`/admin/api/escala-dia/${aba}`),
    staleTime: 2 * 60 * 1000,
  })

  const entradas = res?.entradas || []
  const g = agrupar(entradas)

  async function downloadPdfCompleto() {
    setPdfCompletoLoading(true)
    try {
      const token = localStorage.getItem('gnr_admin_token')
      const resp = await fetch(`/admin/api/escala-pdf-completo`, { headers: { Authorization: `Bearer ${token}` } })
      if (!resp.ok) throw new Error('Erro ao gerar PDF')
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href=url; a.download=`Escala_Completa.pdf`; a.click()
      URL.revokeObjectURL(url)
    } catch(e) { alert('Erro: ' + e.message) }
    finally { setPdfCompletoLoading(false) }
  }

  async function downloadPdf() {
    setPdfLoading(true)
    try {
      const token = localStorage.getItem('gnr_admin_token')
      const resp = await fetch(`/admin/api/escala-pdf/${aba}`, { headers: { Authorization: `Bearer ${token}` } })
      if (!resp.ok) throw new Error('Erro ao gerar PDF')
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href=url; a.download=`Escala_${aba}.pdf`; a.click()
      URL.revokeObjectURL(url)
    } catch(e) { alert('Erro: ' + e.message) }
    finally { setPdfLoading(false) }
  }

  function navDia(delta) {
    const parts = data.split('-')
    const d = new Date(parseInt(parts[0]), parseInt(parts[1])-1, parseInt(parts[2]))
    d.setDate(d.getDate() + delta)
    const yyyy = d.getFullYear()
    const mm = String(d.getMonth()+1).padStart(2,'0')
    const dd = String(d.getDate()).padStart(2,'0')
    setData(`${yyyy}-${mm}-${dd}`)
  }

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'#f8f9fa' }}>
      {/* Header */}
      <div style={{ background:'#fff', borderBottom:'1px solid #dee2e6', padding:'14px 28px', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <div>
          <h1 style={{ fontFamily:"'Syne',sans-serif", fontSize:20, fontWeight:700, color:'#0f2540', margin:0 }}>Escala Geral</h1>
          <p style={{ fontSize:13, color: isFds ? '#2563eb' : '#6c757d', margin:'2px 0 0', fontWeight: isFds ? 600 : 400 }}>
            {DIAS[dataObj.getDay()]}, {dataObj.getDate()} de {MESES[dataObj.getMonth()]} de {dataObj.getFullYear()}
          </p>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          <button onClick={() => navDia(-1)} style={{ width:32, height:32, border:'1px solid #dee2e6', borderRadius:6, background:'#fff', cursor:'pointer', fontSize:16, color:'#6c757d', display:'flex', alignItems:'center', justifyContent:'center' }}>‹</button>
          <button onClick={() => navDia(1)} style={{ width:32, height:32, border:'1px solid #dee2e6', borderRadius:6, background:'#fff', cursor:'pointer', fontSize:16, color:'#6c757d', display:'flex', alignItems:'center', justifyContent:'center' }}>›</button>
          <input type="date" value={data} onChange={e => setData(e.target.value)} style={{
            padding:'5px 10px', border:'1px solid #dee2e6', borderRadius:6, fontSize:13,
            background:'#fff', color:'#212529', outline:'none'
          }}/>
          <button onClick={downloadPdf} disabled={pdfLoading || !entradas.length} style={{
            display:'flex', alignItems:'center', gap:6, padding:'6px 14px',
            border:'1px solid #dee2e6', borderRadius:6, background:'#fff', cursor:'pointer',
            fontSize:13, color:'#495057', fontWeight:500, opacity: (!entradas.length || pdfLoading) ? .4 : 1
          }}>
            {pdfLoading ? '⏳' : '↓'} PDF Dia
          </button>
          <button onClick={downloadPdfCompleto} disabled={pdfCompletoLoading} style={{
            display:'flex', alignItems:'center', gap:6, padding:'6px 14px',
            border:'1px solid #dee2e6', borderRadius:6, background:'#fff', cursor:'pointer',
            fontSize:13, color:'#495057', fontWeight:500, opacity: pdfCompletoLoading ? .4 : 1
          }}>
            {pdfCompletoLoading ? '⏳' : '↓'} PDF Completo
          </button>
        </div>
      </div>

      {/* Conteúdo */}
      <div style={{ flex:1, overflowY:'auto', padding:24 }}>
        {(isLoading||isFetching) && <Loading text="A carregar escala..." />}
        {error && <ErrorBox message={error.message} />}

        {!isLoading && !error && !entradas.length && (
          <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', paddingTop:80, gap:12, opacity:.5 }}>
            <span style={{ fontSize:48 }}>📅</span>
            <p style={{ fontWeight:600, color:'#495057', margin:0 }}>Escala não publicada para {aba}</p>
          </div>
        )}

        {!isLoading && !!entradas.length && (
          <div style={{ maxWidth:1100, margin:'0 auto' }}>
            <SecaoAus aus={g.ausencias} adm={g.adm} />
            <Secao titulo="Atendimento" entradas={g.atendimento} />
            <Secao titulo="Apoio ao Atendimento" entradas={g.apoio} />
            <Secao titulo="Patrulha Ocorrências" entradas={g.po} cols />
            <Secao titulo="Patrulhas" entradas={g.patrulhas} cols />
            <Secao titulo="Remunerados" entradas={g.remunerados} />
            <Secao titulo="Outros" entradas={g.outros} />
          </div>
        )}
      </div>
    </div>
  )
}
