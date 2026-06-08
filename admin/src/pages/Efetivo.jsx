import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Card, Badge } from '../components/ui'

export default function Efetivo() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['efetivo'],
    queryFn: api.efetivo,
    staleTime: 5 * 60 * 1000,
  })

  const militares = data?.militares || []

  return (
    <div>
      <PageHeader icon="👥" title="Efetivo" subtitle={`${militares.length} militares`} />

      <div className="p-8">
        {isLoading && <Loading />}
        {error && <ErrorBox message={error.message} />}
        {!isLoading && !error && (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">ID</th>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Nome</th>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Posto</th>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {militares.map(m => (
                    <tr key={m.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-5 py-3 font-mono text-xs text-slate-400">{m.id}</td>
                      <td className="px-5 py-3 font-medium text-[#0B1929]">{m.nome}</td>
                      <td className="px-5 py-3 text-slate-600">{m.posto}</td>
                      <td className="px-5 py-3">
                        <Badge color={m.disponivel ? 'green' : 'slate'}>
                          {m.disponivel ? 'Activo' : 'Inactivo'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
