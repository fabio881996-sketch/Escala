import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Card, Badge, Button } from '../components/ui'

const DIAS_PT = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb']
const MESES_PT = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

function toAba(date) {
  return `${String(date.getDate()).padStart(2,'0')}-${String(date.getMonth()+1).padStart(2,'0')}`
}

export default function Publicar() {
  const qc = useQueryClient()
  const [msg, setMsg] = useState('')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dias-publicados'],
    queryFn: () => api.get('/api/escala/publicados'),
    staleTime: 30 * 1000,
  })

  const { data: abas } = useQuery({
    queryKey: ['lista-abas'],
    queryFn: () => api.get('/admin/api/lista-abas'),
    staleTime: 60 * 1000,
  })

  const pubMut = useMutation({
    mutationFn: (aba) => api.post(`/api/escala/publicar/${aba}`, {}),
    onSuccess: (_, aba) => {
      qc.invalidateQueries(['dias-publicados'])
      setMsg(`✅ Escala ${aba} publicada!`)
      setTimeout(() => setMsg(''), 4000)
    },
    onError: e => setMsg('❌ ' + e.message),
  })

  const despubMut = useMutation({
    mutationFn: (aba) => api.post(`/api/escala/despublicar/${aba}`, {}),
    onSuccess: (_, aba) => {
      qc.invalidateQueries(['dias-publicados'])
      setMsg(`✅ Escala ${aba} despublicada!`)
      setTimeout(() => setMsg(''), 4000)
    },
    onError: e => setMsg('❌ ' + e.message),
  })

  const diasPub = data?.dias || []
  const todasAbas = abas?.abas || []

  // Gerar próximos 30 dias
  const hoje = new Date()
  const proximos = Array.from({length:30},(_,i) => {
    const d = new Date(hoje)
    d.setDate(d.getDate() + i)
    return d
  })

  return (
    <div>
      <PageHeader icon="📢" title="Publicar Escala" subtitle={`${diasPub.length} dias publicados`} />

      <div className="p-6 space-y-4">
        {msg && (
          <div className={`flex items-center gap-2 p-3 rounded-lg text-sm border ${msg.startsWith('✅') ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700'}`}>
            {msg}
          </div>
        )}

        {isLoading && <Loading />}
        {error && <ErrorBox message={error.message} />}

        <Card>
          <div className="px-5 py-3 border-b border-slate-100">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Próximos 30 dias</span>
          </div>
          <div className="divide-y divide-slate-50">
            {proximos.map(d => {
              const aba = toAba(d)
              const temEscala = todasAbas.includes(aba)
              const publicado = diasPub.includes(aba)
              const diaSem = DIAS_PT[d.getDay()]
              const isFds = d.getDay() === 0 || d.getDay() === 6

              return (
                <div key={aba} className={`flex items-center justify-between px-5 py-3 hover:bg-slate-50 ${isFds ? 'bg-blue-50/30' : ''}`}>
                  <div className="flex items-center gap-3">
                    <div className="w-16 text-center">
                      <div className={`text-xs font-bold ${isFds ? 'text-blue-600' : 'text-slate-400'}`}>{diaSem}</div>
                      <div className="text-sm font-bold text-[#0B1929]">{String(d.getDate()).padStart(2,'0')}</div>
                      <div className="text-xs text-slate-400">{MESES_PT[d.getMonth()]}</div>
                    </div>
                    <div className="font-mono text-xs text-slate-400">{aba}</div>
                    {publicado && <Badge color="green">Publicado</Badge>}
                    {!publicado && temEscala && <Badge color="amber">Com escala</Badge>}
                    {!temEscala && <Badge color="slate">Sem escala</Badge>}
                  </div>
                  <div className="flex gap-2">
                    {!publicado && temEscala && (
                      <Button
                        size="sm"
                        onClick={() => pubMut.mutate(aba)}
                        loading={pubMut.isPending && pubMut.variables === aba}
                      >
                        📢 Publicar
                      </Button>
                    )}
                    {publicado && (
                      <Button
                        size="sm" variant="danger"
                        onClick={() => { if(confirm(`Despublicar ${aba}?`)) despubMut.mutate(aba) }}
                        loading={despubMut.isPending && despubMut.variables === aba}
                      >
                        Despublicar
                      </Button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      </div>
    </div>
  )
}
