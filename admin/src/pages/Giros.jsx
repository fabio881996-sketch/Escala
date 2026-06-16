import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { PageHeader, Loading, ErrorBox, Badge } from '../components/ui'

const COR = { 'I':'blue','II':'green','III':'amber','IV':'navy' }

export default function Giros() {
  const { data, isLoading, error } = useQuery({ queryKey:['giros'], queryFn:api.giros, staleTime:10*60*1000 })
  const giros = data?.giros || []
  const porGiro = giros.reduce((m,g)=>{ if(!m[g.giro])m[g.giro]=[]; m[g.giro].push(g); return m }, {})

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'#f8f9fa' }}>
      <PageHeader icon="🔄" title="Giros" subtitle={`${giros.length} militares com giro atribuído`} />
      <div style={{ flex:1, overflowY:'auto', padding:24 }}>
        {isLoading && <Loading />}
        {error && <ErrorBox message={error.message} />}
        {!isLoading && !error && (
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 }}>
            {Object.entries(porGiro).sort().map(([giro, mils])=>(
              <div key={giro} style={{ background:'#fff', border:'1px solid #dee2e6', borderRadius:8, overflow:'hidden' }}>
                <div style={{ background:'#0f2540', padding:'10px 20px', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
                  <span style={{ color:'#fff', fontFamily:"'Syne',sans-serif", fontWeight:700 }}>Giro {giro}</span>
                  <Badge color={COR[giro]||'slate'}>{mils.length} militares</Badge>
                </div>
                {mils.map(m=>(
                  <div key={m.id} style={{ display:'flex', justifyContent:'space-between', padding:'10px 20px', borderBottom:'1px solid #f8f9fa' }}>
                    <span style={{ fontSize:13, color:'#0f2540', fontWeight:500 }}>{m.nome}</span>
                    <span style={{ fontSize:12, color:'#adb5bd', fontFamily:'monospace' }}>{m.posto}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
