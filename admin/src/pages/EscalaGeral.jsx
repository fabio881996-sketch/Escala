import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Card, Button } from '../components/ui'

const DIAS_PT = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb']
const MESES_PT = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

function toAba(date) {
  return `${String(date.getDate()).padStart(2,'0')}-${String(date.getMonth()+1).padStart(2,'0')}`
}
function dataFmt(date) {
  return `${DIAS_PT[date.getDay()]}, ${date.getDate()} ${MESES_PT[date.getMonth()]} ${date.getFullYear()}`
}

function agrupar(entradas) {
  const g = { ausencias:[], adm:[], atendimento:[], apoio:[], po:[], patrulhas:[], remunerados:[], outros:[] }
  for (const e of entradas) {
    const s = e.servico.toLowerCase()
    if (/ferias|licen|convalesc|folga|fcaa|cter/.test(s)) g.ausencias.push(e)
    else if (/pronto|secretaria|inquer|dilig|tribunal|instrução/.test(s)) g.adm.push(e)
    else if (/apoio ao atendimento/.test(s)) g.apoio.push(e)
    else if (/atendimento/.test(s)) g.atendimento.push(e)
    else if (/patrulha ocorr/.test(s)) g.po.push(e)
    else if (/patrulha|ronda/.test(s)) g.patrulhas.push(e)
    else if (/remun|gratif/.test(s)) g.remunerados.push(e)
    else g.outros.push(e)
  }
  return g
}

function porHorario(entradas) {
  const map = {}
  for (const e of entradas) {
    const k = e.horario || '—'
    if (!map[k]) map[k] = []
    map[k].push(e)
  }
  return Object.entries(map).sort(([a],[b]) => a.localeCompare(b))
}

function Secao({ titulo, entradas, colunas = false }) {
  if (!entradas.length) return null
  return (
    <Card className="mb-4 overflow-hidden">
      <div className="px-5 py-2 bg-[#0B1929] text-white text-xs font-bold uppercase tracking-wider">{titulo}</div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100 bg-slate-50">
            <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 w-24">Horário</th>
            <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500">Militares</th>
            {colunas && <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500">Viatura</th>}
            {colunas && <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500">Rádio</th>}
            {colunas && <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500">Indicativo</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {porHorario(entradas).map(([hor, es]) => (
            <tr key={hor} className="hover:bg-slate-50">
              <td className="px-4 py-2.5 font-mono text-xs font-bold text-[#0B1929]">{hor}</td>
              <td className="px-4 py-2.5">
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  {es.map((e,i) => {
                    const troca = e.id_disp?.includes('🔄')
                    return (
                      <span key={i} className={`text-xs ${troca ? 'text-orange-600 font-semibold' : 'text-slate-700'}`}>
                        {e.nome || e.id}{troca && ' 🔄'}
                      </span>
                    )
                  })}
                </div>
              </td>
              {colunas && <td className="px-4 py-2.5 text-xs text-slate-500">{es[0]?.viatura||'—'}</td>}
              {colunas && <td className="px-4 py-2.5 text-xs text-slate-500">{es[0]?.radio||'—'}</td>}
              {colunas && <td className="px-4 py-2.5 text-xs text-slate-500">{es[0]?.indicativo||'—'}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function SecaoAusencias({ aus, adm }) {
  if (!aus.length && !adm.length) return null
  const byServ = (arr) => arr.reduce((m,e) => { const k=e.servico||'Outro'; if(!m[k])m[k]=[]; m[k].push(e); return m }, {})
  return (
    <div className="grid grid-cols-2 gap-4 mb-4">
      <Card className="p-4">
        <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Ausências</div>
        {Object.entries(byServ(aus)).map(([s,es]) => (
          <div key={s} className="mb-2">
            <div className="text-xs font-semibold text-slate-700">{s}</div>
            <div className="text-xs text-slate-500">{es.map(e=>e.nome||e.id).join(', ')}</div>
          </div>
        ))}
      </Card>
      <Card className="p-4">
        <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">ADM / Outras</div>
        {Object.entries(byServ(adm)).map(([s,es]) => (
          <div key={s} className="mb-2">
            <div className="text-xs font-semibold text-slate-700">{s}</div>
            <div className="text-xs text-slate-500">{es.map(e=>e.nome||e.id).join(', ')}</div>
          </div>
        ))}
      </Card>
    </div>
  )
}

export default function EscalaGeral() {
  const hoje = new Date()
  const [data, setData] = useState(hoje.toISOString().slice(0,10))
  const [pdfLoading, setPdfLoading] = useState(false)

  const dataObj = new Date(data + 'T00:00:00')
  const aba = toAba(dataObj)

  const { data: res, isLoading, error, isFetching } = useQuery({
    queryKey: ['escala-geral', aba],
    queryFn: () => api.get(`/admin/api/escala-dia/${aba}`),
    staleTime: 2 * 60 * 1000,
  })

  const entradas = res?.entradas || []
  const g = agrupar(entradas)

  async function downloadPdf() {
    setPdfLoading(true)
    try {
      const token = localStorage.getItem('gnr_admin_token')
      const resp = await fetch(`/admin/api/escala-pdf/${aba}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!resp.ok) throw new Error('Erro ao gerar PDF')
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `Escala_${aba}.pdf`; a.click()
      URL.revokeObjectURL(url)
    } catch(e) { alert('Erro: ' + e.message) }
    finally { setPdfLoading(false) }
  }

  function navDia(delta) {
    const d = new Date(data + 'T00:00:00')
    d.setDate(d.getDate() + delta)
    setData(d.toISOString().slice(0,10))
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        icon="📅" title="Escala Geral" subtitle={dataFmt(dataObj)}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => navDia(-1)}>‹</Button>
            <input type="date" value={data} onChange={e => setData(e.target.value)}
              className="px-3 py-1.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-[#2E7FD4]" />
            <Button variant="secondary" size="sm" onClick={() => navDia(1)}>›</Button>
            <Button variant="secondary" size="sm" onClick={downloadPdf} loading={pdfLoading}>📥 PDF</Button>
          </div>
        }
      />
      <div className="flex-1 overflow-y-auto p-6">
        {(isLoading || isFetching) && <Loading text="A carregar escala..." />}
        {error && <ErrorBox message={error.message} />}
        {!isLoading && !error && entradas.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
            <span className="text-5xl opacity-30">📅</span>
            <p className="font-display font-semibold text-slate-500">Escala não publicada para este dia</p>
          </div>
        )}
        {!isLoading && entradas.length > 0 && (
          <>
            <SecaoAusencias aus={g.ausencias} adm={g.adm} />
            <Secao titulo="Atendimento" entradas={g.atendimento} />
            <Secao titulo="Apoio ao Atendimento" entradas={g.apoio} />
            <Secao titulo="Patrulha Ocorrências" entradas={g.po} colunas />
            <Secao titulo="Patrulhas" entradas={g.patrulhas} colunas />
            <Secao titulo="Remunerados" entradas={g.remunerados} />
            <Secao titulo="Outros" entradas={g.outros} />
          </>
        )}
      </div>
    </div>
  )
}
