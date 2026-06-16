import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Badge } from '../components/ui'

export default function Ferias() {
  const ano = new Date().getFullYear()
  const { data, isLoading, error } = useQuery({ queryKey:['ferias',ano], queryFn:()=>api.ferias(ano), staleTime:5*60*1000 })
  const ferias = data?.ferias || []
  const porMilitar = ferias.reduce((m,f)=>{ if(!m[f.id])m[f.id]={nome:f.nome,periodos:[]}; m[f.id].periodos.push(f); return m }, {})

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'#f8f9fa' }}>
      <PageHeader icon="🏖️" title="Férias" subtitle={`${Object.keys(porMilitar).length} militares com férias em ${ano}`} />
      <div style={{ flex:1, overflowY:'auto', padding:24 }}>
        {isLoading && <Loading />}
        {error && <ErrorBox message={error.message} />}
        {!isLoading && !error && (
          <div style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, overflow:'hidden' }}>
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
              <thead><tr style={{ background:'#f8f9fa', borderBottom:'1px solid #dee2e6' }}>
                {['Militar','Período','Dias'].map(h=><th key={h} style={{ textAlign:'left', padding:'10px 20px', fontSize:11, fontWeight:600, color:'#6c757d', textTransform:'uppercase', letterSpacing:'0.05em' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {Object.entries(porMilitar).map(([id,{nome,periodos}]) =>
                  periodos.map((p,i)=>(
                    <tr key={`${id}-${i}`} style={{ borderBottom:'1px solid #f8f9fa' }}>
                      {i===0 && <td style={{ padding:'10px 20px', fontWeight:500, color:'#0f2540', verticalAlign:'top' }} rowSpan={periodos.length}>{nome}</td>}
                      <td style={{ padding:'10px 20px', fontFamily:'monospace', fontSize:12, color:'#495057' }}>{p.inicio} → {p.fim||'—'}</td>
                      <td style={{ padding:'10px 20px' }}>{p.dias && <Badge color="blue">{p.dias}d</Badge>}</td>
                    </tr>
                  ))
                )}
                {ferias.length===0 && <tr><td colSpan={3} style={{ padding:'40px', textAlign:'center', color:'#adb5bd' }}>Sem férias registadas para {ano}</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
