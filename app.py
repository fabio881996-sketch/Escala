import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E ESTILO VISUAL (CORES CORRIGIDAS) ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    /* Fundo Geral da App */
    .stApp { background-color: #F8F9FA !important; }
    
    /* Barra Lateral */
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    
    /* Títulos da App (Azul Escuro GNR) */
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { 
        color: #2C3E50 !important; 
        font-weight: 700 !important; 
    }
    
    /* Texto dos Expanders (Categorias da Escala Geral) */
    .streamlit-expanderHeader { 
        background-color: #FFFFFF !important; 
        color: #2C3E50 !important; 
        font-weight: bold !important;
        border: 1px solid #DDE1E6 !important;
        border-radius: 8px !important;
    }

    /* Exceção: Título dentro do Login (Fundo Escuro) */
    div[data-testid="stForm"] h1, div[data-testid="stForm"] h2 { 
        color: white !important; 
    }

    /* Estilo dos Blocos (Cards) */
    .card-servico { 
        background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; 
        border-left: 6px solid #455A64; margin-bottom: 10px; color: #333;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .card-meu { border-left-color: #1E88E5 !important; background-color: #F0F7FF !important; }
    .card-troca { border-left-color: #FFD54F !important; background-color: #FFFDE7 !important; }
    .troca-tag { background-color: #FFD54F; color: black; padding: 2px 10px; border-radius: 20px; font-weight: bold; font-size: 0.7rem; float: right; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNÇÕES DE DADOS ---
def get_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

def load_data(aba_nome):
    try:
        base_url = st.secrets["gsheet_url"].split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url, dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]
        return df.fillna("")
    except
