import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Card, Badge, Button, Input } from '../components/ui'

const DIAS_PT = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb']

function toAba(date) {
  return `${String(date.getDate()).padStart(2,'0')}-${String(date.getMonth()+1).padStart(2,'0')}`
}

export default function GerarEscala() {
  const hoje = new Date()
  const [dataInicio, setDataInicio] = useState(hoje.toISOString().slice(0,10))
  const [dataFim, setDataFim] = useState(hoje.toISOString().slice(0,10))
  const [resultado, setResultado] = useState(null)
  const [msg, setMsg] = useState('')

  const gerarMut = useMutation({
    mutationFn: (body) => api.gerarEscala(body),
    onSuccess: (data) => {
      setResultado(data)
      setMsg('')
    },
    onError: e => setMsg('❌ ' + e.message),
  })

  const guardarMut = useMutation({
    mutationFn: (body) => api.guardarEscala(body),
    onSuccess: () => {
      setMsg('✅ Escala guardada com sucesso!')
      setResultado(null)
      setTimeout(() => setMsg(''), 4000)
    },
    onError: e => setMsg('❌ ' + e.message),
  })

  function gerar() {
    const di = new Date(dataInicio + 'T00:00:00')
    const df = new Date(dataFim + 'T00:00:00')
    const dias = []
    const d = new Date(di)
    while (d <= df) {
      dias.push(toAba(d))
      d.setDate(d.getDate() + 1)
    }
    gerarMut.mutate({ dias })
  }

  function guardar() {
    guardarMut.mutate({ resultado })
  }

  const diasGerados = resultado?.resultados || []

  return (
    <div>
      <PageHeader icon="⚙️" title="Gerar Escala" subtitle="Geração automática" />

      <div className="p-6 space-y-4">
        {msg && (
          <div className={`flex items-center gap-2 p-3 rounded-lg text-sm border ${msg.startsWith('✅') ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700'}`}>
            {msg}
          </div>
        )}

        <Card className="p-5">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <Input label="Data Início" type="date" value={dataInicio} onChange={e => setDataInicio(e.target.value)} />
            <Input label="Data Fim" type="date" value={dataFim} onChange={e => setDataFim(e.target.value)} />
          </div>
          <Button onClick={gerar} loading={gerarMut.isPending} className="w-full">
            ⚙️ Gerar Escala Automática
          </Button>
        </Card>

        {gerarMut.isPending && <Loading text="A gerar escala... pode demorar alguns segundos" />}

        {resultado && diasGerados.length > 0 && (
          <>
            <div className="flex items-center justify-between">
              <span className="font-display font-semibold text-[#0B1929]">
                {diasGerados.length} dia{diasGerados.length > 1 ? 's' : ''} gerado{diasGerados.length > 1 ? 's' : ''}
              </span>
              <Button onClick={guardar} loading={guardarMut.isPending} variant="success">
                💾 Guardar na Escala
              </Button>
            </div>

            {diasGerados.map((res, i) => {
              const d = new Date(res.data + 'T00:00:00') 
              const diaSem = DIAS_PT[d.getDay()]
              const isFds = d.getDay() === 0 || d.getDay() === 6

              // Agrupar por serviço
              const porServ = {}
              for (const [mid, serv, hor] of (res.escalados || [])) {
                const k = `${serv}|${hor}`
                if (!porServ[k]) porServ[k] = { serv, hor, ids: [] }
                porServ[k].ids.push(mid)
              }

              return (
                <Card key={i} className="overflow-hidden">
                  <div className={`px-5 py-2.5 border-b flex items-center justify-between ${isFds ? 'bg-blue-50' : 'bg-slate-50'}`}>
                    <span className={`font-display font-bold text-sm ${isFds ? 'text-blue-700' : 'text-[#0B1929]'}`}>
                      {diaSem}, {res.data}
                    </span>
                    <div className="flex gap-2">
                      <Badge color="green">{res.escalados?.length || 0} escalados</Badge>
                      {res.disponiveis?.length > 0 && <Badge color="blue">{res.disponiveis.length} disponíveis</Badge>}
                      {res.avisos?.length > 0 && <Badge color="amber">{res.avisos.length} avisos</Badge>}
                    </div>
                  </div>
                  <div className="p-4">
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(porServ).map(([k, {serv, hor, ids}]) => (
                        <div key={k} className="flex items-start gap-2 p-2 bg-slate-50 rounded-lg">
                          <div className="flex-1">
                            <span className="text-xs font-bold text-[#0B1929]">{serv}</span>
                            {hor && <span className="text-xs text-slate-400 ml-1">({hor})</span>}
                            <div className="text-xs text-slate-500 mt-0.5">{ids.join(', ')}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                    {res.avisos?.length > 0 && (
                      <details className="mt-2">
                        <summary className="text-xs text-amber-600 cursor-pointer">⚠️ {res.avisos.length} avisos</summary>
                        <div className="mt-1 space-y-1">
                          {res.avisos.map((av, j) => (
                            <div key={j} className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded">{av}</div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                </Card>
              )
            })}

            <Button onClick={guardar} loading={guardarMut.isPending} variant="success" className="w-full">
              💾 Guardar na Escala
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
