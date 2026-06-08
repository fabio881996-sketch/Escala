import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Card, Badge, Button } from '../components/ui'

function toAba(date) {
  return `${String(date.getDate()).padStart(2,'0')}-${String(date.getMonth()+1).padStart(2,'0')}`
}

export default function Alertas() {
  const hoje = new Date()
  const [data, setData] = useState(hoje.toISOString().slice(0,10))
  const aba = toAba(new Date(data + 'T00:00:00'))

  const { data: res, isLoading, error } = useQuery({
    queryKey: ['alertas', aba],
    queryFn: () => api.get(`/admin/api/alertas?aba=${aba}`),
    staleTime: 60 * 1000,
  })

  const alertas = res?.alertas || []
  const total = res?.total || 0

  return (
    <div>
      <PageHeader
        icon="🚨" title="Alertas" subtitle={total > 0 ? `${total} alertas encontrados` : 'Sem alertas'}
        actions={
          <input type="date" value={data} onChange={e => setData(e.target.value)}
            className="px-3 py-1.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-[#2E7FD4]" />
        }
      />

      <div className="p-6">
        {isLoading && <Loading />}
        {error && <ErrorBox message={error.message} />}
        {!isLoading && !error && alertas.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
            <span className="text-5xl">✅</span>
            <p className="font-display font-semibold text-slate-500">Sem alertas para {aba}</p>
          </div>
        )}
        {alertas.length > 0 && (
          <Card>
            <div className="divide-y divide-slate-100">
              {alertas.map((a, i) => (
                <div key={i} className="flex items-start gap-3 px-5 py-4">
                  <span className="text-lg mt-0.5">
                    {a.tipo === 'duplicado' ? '⚠️' : a.tipo === 'consecutivo' ? '🔄' : '❗'}
                  </span>
                  <div>
                    <div className="font-medium text-[#0B1929] text-sm">{a.militar}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{a.mensagem}</div>
                  </div>
                  <Badge color={a.tipo === 'duplicado' ? 'red' : 'amber'} className="ml-auto shrink-0">
                    {a.tipo}
                  </Badge>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
