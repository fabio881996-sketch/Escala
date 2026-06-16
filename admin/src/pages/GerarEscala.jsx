import { PageHeader } from '../components/ui'

export default function GerarEscala() {
  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'#f8f9fa' }}>
      <PageHeader icon="⚙️" title="Gerar Escala" subtitle="Geração automática" />
      <div style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:16, opacity:.5 }}>
        <span style={{ fontSize:56 }}>⚙️</span>
        <p style={{ fontFamily:"'Syne',sans-serif", fontWeight:600, color:'#495057', fontSize:16, margin:0 }}>Em desenvolvimento</p>
        <p style={{ fontSize:13, color:'#6c757d', margin:0 }}>Usa o Streamlit para gerar escalas por agora</p>
      </div>
    </div>
  )
}
