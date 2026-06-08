import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Card, Badge, Button, Select, Input } from '../components/ui'

const TABS = ['A', 'B']

export default function Remunerados() {
  const hoje = new Date().toISOString().slice(0,10)
  const [data, setData] = useState(hoje)
  const [slots, setSlots] = useState([{ hor: '', n: 2, tab: 'A', obs: '' }])
  const [resultado, setResultado] = useState(null)
  const [msg, setMsg] = useState('')

  const { data: util } = useQuery({ queryKey: ['utilizadores'], queryFn: api.utilizadores, staleTime: 5*60*1000 })

  const calcMut = useMutation({
    mutationFn: (body) => api.post('/admin/api/remunerados/calcular', body),
    onSuccess: (data) => setResultado(data),
    onError: e => setMsg('❌ ' + e.message),
  })

  const confMut = useMutation({
    mutationFn: (body) => api.post('/admin/api/remunerados/confirmar', body),
    onSuccess: () => {
      setMsg('✅ Nomeação confirmada!')
      setResultado(null)
      setTimeout(() => setMsg(''), 4000)
    },
    onError: e => setMsg('❌ ' + e.message),
  })

  function addSlot() {
    setSlots(s => [...s, { hor: '', n: 2, tab: 'A', obs: '' }])
  }

  function removeSlot(i) {
    setSlots(s => s.filter((_,j) => j !== i))
  }

  function updateSlot(i, key, val) {
    setSlots(s => s.map((slot,j) => j === i ? {...slot, [key]: val} : slot))
  }

  function calcular() {
    const dt = new Date(data + 'T00:00:00')
    const aba = `${String(dt.getDate()).padStart(2,'0')}-${String(dt.getMonth()+1).padStart(2,'0')}`
    const dataFmt = `${String(dt.getDate()).padStart(2,'0')}/${String(dt.getMonth()+1).padStart(2,'0')}/${dt.getFullYear()}`
    calcMut.mutate({ aba, data: dataFmt, slots })
  }

  function confirmar() {
    confMut.mutate({ resultado })
  }

  const corGrupo = (g) => {
    if (g.includes('Voluntário c/ serviço') || g.includes('Voluntário disponível')) return 'green'
    if (g.includes('folga')) return 'blue'
    if (g.includes('Não voluntário')) return 'amber'
    return 'slate'
  }

  return (
    <div>
      <PageHeader icon="💶" title="Remunerados" subtitle="Nomeação automática" />

      <div className="p-6 space-y-4">
        {msg && (
          <div className={`flex items-center gap-2 p-3 rounded-lg text-sm border ${msg.startsWith('✅') ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700'}`}>
            {msg}
          </div>
        )}

        <Card className="p-5">
          <div className="mb-4">
            <Input label="Data" type="date" value={data} onChange={e => setData(e.target.value)} />
          </div>

          <div className="font-display font-semibold text-[#0B1929] text-sm mb-3">Remunerados a nomear</div>

          <div className="space-y-3">
            {slots.map((slot, i) => (
              <div key={i} className="grid grid-cols-5 gap-3 items-end p-3 bg-slate-50 rounded-xl">
                <Input
                  label={`Horário ${i+1}`}
                  value={slot.hor}
                  onChange={e => updateSlot(i,'hor',e.target.value)}
                  placeholder="ex: 08-12"
                />
                <div className="space-y-1">
                  <label className="block text-xs font-medium text-slate-600 tracking-wide uppercase">Nº Mil.</label>
                  <input type="number" min={1} max={10} value={slot.n}
                    onChange={e => updateSlot(i,'n',parseInt(e.target.value))}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-[#2E7FD4]" />
                </div>
                <Select label="Tabela" value={slot.tab} onChange={e => updateSlot(i,'tab',e.target.value)}>
                  <option value="A">A</option>
                  <option value="B">B</option>
                </Select>
                <Input
                  label="Observação"
                  value={slot.obs}
                  onChange={e => updateSlot(i,'obs',e.target.value)}
                  placeholder="ex: Reg. Trânsito"
                />
                <div className="flex gap-2">
                  {i > 0 && (
                    <button onClick={() => removeSlot(i)}
                      className="px-3 py-2 text-red-400 hover:text-red-600 border border-red-200 rounded-lg text-sm transition-colors">
                      🗑️
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="flex gap-3 mt-4">
            <Button variant="secondary" onClick={addSlot}>➕ Adicionar remunerado</Button>
            <Button onClick={calcular} loading={calcMut.isPending} disabled={!slots.some(s => s.hor)}>
              🔍 Calcular Nomeação
            </Button>
          </div>
        </Card>

        {calcMut.isPending && <Loading text="A calcular nomeação..." />}

        {resultado && (
          <Card className="overflow-hidden">
            <div className="px-5 py-3 bg-[#0B1929] text-white font-display font-semibold text-sm">
              Resultado da Nomeação
            </div>
            <div className="divide-y divide-slate-100">
              {resultado.resultados?.map((res, i) => (
                <div key={i} className="p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <span className="font-display font-bold text-[#0B1929]">
                        Remunerado {i+1} — Tabela {res.slot?.tab}
                      </span>
                      <span className="ml-2 font-mono text-sm text-slate-500">{res.slot?.hor}</span>
                    </div>
                    <Badge color={res.nomeados?.length >= res.slot?.n ? 'green' : 'red'}>
                      {res.nomeados?.length}/{res.slot?.n} nomeados
                    </Badge>
                  </div>

                  {res.nomeados?.length > 0 ? (
                    <div className="space-y-2">
                      {res.nomeados.map((n, j) => (
                        <div key={j} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                          <div>
                            <span className="font-medium text-sm text-[#0B1929]">{n.nome}</span>
                            <span className="text-xs text-slate-400 ml-2">({n.id})</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge color={corGrupo(n.grupo)}>{n.grupo}</Badge>
                            <span className="text-xs text-slate-400">{n.total}h acum.</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-red-500 bg-red-50 p-3 rounded-lg">
                      ❌ Não foi possível nomear militares suficientes
                    </div>
                  )}

                  {res.avisos?.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {res.avisos.map((av, j) => (
                        <div key={j} className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-3 py-1.5"
                          dangerouslySetInnerHTML={{__html: av}} />
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {resultado.resultados?.some(r => r.nomeados?.length > 0) && (
              <div className="px-5 py-4 border-t border-slate-100 bg-slate-50">
                <Button onClick={confirmar} loading={confMut.isPending} className="w-full">
                  ✅ Confirmar Nomeação e Escrever na Escala
                </Button>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  )
}
