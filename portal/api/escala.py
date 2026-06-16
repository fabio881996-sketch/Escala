"""Router de escala."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from services.data_loader_factory import get_data_loader as _get_data_loader
from portal.api.auth import obter_user_atual, obter_admin

router = APIRouter()

_loader: DataLoader | None = None


def get_loader():
    global _loader
    if _loader is None:
        _loader = _get_data_loader()
    return _loader


@router.get("/dia/{data_str}")
async def escala_dia(data_str: str, current_user: dict = Depends(obter_user_atual)):
    """Devolve escala de um dia com nomes formatados."""
    try:
        loader = get_loader()
        # Verificar se o dia está publicado (admins vêem sempre)
        if not current_user.get("is_admin"):
            dias_pub = loader.carregar_dias_publicados()
            if data_str not in dias_pub:
                return {"data": data_str, "entradas": []}
        df = loader.carregar_escala(data_str)
        if df.empty:
            return {"data": data_str, "entradas": []}

        df_util = loader.carregar_usuarios()
        id_nome = {}
        if not df_util.empty:
            for _, r in df_util.iterrows():
                uid = str(r.get("id", "")).strip()
                posto = str(r.get("posto", "")).strip()
                # Abreviar postos GNR
                _postos = {
                    "Guarda Principal": "Grd Pr",
                    "Cabo Chefe": "Cb Ch",
                    "Cabo": "Cb",
                    "Furriel": "Furr",
                    "Segundo Sargento": "2Sarg",
                    "Primeiro Sargento": "1Sarg",
                    "Sargento Ajudante": "Sarg Aj",
                    "Sargento Chefe": "Sarg Ch",
                    "Sargento": "2Sarg",
                    "Guarda": "Grd",
                    "Alferes": "Alf",
                    "Tenente": "Ten",
                    "Capitão": "Cap",
                }
                posto_abrev = posto
                for _nome, _abrev in _postos.items():
                    if posto.lower() == _nome.lower():
                        posto_abrev = _abrev
                        break
                nomes = str(r.get("nome", "")).strip().split()
                apelido = nomes[-1] if nomes else ""
                nome_fmt = f"{uid} {posto_abrev} {apelido}".strip() if posto else f"{uid} {apelido}".strip()
                if uid:
                    id_nome[uid] = nome_fmt

        # Aplicar trocas aprovadas
        df_trocas = loader.carregar_trocas()
        try:
            dt_obj = datetime.strptime(data_str, "%d-%m")
            d_s = dt_obj.strftime(f"%d/%m/{datetime.now().year}")
        except Exception:
            d_s = ""

        if not df_trocas.empty and d_s:
            trocas_dia = df_trocas[
                (df_trocas["data"] == d_s) &
                (df_trocas["status"] == "Aprovada") &
                (~df_trocas["servico_origem"].isin(["MATAR_REMUNERADO","FAZER_REMUNERADO"]))
            ]
            for _, t in trocas_dia.iterrows():
                id_orig = str(t["id_origem"]).strip()
                id_dest = str(t["id_destino"]).strip()
                # Trocar os serviços entre os dois militares no df
                mask_orig = df["id"].astype(str).str.strip() == id_orig
                mask_dest = df["id"].astype(str).str.strip() == id_dest
                if mask_orig.any() and mask_dest.any():
                    idx_orig = df[mask_orig].index[0]
                    idx_dest = df[mask_dest].index[0]
                    # Guardar valores originais
                    cols_trocar = ["serviço", "horário", "viatura", "rádio", "indicativo rádio", "giro", "observações"]
                    for col in cols_trocar:
                        if col in df.columns:
                            val_orig = df.at[idx_orig, col]
                            val_dest = df.at[idx_dest, col]
                            df.at[idx_orig, col] = val_dest
                            df.at[idx_dest, col] = val_orig
                    # Marcar troca_com em ambas as linhas
                    df.at[idx_orig, "__troca_com"] = id_dest
                    df.at[idx_dest, "__troca_com"] = id_orig

        # Aplicar cedência de remunerado (FAZER_REMUNERADO e MATAR_REMUNERADO)
        if not df_trocas.empty and d_s:
            trocas_rem = df_trocas[
                (df_trocas["data"] == d_s) &
                (df_trocas["status"] == "Aprovada") &
                (df_trocas["servico_origem"].isin(["MATAR_REMUNERADO","FAZER_REMUNERADO"]))
            ]
            for _, t in trocas_rem.iterrows():
                is_fazer = str(t["servico_origem"]).strip() == "FAZER_REMUNERADO"
                quem_faz   = str(t["id_origem"]).strip() if is_fazer else str(t["id_destino"]).strip()
                quem_cede  = str(t["id_destino"]).strip() if is_fazer else str(t["id_origem"]).strip()
                # Encontrar linha do remunerado — onde está quem cede
                for idx_r, row_r in df.iterrows():
                    ids_r = [i.strip() for i in str(row_r.get("id","")).split(";")]
                    serv_r = str(row_r.get("serviço","")).lower()
                    if quem_cede in ids_r and ("remun" in serv_r or "gratif" in serv_r):
                        # Substituir quem_cede por quem_faz
                        novos_ids = [quem_faz if i == quem_cede else i for i in ids_r]
                        df.at[idx_r, "id"] = ";".join(novos_ids)
                        break

        entradas = df.fillna("").to_dict(orient="records")
        for e in entradas:
            uid = str(e.get("id", "")).strip()
            e["nome_fmt"] = id_nome.get(uid, uid)
            troca_id = str(e.get("__troca_com", "")).strip()
            e["troca_com"] = id_nome.get(troca_id, "") if troca_id else ""

        return {"data": data_str, "entradas": entradas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_colegas(df_d, servico, horario, u_id, df_trocas, d_s, id_para_nome):
    """Devolve colegas correctos após aplicar trocas."""
    import re as _re
    # Construir mapa id -> (servico, horario) após trocas — expandir IDs múltiplos
    serv_map = {}
    for _, r in df_d.iterrows():
        raw_id = str(r.get("id","")).strip()
        sv = str(r.get("serviço","")).strip()
        hor = str(r.get("horário","")).strip()
        for mid in [i.strip() for i in raw_id.split(";") if i.strip()]:
            serv_map[mid] = (sv, hor)
    # Aplicar trocas aprovadas ao mapa
    if not df_trocas.empty and d_s:
        tr = df_trocas[
            (df_trocas["data"] == d_s) &
            (df_trocas["status"] == "Aprovada") &
            (~df_trocas["servico_origem"].isin(["MATAR_REMUNERADO","FAZER_REMUNERADO"]))
        ]
        for _, t in tr.iterrows():
            id_o = str(t["id_origem"]).strip()
            id_d = str(t["id_destino"]).strip()
            s = str(t["servico_destino"])
            serv_novo_o = s.rsplit("(",1)[0].strip()
            hor_novo_o  = s.rsplit("(",1)[1].rstrip(")") if "(" in s else serv_map.get(id_o,("",""))[1]
            s2 = str(t["servico_origem"])
            serv_novo_d = s2.rsplit("(",1)[0].strip()
            hor_novo_d  = s2.rsplit("(",1)[1].rstrip(")") if "(" in s2 else serv_map.get(id_d,("",""))[1]
            if id_o in serv_map: serv_map[id_o] = (serv_novo_o, hor_novo_o)
            if id_d in serv_map: serv_map[id_d] = (serv_novo_d, hor_novo_d)
    # Encontrar quem tem o mesmo serviço/horário
    colegas = []
    serv_lower = servico.strip().lower()
    for mid, (sv, hor) in serv_map.items():
        if mid == str(u_id).strip(): continue
        if sv.strip().lower() == serv_lower and hor.strip() == horario.strip():
            colegas.append(id_para_nome.get(mid, mid))
    return colegas


@router.get("/minha")
async def minha_escala(current_user: dict = Depends(obter_user_atual)):
    """Batch optimizado — uma chamada HTTP para todos os dias."""
    u_id = current_user.get("sub")
    try:
        loader = get_loader()
        hj = datetime.now()

        dias_pub = loader.carregar_dias_publicados()
        df_trocas = loader.carregar_trocas()
        df_util = loader.carregar_usuarios()

        # Mapa id -> formato "ID Posto PrimeiroNome Apelido"
        id_para_nome = {}
        if not df_util.empty:
            for _, r in df_util.iterrows():
                uid = str(r.get("id", "")).strip()
                posto = str(r.get("posto", "")).strip()
                nomes = str(r.get("nome", "")).strip().split()
                nome_curto = f"{nomes[0]} {nomes[-1]}" if len(nomes) > 1 else " ".join(nomes)
                if uid:
                    id_para_nome[uid] = f"{uid} {posto} {nome_curto}".strip()

        dias_a_mostrar: list[date] = []
        for delta in range(90):
            dt = hj.date() + timedelta(days=delta)
            if dt.strftime("%d-%m") in dias_pub:
                dias_a_mostrar.append(dt)
            if len(dias_a_mostrar) >= 20:
                break

        if not dias_a_mostrar:
            return {"servicos": []}

        # BATCH — todas as escalas numa única chamada ao Sheets
        escalas = loader.carregar_escalas_batch(dias_a_mostrar)

        servicos = []
        dias_sem = 0

        for dt in dias_a_mostrar:
            if dias_sem >= 5:
                break

            aba = dt.strftime("%d-%m")
            df_d = escalas.get(aba)

            if df_d is None or df_d.empty:
                dias_sem += 1
                continue

            _uid_str = str(u_id).strip()
            meu = df_d[df_d["id"].astype(str).str.strip().apply(
                lambda x: _uid_str == x or _uid_str in [i.strip() for i in x.split(";")]
            )]

            # Remover linhas de remunerado que foram cedidas via MATAR_REMUNERADO
            if not df_trocas.empty and not meu.empty:
                d_s_check = dt.strftime("%d/%m/%Y")
                cedeu_rem = df_trocas[
                    (df_trocas["data"] == d_s_check) &
                    (df_trocas["status"] == "Aprovada") &
                    (df_trocas["servico_origem"] == "MATAR_REMUNERADO") &
                    (df_trocas["id_origem"].astype(str).str.strip() == _uid_str)
                ]
                if not cedeu_rem.empty:
                    meu = meu[~meu["serviço"].astype(str).str.lower().str.contains("remun|gratif")]
            if meu.empty:
                dias_sem += 1
                continue

            dias_sem = 0
            d_s = dt.strftime("%d/%m/%Y")

            # Iterar todas as linhas do militar — pode ter serviço normal + remunerado nomeado
            import re as _re
            linhas_normais = meu[~meu["serviço"].astype(str).str.lower().str.contains("remun|gratif", na=False)]
            linhas_remun   = meu[meu["serviço"].astype(str).str.lower().str.contains("remun|gratif", na=False)]

            # Processar serviços normais
            for _, row in (linhas_normais if not linhas_normais.empty else meu.head(1)).iterrows():
                servico = str(row.get("serviço", ""))
                horario = str(row.get("horário", ""))
                if _re.search(r"remun|gratif", servico.lower()):
                    continue

                troca_aplicada = False
                troca_com_id = ""
                row_ref = row

                if not df_trocas.empty:
                    tr = df_trocas[
                        (df_trocas["data"] == d_s) &
                        (df_trocas["status"] == "Aprovada") &
                        (~df_trocas["servico_origem"].isin(["MATAR_REMUNERADO","FAZER_REMUNERADO"]))
                    ]
                    for _, t in tr.iterrows():
                        if str(t["id_origem"]).strip() == str(u_id).strip():
                            s = str(t["servico_destino"])
                        elif str(t["id_destino"]).strip() == str(u_id).strip():
                            s = str(t["servico_origem"])
                        else:
                            continue
                        serv_novo = s.rsplit("(", 1)[0].strip()
                        hor_novo  = s.rsplit("(", 1)[1].rstrip(")") if "(" in s else horario
                        mask_novo = (
                            (df_d["serviço"].astype(str).str.strip().str.lower() == serv_novo.lower()) &
                            (df_d["horário"].astype(str).str.strip() == hor_novo.strip())
                        )
                        if mask_novo.any():
                            row_ref = df_d[mask_novo].iloc[0]
                        servico = serv_novo
                        horario = hor_novo
                        troca_aplicada = True
                        troca_com_id = str(t["id_destino"]).strip() if str(t["id_origem"]).strip() == str(u_id).strip() else str(t["id_origem"]).strip()
                        break

                servicos.append({
                    "data": d_s, "aba": aba, "servico": servico, "horario": horario,
                    "troca_aprovada": troca_aplicada,
                    "troca_com": id_para_nome.get(troca_com_id, troca_com_id) if troca_com_id else "",
                    "troca_com_label": "Cedido por",
                    "viatura": str(row_ref.get("viatura", "") or "").replace("nan", ""),
                    "radio": str(row_ref.get("rádio", "") or "").replace("nan", ""),
                    "indicativo": str(row_ref.get("indicativo rádio", "") or "").replace("nan", ""),
                    "giro": str(row_ref.get("giro", "") or "").replace("nan", ""),
                    "observacoes": str(row_ref.get("observações", "") or "").replace("nan", ""),
                    "is_hoje": dt == hj.date(),
                    "is_amanha": dt == (hj.date() + timedelta(days=1)),
                    "colegas": _get_colegas(df_d, servico, horario, u_id, df_trocas, d_s, id_para_nome),
                })

            # Processar remunerados nomeados directamente (linha multi-ID no Sheets)
            for _, row_rem in linhas_remun.iterrows():
                serv_rem = str(row_rem.get("serviço","")).strip()
                hor_rem  = str(row_rem.get("horário","")).strip()
                ids_linha = [i.strip() for i in str(row_rem.get("id","")).split(";") if i.strip()]
                colegas_rem = [id_para_nome.get(i, i) for i in ids_linha if i != str(u_id).strip()]
                servicos.append({
                    "data": d_s, "aba": aba, "servico": serv_rem, "horario": hor_rem,
                    "troca_aprovada": False, "troca_com": "", "troca_com_label": "",
                    "viatura": str(row_rem.get("viatura","") or "").replace("nan",""),
                    "radio": str(row_rem.get("rádio","") or "").replace("nan",""),
                    "indicativo": str(row_rem.get("indicativo rádio","") or "").replace("nan",""),
                    "giro": "", "observacoes": str(row_rem.get("observações","") or "").replace("nan",""),
                    "is_hoje": dt == hj.date(), "is_amanha": dt == (hj.date() + timedelta(days=1)),
                    "colegas": colegas_rem, "is_remunerado": True,
                })
            # Verificar se há FAZER_REMUNERADO ou MATAR_REMUNERADO aprovado — adicionar remunerado cedido
            if not df_trocas.empty:
                tr_rem = df_trocas[
                    (df_trocas["data"] == d_s) &
                    (df_trocas["status"] == "Aprovada") &
                    (df_trocas["servico_origem"].isin(["MATAR_REMUNERADO","FAZER_REMUNERADO"]))
                ]
                for _, t_rem in tr_rem.iterrows():
                    # FAZER_REMUNERADO: id_origem é quem faz, id_destino é quem cede
                    # MATAR_REMUNERADO: id_destino é quem faz, id_origem é quem cede
                    is_fazer = str(t_rem["servico_origem"]).strip() == "FAZER_REMUNERADO"
                    quem_faz = str(t_rem["id_origem"]).strip() if is_fazer else str(t_rem["id_destino"]).strip()
                    quem_cede = str(t_rem["id_destino"]).strip() if is_fazer else str(t_rem["id_origem"]).strip()
                    if quem_faz != str(u_id).strip():
                        continue
                    # Encontrar linha do remunerado na escala do dia
                    serv_rem = str(t_rem.get("servico_destino","")).strip()
                    hor_rem = ""
                    vtr_rem = ""
                    rad_rem = ""
                    ind_rem = ""
                    obs_rem = ""
                    if "(" in serv_rem:
                        hor_rem = serv_rem.rsplit("(",1)[1].rstrip(")")
                        serv_rem = serv_rem.rsplit("(",1)[0].strip()
                    # Procurar linha do remunerado no df_d pelo id de quem cede
                    mask_rem = df_d["id"].astype(str).str.strip().apply(
                        lambda x: quem_cede == x or quem_cede in [i.strip() for i in x.split(";")]
                    )
                    rem_rows = df_d[mask_rem & df_d["serviço"].astype(str).str.lower().str.contains("remun|gratif")]
                    if not rem_rows.empty:
                        r_rem = rem_rows.iloc[0]
                        serv_rem = str(r_rem.get("serviço","")).strip()
                        hor_rem  = str(r_rem.get("horário","")).strip()
                        vtr_rem  = str(r_rem.get("viatura","") or "").replace("nan","")
                        rad_rem  = str(r_rem.get("rádio","") or "").replace("nan","")
                        ind_rem  = str(r_rem.get("indicativo rádio","") or "").replace("nan","")
                        obs_rem  = str(r_rem.get("observações","") or "").replace("nan","")
                    # Colegas do remunerado — outros militares na mesma linha
                    colegas_rem = []
                    if not rem_rows.empty:
                        ids_rem = [i.strip() for i in str(rem_rows.iloc[0].get("id","")).split(";")]
                        colegas_rem = [id_para_nome.get(i, i) for i in ids_rem if i and i != str(u_id).strip() and i != quem_cede]
                    # Também incluir outros com FAZER_REMUNERADO aprovado no mesmo slot
                    outros_fazer = df_trocas[
                        (df_trocas["data"] == d_s) &
                        (df_trocas["status"] == "Aprovada") &
                        (df_trocas["servico_origem"].isin(["MATAR_REMUNERADO","FAZER_REMUNERADO"])) &
                        (df_trocas["id_origem" if is_fazer else "id_destino"].astype(str).str.strip() != str(u_id).strip())
                    ]
                    for _, o in outros_fazer.iterrows():
                        outro_id = str(o["id_origem"]).strip() if is_fazer else str(o["id_destino"]).strip()
                        nome_outro = id_para_nome.get(outro_id, outro_id)
                        if nome_outro not in colegas_rem:
                            colegas_rem.append(nome_outro)

                    servicos.append({
                        "data": d_s,
                        "aba": aba,
                        "servico": serv_rem or "Svç Remunerado",
                        "horario": hor_rem,
                        "troca_aprovada": False,
                        "troca_com": id_para_nome.get(quem_cede, quem_cede),
                        "troca_com_label": "Cedido por",
                        "viatura": vtr_rem,
                        "radio": rad_rem,
                        "indicativo": ind_rem,
                        "giro": "",
                        "observacoes": obs_rem,
                        "is_hoje": dt == hj.date(),
                        "is_amanha": dt == (hj.date() + timedelta(days=1)),
                        "colegas": colegas_rem,
                        "is_remunerado": True,
                    })

        return {"servicos": servicos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/aniversarios")
async def aniversarios(current_user: dict = Depends(obter_user_atual)):
    """Devolve aniversariantes de hoje."""
    try:
        from datetime import datetime as _dt
        loader = get_loader()
        df_util = loader.carregar_usuarios()
        hoje = _dt.now()
        aniversariantes = []
        if 'nascimento' in df_util.columns:
            for _, row in df_util.iterrows():
                nasc = str(row.get('nascimento', '')).strip()
                if not nasc or nasc == 'nan':
                    continue
                try:
                    dt_nasc = _dt.strptime(nasc.replace('/', '-'), '%d-%m-%Y')
                    if dt_nasc.day == hoje.day and dt_nasc.month == hoje.month:
                        idade = hoje.year - dt_nasc.year
                        nome = f"{row.get('posto','')} {row.get('nome','')}".strip()
                        aniversariantes.append({"nome": nome, "idade": idade})
                except Exception:
                    continue
        return {"aniversariantes": aniversariantes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/publicados")
async def dias_publicados(current_user: dict = Depends(obter_user_atual)):
    try:
        loader = get_loader()
        dias = sorted(loader.carregar_dias_publicados())
        return {"dias": dias}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/publicar/{aba}")
async def publicar_dia(aba: str, current_user: dict = Depends(obter_admin)):
    try:
        loader = get_loader()
        loader.publicar_dia(aba)
        loader.limpar_cache()
        try:
            from portal.api.notificacoes import enviar_push
            df_util = loader.carregar_usuarios()
            todos_ids = df_util["id"].astype(str).str.strip().tolist()
            data_fmt = aba.replace("-", "/")
            enviar_push(
                u_ids=todos_ids,
                titulo="📅 Nova escala publicada",
                corpo=f"A escala de {data_fmt} foi publicada.",
                url="/escala-geral",
                tag="escala-publicada",
            )
        except Exception:
            pass
        return {"ok": True, "aba": aba}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/publicar/{aba}")
async def despublicar_dia(aba: str, current_user: dict = Depends(obter_admin)):
    try:
        loader = get_loader()
        loader.despublicar_dia(aba)
        loader.limpar_cache()
        return {"ok": True, "aba": aba}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
