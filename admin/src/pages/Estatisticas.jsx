import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Card, StatCard, Select } from '../components/ui'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const CORES = ['#2E7FD4','#0B1929','#C9A84C','#16A34A','#DC2626','#7C3AED','#0891B2','#D97706']

export default function Estatisticas() {
  const ano = new Date().getFullYear()
  const [milId, setMilId] = useState('')

  const { data: util } = useQuery({ queryKey: ['utilizadores'], queryFn: api.utilizadores, staleTime: 5*60*1000 })
  const militares = util?.utilizadores || []

  const { data, isLoading, error } = useQuery({
    queryKey: ['estatisticas', milId, ano],
    queryFn: () => api.estatisticas(milId || '_todos', ano),
    enabled: !!milId,
    staleTime: 5 * 60 * 1000,
  })

  const servicos = data?.servicos || []
  const total = data?.total || 0

  return (
    <div>
      <PageHeader icon="📊" title="Estatísticas" subtitle={`Ano ${ano}`} />

      <div className="p-6 space-y-4">
        <Card className="p-5">
          <Select
            label="Militar"
            value={milId}
            onChange={e => setMilId(e.target.value)}
          >
            <option value="">Selecionar militar...</option>
            {militares.map(m => (
              <option key={m.id} value={m.id}>{m.posto} {m.nome}</option>
            ))}
          </Select>
        </Card>

        {!milId && (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
            <span className="text-5xl opacity-30">📊</span>
            <p className="font-display font-semibold text-slate-500">Seleciona um militar para ver as estatísticas</p>
          </div>
        )}

        {milId && isLoading && <Loading />}
        {milId && error && <ErrorBox message={error.message} />}

        {milId && !isLoading && !error && (
          <>
            <div className="grid grid-cols-3 gap-4">
              <StatCard icon="📋" label="Total Serviços" value={total} color="navy" />
              <StatCard icon="👤" label="Militar" value={data?.nome?.split(' ').slice(-1)[0] || '—'} color="blue" />
              <StatCard icon="📅" label="Tipos diferentes" value={servicos.length} color="green" />
            </div>

            {servicos.length > 0 && (
              <>
                <Card className="p-5">
                  <div className="font-display font-semibold text-[#0B1929] mb-4">Distribuição por Serviço</div>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={servicos.slice(0,12)} margin={{top:0,right:20,bottom:40,left:0}}>
                      <XAxis dataKey="servico" tick={{fontSize:10}} angle={-35} textAnchor="end" interval={0} />
                      <YAxis tick={{fontSize:11}} />
                      <Tooltip formatter={(v, n) => [v, 'Serviços']} />
                      <Bar dataKey="total" radius={[4,4,0,0]}>
                        {servicos.slice(0,12).map((_, i) => (
                          <Cell key={i} fill={CORES[i % CORES.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </Card>

                <Card>
                  <div className="px-5 py-3 border-b border-slate-100">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Detalhe</span>
                  </div>
                  <table className="w-full text-sm">
                    <tbody className="divide-y divide-slate-50">
                      {servicos.map((s, i) => (
                        <tr key={i} className="hover:bg-slate-50">
                          <td className="px-5 py-3 font-medium text-[#0B1929]">{s.servico}</td>
                          <td className="px-5 py-3 text-right">
                            <span className="font-display font-bold text-[#2E7FD4]">{s.total}</span>
                            <span className="text-xs text-slate-400 ml-1">serviços</span>
                          </td>
                          <td className="px-5 py-3 w-40">
                            <div className="w-full bg-slate-100 rounded-full h-1.5">
                              <div className="h-1.5 rounded-full bg-[#2E7FD4]"
                                style={{width: `${Math.round(s.total/total*100)}%`}} />
                            </div>
                          </td>
                          <td className="px-5 py-3 text-right text-xs text-slate-400">
                            {Math.round(s.total/total*100)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Card>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}
