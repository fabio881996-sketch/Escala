import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Loading, ErrorBox, Button } from '../components/ui'

const DIAS_PT = ['Domingo','Segunda-feira','Terça-feira','Quarta-feira','Quinta-feira','Sexta-feira','Sábado']
const MESES_PT = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

function toAba(date) {
  return `${String(date.getDate()).padStart(2,'0')}-${String(date.getMonth()+1).padStart(2,'0')}`
}

function agrupar(entradas) {
  const g = { ausencias:[], adm:[], atendimento:[], apoio:[], po:[], patrulhas:[], remunerados:[], outros:[] }
  for (const e of entradas) {
    const s = (e.servico||'').toLowerCase()
    if (/ferias|licen|convalesc|folga|fcaa|cter/.test(s)) g.ausencias.push(e)
    else if (/pronto|secretaria|inquer|dilig|tribunal|instrução|instrucao/.test(s)) g.adm.push(e)
    else if (/apoio ao atendimento/.test(s)) g.apoio.push(e)
    else if (/atendimento/.test(s)) g.atendimento.push(e)
    else if (/patrulha ocorr|patrulha oc/.test(s)) g.po.push(e)
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

function byServico(arr) {
  return arr.reduce((m,e) => { const k=e.servico||'Outro'; if(!m[k])m[k]=[]; m[k].push(e); return m }, {})
}

// Secção de ausências — duas colunas
function SecaoAusencias({ aus, adm }) {
  if (!aus.length && !adm.length) return null
  return (
    <div className="grid grid-cols-2 gap-4 mb-5">
      {/* Ausências */}
      <div className="border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <div className="px-4 py-2.5 bg-slate-700 text-white text-xs font-bold uppercase tracking-widest">
          Ausências
        </div>
        <div className="p-4 space-y-3 bg-white">
          {Object.entries(byServico(aus)).map(([s, es]) => (
            <div key={s}>
              <div className="text-xs font-bold text-slate-800 mb-1">{s}</div>
              <div className="text-xs text-slate-500 leading-relaxed">
                {es.map(e => e.nome || e.id).join(', ')}
              </div>
            </div>
          ))}
          {!aus.length && <p className="text-xs text-slate-400 italic">Sem ausências</p>}
        </div>
      </div>
      {/* ADM */}
      <div className="border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <div className="px-4 py-2.5 bg-slate-700 text-white text-xs font-bold uppercase tracking-widest">
          ADM / Outras
        </div>
        <div className="p-4 space-y-3 bg-white">
          {Object.entries(byServico(adm)).map(([s, es]) => (
            <div key={s}>
              <div className="text-xs font-bold text-slate-800 mb-1">{s}</div>
              <div className="text-xs text-slate-500 leading-relaxed">
                {es.map(e => e.nome || e.id).join(', ')}
              </div>
            </div>
          ))}
          {!adm.length && <p className="text-xs text-slate-400 italic">Sem serviços ADM</p>}
        </div>
      </div>
    </div>
  )
}

// Secção de serviço com tabela
function Secao({ titulo, entradas, colunas = false }) {
  if (!entradas.length) return null
  return (
    <div className="mb-5 border border-slate-200 rounded-xl overflow-hidden shadow-sm">
      <div className="px-5 py-2.5 bg-[#0B1929] text-white">
        <span className="text-xs font-bold uppercase tracking-widest">{titulo}</span>
      </div>
      <table className="w-full">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-200">
            <th className="text-left px-5 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider w-28">Horário</th>
            <th className="text-left px-5 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Militares</th>
            {colunas && <>
              <th className="text-left px-5 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider w-28">Viatura</th>
              <th className="text-left px-5 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider w-28">Rádio</th>
              <th className="text-left px-5 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider w-28">Indicativo</th>
            </>}
          </tr>
        </thead>
        <tbody>
          {porHorario(entradas).map(([hor, es], i) => (
            <tr key={hor} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}>
              <td className="px-5 py-3 font-mono text-sm font-bold text-[#0B1929]">{hor}</td>
              <td className="px-5 py-3">
                <div className="flex flex-wrap gap-x-6 gap-y-1">
                  {es.map((e,j) => {
                    const troca = e.id_disp?.includes('🔄')
                    return (
                      <span key={j} className={`text-sm ${troca ? 'text-orange-500 font-semibold' : 'text-slate-700'}`}>
                        {e.nome || e.id}
                        {troca && <span className="ml-1 text-xs opacity-70">🔄</span>}
                      </span>
                    )
                  })}
                </div>
              </td>
              {colunas && <>
                <td className="px-5 py-3 text-sm text-slate-600 font-mono">{es[0]?.viatura || <span className="text-slate-300">—</span>}</td>
                <td className="px-5 py-3 text-sm text-slate-600 font-mono">{es[0]?.radio || <span className="text-slate-300">—</span>}</td>
                <td className="px-5 py-3 text-sm text-slate-600 font-mono">{es[0]?.indicativo || <span className="text-slate-300">—</span>}</td>
              </>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function EscalaGeral() {
  const hoje = new Date()
  const [data, setData] = useState(hoje.toISOString().slice(0,10))
  const [pdfLoading, setPdfLoading] = useState(false)

  const dataObj = new Date(data + 'T00:00:00')
  const aba = toAba(dataObj)
  const diaSem = DIAS_PT[dataObj.getDay()]
  const dataFmt = `${diaSem}, ${dataObj.getDate()} de ${MESES_PT[dataObj.getMonth()]} de ${dataObj.getFullYear()}`
  const isFds = dataObj.getDay() === 0 || dataObj.getDay() === 6

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
    <div className="flex flex-col h-full bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-8 py-4 flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-bold text-[#0B1929]">Escala Geral</h1>
          <p className={`text-sm mt-0.5 font-medium ${isFds ? 'text-blue-600' : 'text-slate-500'}`}>{dataFmt}</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => navDia(-1)}
            className="w-8 h-8 flex items-center justify-center border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-500 hover:text-[#0B1929] transition-colors">
            ‹
          </button>
          <input type="date" value={data} onChange={e => setData(e.target.value)}
            className="px-3 py-1.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-[#2E7FD4] bg-white" />
          <button onClick={() => navDia(1)}
            className="w-8 h-8 flex items-center justify-center border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-500 hover:text-[#0B1929] transition-colors">
            ›
          </button>
          <button onClick={downloadPdf} disabled={pdfLoading || !entradas.length}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-[#0B1929] disabled:opacity-40 transition-colors">
            {pdfLoading ? '⏳' : '📥'} PDF
          </button>
        </div>
      </div>

      {/* Conteúdo */}
      <div className="flex-1 overflow-y-auto p-6">
        {(isLoading || isFetching) && <Loading text="A carregar escala..." />}
        {error && <ErrorBox message={error.message} />}

        {!isLoading && !error && entradas.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center text-3xl">📅</div>
            <div className="text-center">
              <p className="font-display font-semibold text-slate-600">Escala não publicada</p>
              <p className="text-sm text-slate-400 mt-1">Ainda não existe escala publicada para {aba}</p>
            </div>
          </div>
        )}

        {!isLoading && entradas.length > 0 && (
          <div className="max-w-5xl mx-auto">
            <SecaoAusencias aus={g.ausencias} adm={g.adm} />
            <Secao titulo="Atendimento" entradas={g.atendimento} />
            <Secao titulo="Apoio ao Atendimento" entradas={g.apoio} />
            <Secao titulo="Patrulha Ocorrências" entradas={g.po} colunas />
            <Secao titulo="Patrulhas" entradas={g.patrulhas} colunas />
            <Secao titulo="Remunerados" entradas={g.remunerados} />
            <Secao titulo="Outros" entradas={g.outros} />
          </div>
        )}
      </div>
    </div>
  )
}
