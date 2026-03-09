def load_sheet(aba_nome):
    try:
        # Tenta ler via CSV (Método rápido)
        url = st.secrets["gsheet_url"].split('/edit')[0]
        csv_url = f"{url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url, dtype=str)
        
        if df.empty:
            st.error(f"A aba '{aba_nome}' parece estar vazia.")
            return None
            
        df.columns = [c.strip().lower() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        return df.replace("nan", "")
    except Exception as e:
        # Se falhar o CSV, tentamos via API (Método seguro)
        try:
            client = get_gspread_client()
            sh = client.open_by_url(st.secrets["gsheet_url"])
            worksheet = sh.worksheet(aba_nome)
            data = worksheet.get_all_records()
            df = pd.DataFrame(data).astype(str)
            df.columns = [c.strip().lower() for c in df.columns]
            return df
        except Exception as e_api:
            st.error(f"Erro Crítico ao ler '{aba_nome}': {e_api}")
            return None
            
    
