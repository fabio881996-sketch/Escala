import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Card, Badge, Button, Input, Select } from '../components/ui'

const TIPOS = ['Convalescença','Licença','Outras Licenças','Diligência','Tribunal','Instrução','FCAA CTer','Folga Complementar']

const COR_TIPO = {
  'Convalescença': 'amber',
  'Licença': 'blue',
  'Outras Licenças': 'blue',
  'Diligência': 'slate',
  'Tribunal': 'slate',
  'Instrução': 'navy',
  'FCAA CTer': 'red',
  'Folga Complementar': 'green',
}

export default function Dispensas() {
  const qc = useQueryClient()
  const [mostrarForm, setMostrarForm] = useState(false)
  const [form, setForm] = useState({ id: '', tipo: TIPOS[0], inicio: '', fim: '', obs: '' })
  const [filtro, setFiltro] = useState('')
  const [msg, setMsg] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['dispensas'],
    queryFn: api.dispensas,
    staleTime: 60 * 1000,
  })

  const { data: util } = useQuery({
    queryKey: ['utilizadores'],
    queryFn: api.utilizadores,
    staleTime: 5 * 60 * 1000,
  })

  const addMut = useMutation({
    mutationFn: api.adicionarDispensa,
    onSuccess: () => {
      qc.invalidateQueries(['dispensas'])
      setMostrarForm(false)
      setForm({ id: '', tipo: TIPOS[0], inicio: '', fim: '', obs: '' })
      setMsg('✅ Dispensa registada!')
      setTimeout(() => setMsg(''), 3000)
    },
    onError: e => setMsg('❌ ' + e.message),
  })

  const delMut = useMutation({
    mutationFn: api.removerDispensa,
    onSuccess: () => {
      qc.invalidateQueries(['dispensas'])
      setMsg('✅ Dispensa removida!')
      setTimeout(() => setMsg(''), 3000)
    },
  })

  const militares = util?.utilizadores || []
  const dispensas = (data?.dispensas || []).filter(d =>
    !filtro || d.nome?.toLowerCase().includes(filtro.toLowerCase()) || d.tipo?.toLowerCase().includes(filtro.toLowerCase())
  )

  // Agrupar activas vs passadas
  const hoje = new Date().toISOString().slice(0,10).split('-').reverse().join('/')
  const activas = dispensas.filter(d => d.activa !== false)
  const passadas = dispensas.filter(d => d.activa === false)

  function handleAdd(e) {
    e.preventDefault()
    if (!form.id || !form.inicio) return
    addMut.mutate(form)
  }

  return (
    <div>
      <PageHeader
        icon="🏥" title="Dispensas" subtitle={`${activas.length} activas`}
        actions={
          <Button onClick={() => setMostrarForm(!mostrarForm)}>
            {mostrarForm ? '✕ Cancelar' : '➕ Nova Dispensa'}
          </Button>
        }
      />

      <div className="p-6 space-y-4">
        {msg && (
          <div className={`flex items-center gap-2 p-3 rounded-lg text-sm border ${msg.startsWith('✅') ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700'}`}>
            {msg}
          </div>
        )}

        {/* Formulário */}
        {mostrarForm && (
          <Card className="p-5">
            <div className="font-display font-semibold text-[#0B1929] mb-4">Nova Dispensa</div>
            <form onSubmit={handleAdd} className="grid grid-cols-2 gap-4">
              <Select label="Militar" value={form.id} onChange={e => setForm(f=>({...f,id:e.target.value}))} required>
                <option value="">Selecionar...</option>
                {militares.map(m => (
                  <option key={m.id} value={m.id}>{m.posto} {m.nome} ({m.id})</option>
                ))}
              </Select>
              <Select label="Tipo" value={form.tipo} onChange={e => setForm(f=>({...f,tipo:e.target.value}))}>
                {TIPOS.map(t => <option key={t}>{t}</option>)}
              </Select>
              <Input label="Data Início" type="date" value={form.inicio} onChange={e => setForm(f=>({...f,inicio:e.target.value}))} required />
              <Input label="Data Fim" type="date" value={form.fim} onChange={e => setForm(f=>({...f,fim:e.target.value}))} />
              <div className="col-span-2">
                <Input label="Observações" value={form.obs} onChange={e => setForm(f=>({...f,obs:e.target.value}))} placeholder="Opcional" />
              </div>
              <div className="col-span-2 flex justify-end gap-2">
                <Button type="button" variant="secondary" onClick={() => setMostrarForm(false)}>Cancelar</Button>
                <Button type="submit" loading={addMut.isPending}>Guardar</Button>
              </div>
            </form>
          </Card>
        )}

        {/* Filtro */}
        <div className="flex gap-3">
          <input
            value={filtro}
            onChange={e => setFiltro(e.target.value)}
            placeholder="Filtrar por nome ou tipo..."
            className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-[#2E7FD4]"
          />
        </div>

        {isLoading && <Loading />}
        {error && <ErrorBox message={error.message} />}

        {/* Activas */}
        {activas.length > 0 && (
          <Card>
            <div className="px-5 py-2 bg-amber-50 border-b border-amber-100">
              <span className="text-xs font-bold text-amber-700 uppercase tracking-wider">Activas ({activas.length})</span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="text-left px-5 py-2.5 text-xs font-semibold text-slate-500">Militar</th>
                  <th className="text-left px-5 py-2.5 text-xs font-semibold text-slate-500">Tipo</th>
                  <th className="text-left px-5 py-2.5 text-xs font-semibold text-slate-500">Início</th>
                  <th className="text-left px-5 py-2.5 text-xs font-semibold text-slate-500">Fim</th>
                  <th className="text-left px-5 py-2.5 text-xs font-semibold text-slate-500">Obs</th>
                  <th className="px-5 py-2.5 w-16"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {activas.map(d => (
                  <tr key={d.__row} className="hover:bg-slate-50">
                    <td className="px-5 py-3 font-medium text-[#0B1929]">{d.nome}</td>
                    <td className="px-5 py-3"><Badge color={COR_TIPO[d.tipo] || 'slate'}>{d.tipo}</Badge></td>
                    <td className="px-5 py-3 text-slate-600 text-xs font-mono">{d.inicio}</td>
                    <td className="px-5 py-3 text-slate-600 text-xs font-mono">{d.fim || '—'}</td>
                    <td className="px-5 py-3 text-slate-400 text-xs">{d.obs}</td>
                    <td className="px-5 py-3">
                      <button
                        onClick={() => { if(confirm('Remover esta dispensa?')) delMut.mutate(d.__row) }}
                        className="text-red-400 hover:text-red-600 text-xs transition-colors"
                        disabled={delMut.isPending}
                      >
                        🗑️
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}

        {/* Passadas */}
        {passadas.length > 0 && (
          <details className="group">
            <summary className="cursor-pointer text-sm text-slate-500 hover:text-slate-700 py-2 select-none">
              📋 Histórico ({passadas.length} registos)
            </summary>
            <Card className="mt-2">
              <table className="w-full text-sm">
                <tbody className="divide-y divide-slate-50">
                  {passadas.map(d => (
                    <tr key={d.__row} className="hover:bg-slate-50 opacity-60">
                      <td className="px-5 py-2.5 font-medium text-[#0B1929]">{d.nome}</td>
                      <td className="px-5 py-2.5"><Badge color="slate">{d.tipo}</Badge></td>
                      <td className="px-5 py-2.5 text-slate-500 text-xs font-mono">{d.inicio} → {d.fim}</td>
                      <td className="px-5 py-2.5">
                        <button onClick={() => { if(confirm('Remover?')) delMut.mutate(d.__row) }} className="text-red-300 hover:text-red-500 text-xs">🗑️</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </details>
        )}

        {!isLoading && dispensas.length === 0 && (
          <div className="text-center py-16 text-slate-400">
            <div className="text-4xl mb-3">🏥</div>
            <p className="font-display font-semibold">Sem dispensas registadas</p>
          </div>
        )}
      </div>
    </div>
  )
}
