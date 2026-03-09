st.markdown("""
    <style>
    /* Fundo Geral */
    .stApp { background-color: #F8F9FA !important; }
    
    /* Barra Lateral */
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    
    /* Títulos Principais - Cor azul escura GNR */
    h1, h2, h3 { color: #455A64 !important; font-weight: 700 !important; }
    
    /* Estilo dos Expanders na Escala Geral */
    .streamlit-expanderHeader { 
        background-color: #FFFFFF !important; 
        color: #455A64 !important; 
        font-weight: bold !important;
        border-radius: 5px;
    }
    
    /* Login Form (Mantém branco lá dentro porque o fundo é escuro) */
    div[data-testid="stForm"] h1, div[data-testid="stForm"] h2 { 
        color: white !important; 
    }
    
    /* Cards Visuais */
    .card-servico { 
        background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; 
        border-left: 6px solid #455A64; margin-bottom: 10px; color: #333;
    }
    .card-meu { border-left-color: #1E88E5 !important; background-color: #F0F7FF !important; }
    .card-troca { border-left-color: #FFD54F !important; background-color: #FFFDE7 !important; }
    .troca-tag { background-color: #FFD54F; color: black; padding: 2px 10px; border-radius: 20px; font-weight: bold; font-size: 0.7rem; float: right; }
    </style>
    """, unsafe_allow_html=True)
