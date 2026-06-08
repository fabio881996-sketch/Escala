import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Card, Badge } from '../components/ui'

export default function Ferias() {
  const ano = new Date().getFullYear()

  const { data, isLoading, error } = useQuery({
    queryKey: ['ferias', ano],
    queryFn: () => api.ferias(ano),
    staleTime: 5 * 60 * 1000,
  })

  const ferias = data?.ferias || []

  // Agrupar por militar
  const porMilitar = ferias.reduce((m,f) => {
    if (!m[f.id]) m[f.id] = { nome: f.nome, periodos: [] }
    m[f.id].periodos.push(f)
    return m
  }, {})

  return (
    <div>
      <PageHeader icon="🏖️" title="Férias" subtitle={`${Object.keys(porMilitar).length} militares com férias em ${ano}`} />

      <div className="p-6">
        {isLoading && <Loading />}
        {error && <ErrorBox message={error.message} />}
        {!isLoading && !error && (
          <Card>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500">Militar</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500">Período</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500">Dias</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {Object.entries(porMilitar).map(([id, {nome, periodos}]) =>
                  periodos.map((p, i) => (
                    <tr key={`${id}-${i}`} className="hover:bg-slate-50">
                      {i === 0 && (
                        <td className="px-5 py-3 font-medium text-[#0B1929]" rowSpan={periodos.length}>
                          {nome}
                        </td>
                      )}
                      <td className="px-5 py-3 text-slate-600 text-xs font-mono">
                        {p.inicio} → {p.fim || '—'}
                      </td>
                      <td className="px-5 py-3">
                        {p.dias && <Badge color="blue">{p.dias}d</Badge>}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            {ferias.length === 0 && (
              <div className="text-center py-12 text-slate-400">
                <div className="text-4xl mb-3">🏖️</div>
                <p>Sem férias registadas para {ano}</p>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  )
}
