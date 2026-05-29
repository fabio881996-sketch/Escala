"""Router de escala."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from core.database import GoogleSheetsClient
from services.data_loader import DataLoader
from portal.api.auth import obter_user_atual, obter_admin

router = APIRouter()

_loader: DataLoader | None = None


def get_loader() -> DataLoader:
    global _loader
    if _loader is None:
        _loader = DataLoader(sheets_client=GoogleSheetsClient())
    return _loader


@router.get("/dia/{data_str}")
async def escala_dia(data_str: str, current_user: dict = Depends(obter_user_atual)):
    """Devolve escala de um dia com nomes formatados."""
    try:
        loader = get_loader()
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
                (df_trocas["servico_origem"] != "MATAR_REMUNERADO")
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

        entradas = df.fillna("").to_dict(orient="records")
        for e in entradas:
            uid = str(e.get("id", "")).strip()
            e["nome_fmt"] = id_nome.get(uid, uid)
            troca_id = str(e.get("__troca_com", "")).strip()
            e["troca_com"] = id_nome.get(troca_id, "") if troca_id else ""

        return {"data": data_str, "entradas": entradas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

            meu = df_d[df_d["id"].astype(str).str.strip() == str(u_id).strip()]
            if meu.empty:
                dias_sem += 1
                continue

            dias_sem = 0
            row = meu.iloc[0]
            d_s = dt.strftime("%d/%m/%Y")
            servico = str(row.get("serviço", ""))
            horario = str(row.get("horário", ""))

            troca_aplicada = False
            id_excluir = ""
            # row_ref aponta para a linha cujos dados (viatura, radio, colegas) devem ser usados
            row_ref = row

            if not df_trocas.empty:
                tr = df_trocas[
                    (df_trocas["data"] == d_s) &
                    (df_trocas["status"] == "Aprovada") &
                    (df_trocas["servico_origem"] != "MATAR_REMUNERADO")
                ]
                for _, t in tr.iterrows():
                    if str(t["id_origem"]).strip() == str(u_id).strip():
                        id_outro = str(t["id_destino"]).strip()
                    elif str(t["id_destino"]).strip() == str(u_id).strip():
                        id_outro = str(t["id_origem"]).strip()
                    else:
                        continue

                    # Buscar o serviço do outro militar directamente na escala
                    linha_outro = df_d[df_d["id"].astype(str).str.strip() == id_outro]
                    if linha_outro.empty:
                        continue

                    row_ref = linha_outro.iloc[0]
                    servico = str(row_ref.get("serviço", "")).strip()
                    horario = str(row_ref.get("horário", "")).strip()
                    id_excluir = id_outro
                    troca_aplicada = True
                    break

            servicos.append({
                "data": d_s,
                "aba": aba,
                "servico": servico,
                "horario": horario,
                "troca_aprovada": troca_aplicada,
                "viatura": str(row_ref.get("viatura", "") or "").replace("nan", ""),
                "radio": str(row_ref.get("rádio", "") or "").replace("nan", ""),
                "indicativo": str(row_ref.get("indicativo rádio", "") or "").replace("nan", ""),
                "giro": str(row_ref.get("giro", "") or "").replace("nan", ""),
                "observacoes": str(row_ref.get("observações", "") or "").replace("nan", ""),
                "is_hoje": dt == hj.date(),
                "is_amanha": dt == (hj.date() + timedelta(days=1)),
                "colegas": [
                    id_para_nome.get(str(r["id"]).strip(), str(r["id"]).strip())
                    for _, r in df_d[
                        (df_d["serviço"].astype(str).str.strip().str.lower() == servico.strip().lower()) &
                        (df_d["horário"].astype(str).str.strip() == horario.strip()) &
                        (df_d["id"].astype(str).str.strip() != str(u_id).strip()) &
                        (df_d["id"].astype(str).str.strip() != str(id_excluir).strip())
                    ].iterrows()
                    if str(r["id"]).strip()
                ],
            })

        return {"servicos": servicos}
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
        from core.database import get_sheet
        sh = get_sheet()
        try:
            ws = sh.worksheet("escala_publicada")
        except Exception:
            ws = sh.add_worksheet(title="escala_publicada", rows=100, cols=1)
            ws.update("A1", [["data"]])
        ws.append_row([aba])
        get_loader().limpar_cache()
        # Notificar todos os utilizadores
        try:
            from portal.api.notificacoes import enviar_push
            df_util = get_loader().carregar_usuarios()
            todos_ids = df_util["id"].astype(str).str.strip().tolist()
            # Formatar data para exibição (DD-MM → DD/MM)
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
        from core.database import get_sheet
        sh = get_sheet()
        ws = sh.worksheet("escala_publicada")
        vals = ws.get_all_values()
        for i, row in enumerate(vals[1:], start=2):
            if str(row[0]).strip() == aba:
                ws.delete_rows(i)
                break
        get_loader().limpar_cache()
        return {"ok": True, "aba": aba}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
