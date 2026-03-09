elif menu == "🔍 Escala Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY", key="geral")
        d_str_sel = data_sel.strftime('%d/%m/%Y')
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_data(nome_aba)
        
        if not df_dia.empty:
            df_atual = df_dia.copy()

            # --- APLICAR TROCAS NA LISTA GERAL ---
            if not df_trocas.empty and 'data' in df_trocas.columns:
                # Filtra trocas apenas para o dia selecionado
                trocas_do_dia = df_trocas[df_trocas['data'] == d_str_sel]
                
                for _, t in trocas_do_dia.iterrows():
                    # Quem deu o serviço (Origem)
                    idx_origem = df_atual.index[df_atual['id'].astype(str) == str(t['id_origem'])].tolist()
                    if idx_origem:
                        df_atual.at[idx_origem[0], 'serviço'] = f"{t['servico_destino']} (🔄 Troca)"
                    
                    # Se o destino (quem recebeu) também estiver na escala, atualizamos o dele
                    idx_destino = df_atual.index[df_atual['id'].astype(str) == str(t['id_destino'])].tolist()
                    if idx_destino:
                        df_atual.at[idx_destino[0], 'serviço'] = f"{t['servico_origem']} (🔄 Troca)"

            def mostrar_grupo(titulo, keywords, df_base, excluir=True):
                padrao = '|'.join(keywords).lower()
                temp_df = df_base[df_base['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
                    
                    if excluir:
                        return df_base[~df_base['id'].isin(temp_df['id'])]
                return df_base

            # --- EXIBIÇÃO POR CATEGORIAS ---
            df_atual = mostrar_grupo("Atendimento", ["atendimento"], df_atual)
            df_atual = mostrar_grupo("Apoio ao Atendimento", ["apoio"], df_atual)
            df_atual = mostrar_grupo("Patrulhas", ["po", "patrulha", "ronda", "vtr"], df_atual)
            _ = mostrar_grupo("Remunerados", ["remu", "renu", "grat", "extra"], df_atual, excluir=False)
            df_atual = mostrar_grupo("Folga", ["folga"], df_atual)
            df_atual = mostrar_grupo("Ausentes", ["férias", "licença", "doente", "diligência", "falta"], df_atual)
            df_atual = mostrar_grupo("Administrativo e Outros", ["secretaria", "tribunal", "inquérito", "pronto", "oficina", "comando", "permanência"], df_atual)
        else:
            st.warning("Nenhum dado encontrado para este dia.")
            
