import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Card, StatCard } from '../components/ui'
import { useAuth } from '../store/auth'

export default function Dashboard() {
  const { user } = useAuth()
  const ano = new Date().getFullYear()

  const { data: util } = useQuery({ queryKey: ['utilizadores'], queryFn: api.utilizadores, staleTime: 5*60*1000 })
  const { data: disp } = useQuery({ queryKey: ['dispensas'], queryFn: api.dispensas, staleTime: 60*1000 })
  const { data: ferias } = useQuery({ queryKey: ['ferias', ano], queryFn: () => api.ferias(ano), staleTime: 5*60*1000 })

  const totalMil = util?.utilizadores?.length || 0
  const dispensasActivas = (disp?.dispensas || []).filter(d => {
    const hoje = new Date().toISOString().slice(0,10).split('-').reverse().join('/')
    return !d.fim || d.fim >= hoje
  }).length
  const totalFerias = ferias?.ferias?.length || 0

  const hora = new Date().getHours()
  const saudacao = hora < 12 ? 'Bom dia' : hora < 18 ? 'Boa tarde' : 'Boa noite'

  return (
    <div>
      <PageHeader
        icon="📊"
        title="Dashboard"
        subtitle={`${saudacao}, ${user?.nome?.split(' ')[0] || 'Admin'}`}
      />

      <div className="p-6 space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          <StatCard icon="👥" label="Efetivo" value={totalMil} color="navy" />
          <StatCard icon="🏥" label="Dispensas Activas" value={dispensasActivas} color="amber" />
          <StatCard icon="🏖️" label="Períodos de Férias" value={totalFerias} color="blue" />
          <StatCard icon="📅" label="Ano" value={ano} color="green" />
        </div>

        {/* Acesso rápido */}
        <Card className="p-5">
          <div className="font-display font-semibold text-[#0B1929] mb-4">Acesso Rápido</div>
          <div className="grid grid-cols-3 gap-3">
            {[
              { href: '/admin/escala-geral', icon: '📅', label: 'Escala Geral' },
              { href: '/admin/gerar-escala', icon: '⚙️', label: 'Gerar Escala' },
              { href: '/admin/publicar', icon: '📢', label: 'Publicar' },
              { href: '/admin/dispensas', icon: '🏥', label: 'Dispensas' },
              { href: '/admin/remunerados', icon: '💶', label: 'Remunerados' },
              { href: '/admin/alertas', icon: '🚨', label: 'Alertas' },
            ].map(({href, icon, label}) => (
              <a key={href} href={href}
                className="flex items-center gap-3 p-3 rounded-xl border border-slate-200 hover:border-[#2E7FD4] hover:bg-[#2E7FD4]/5 transition-all group">
                <span className="text-xl">{icon}</span>
                <span className="text-sm font-display font-medium text-slate-700 group-hover:text-[#2E7FD4]">{label}</span>
              </a>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
