import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Card, Badge } from '../components/ui'

const COR_GIRO = { 'I':'blue', 'II':'green', 'III':'amber', 'IV':'navy' }

export default function Giros() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['giros'],
    queryFn: api.giros,
    staleTime: 10 * 60 * 1000,
  })

  const giros = data?.giros || []
  const porGiro = giros.reduce((m,g) => { if(!m[g.giro])m[g.giro]=[]; m[g.giro].push(g); return m }, {})

  return (
    <div>
      <PageHeader icon="🔄" title="Giros" subtitle={`${giros.length} militares com giro atribuído`} />
      <div className="p-6">
        {isLoading && <Loading />}
        {error && <ErrorBox message={error.message} />}
        {!isLoading && !error && (
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(porGiro).sort().map(([giro, militares]) => (
              <Card key={giro} className="overflow-hidden">
                <div className="px-5 py-2.5 bg-[#0B1929] text-white flex items-center justify-between">
                  <span className="font-display font-bold text-sm">Giro {giro}</span>
                  <Badge color={COR_GIRO[giro] || 'slate'}>{militares.length} militares</Badge>
                </div>
                <div className="divide-y divide-slate-50">
                  {militares.map(m => (
                    <div key={m.id} className="flex items-center justify-between px-5 py-2.5">
                      <span className="text-sm text-[#0B1929] font-medium">{m.nome}</span>
                      <span className="text-xs text-slate-400 font-mono">{m.posto}</span>
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
