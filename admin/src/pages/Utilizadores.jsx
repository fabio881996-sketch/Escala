import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Card, Badge, Button, Input } from '../components/ui'

export default function Utilizadores() {
  const qc = useQueryClient()
  const [editId, setEditId] = useState(null)
  const [newPin, setNewPin] = useState('')
  const [msg, setMsg] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['utilizadores'],
    queryFn: api.utilizadores,
    staleTime: 5 * 60 * 1000,
  })

  const updateMut = useMutation({
    mutationFn: ({ id, body }) => api.updateUtilizador(id, body),
    onSuccess: () => {
      qc.invalidateQueries(['utilizadores'])
      setEditId(null)
      setNewPin('')
      setMsg('✅ PIN actualizado!')
      setTimeout(() => setMsg(''), 3000)
    },
  })

  const militares = data?.utilizadores || []

  return (
    <div>
      <PageHeader icon="👤" title="Gerir Utilizadores" subtitle={`${militares.length} contas registadas`} />

      <div className="p-8">
        {msg && (
          <div className="mb-4 flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
            {msg}
          </div>
        )}
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
                    <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Admin</th>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">PIN</th>
                    <th className="px-5 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {militares.map(m => (
                    <tr key={m.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-5 py-3 font-mono text-xs text-slate-400">{m.id}</td>
                      <td className="px-5 py-3 font-medium text-[#0B1929]">{m.nome}</td>
                      <td className="px-5 py-3 text-slate-600">{m.posto}</td>
                      <td className="px-5 py-3">
                        {m.is_admin && <Badge color="navy">Admin</Badge>}
                      </td>
                      <td className="px-5 py-3">
                        {editId === m.id ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="password"
                              value={newPin}
                              onChange={e => setNewPin(e.target.value.slice(0, 4))}
                              maxLength={4}
                              placeholder="Novo PIN"
                              className="w-24 px-2 py-1 border border-[#2E7FD4] rounded-lg text-sm focus:outline-none"
                              autoFocus
                            />
                            <Button
                              size="sm"
                              onClick={() => updateMut.mutate({ id: m.id, body: { pin: newPin } })}
                              disabled={newPin.length !== 4}
                              loading={updateMut.isPending}
                            >
                              ✓
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setEditId(null)}>✕</Button>
                          </div>
                        ) : (
                          <span className="text-slate-300 font-mono text-xs">
                            {m.tem_pin ? '••••' : <span className="text-amber-500">Sem PIN</span>}
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right">
                        {editId !== m.id && (
                          <Button size="sm" variant="secondary" onClick={() => { setEditId(m.id); setNewPin('') }}>
                            ✏️ Editar PIN
                          </Button>
                        )}
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
