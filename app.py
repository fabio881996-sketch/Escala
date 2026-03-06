# --- 📅 ESCALA DIÁRIA ---
    if menu == "📅 Escala Diária":
        st.title("📅 Escala de Serviço Diária")
        data_sel = st.date_input("Consultar dia:", format="DD/MM/YYYY")
        
        # Tenta vários formatos de nome de aba para garantir
        nome_aba = data_sel.strftime("%d-%m") # Ex: 06-03
        nome_aba_curto = data_sel.strftime("%-d-%-m") # Ex: 6-3 (para sistemas que tiram o zero)

        # Tenta carregar a aba
        df_dia = load_data(nome_aba)
        if df_dia is None:
            df_dia = load_data(nome_aba_curto)

        if df_dia is not None:
            # Limpeza imediata para evitar erros de leitura
            df_dia.columns = [str(c).strip().lower() for c in df_dia.columns]
            
            # Garante que as colunas necessárias existem
            if 'id' in df_dia.columns and 'serviço' in df_dia.columns:
                df_dia['id'] = df_dia['id'].astype(str).str.strip()
                df_dia['serviço'] = df_dia['serviço'].fillna("---").astype(str).str.strip()
                df_dia['horário'] = df_dia['horário'].fillna("---").astype(str).str.strip()

                # --- AQUI CONTINUAM OS TEUS BLOCOS (Atendimento, Patrulhas, etc) ---
                st.success(f"✅ Escala de {nome_aba} carregada com sucesso.")
                
                # Exemplo de um bloco:
                temp_atend = df_dia[df_dia['serviço'].str.lower() == "atendimento"]
                if not temp_atend.empty:
                    st.subheader("🔹 Atendimento")
                    st.table(temp_atend[['id', 'horário']])
                else:
                    st.write("Sem pessoal no Atendimento registado.")
            else:
                st.error("A folha existe, mas as colunas 'id' ou 'serviço' não foram encontradas.")
        else:
            st.warning(f"⚠️ A aba '{nome_aba}' não foi encontrada na Google Sheet.")
            st.info("Verifica se o nome da aba na Excel é exatamente '06-03'.")
            
