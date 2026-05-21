"""Router de escala."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.database import GoogleSheetsClient
from services.data_loader import DataLoader
from portal.api.auth import obter_user_atual, obter_admin

router = APIRouter()


def get_loader() -> DataLoader:
    return DataLoader(sheets_client=GoogleSheetsClient())


@router.get("/dia/{data_str}")
async def escala_dia(data_str: str, current_user: dict = Depends(obter_user_atual)):
    """Devolve escala de um dia no formato DD-MM."""
    try:
        loader = get_loader()
        df = loader.carregar_escala(data_str)
        if df.empty:
            return {"data": data_str, "entradas": []}
        return {"data": data_str, "entradas": df.fillna("").to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/minha")
async def minha_escala(current_user: dict = Depends(obter_user_atual)):
    """Devolve os próximos serviços do utilizador autenticado."""
    u_id = current_user.get("sub")
    try:
        loader = get_loader()
        dias_pub = loader.carregar_dias_publicados()
        ano = datetime.now().year
        feriados = loader.carregar_feriados(ano)
        df_trocas = loader.carregar_trocas()

        servicos = []
        hj = datetime.now()

        dias_a_mostrar = []
        for delta in range(90):
            dt = hj.date() + __import__("datetime").timedelta(days=delta)
            aba = dt.strftime("%d-%m")
            if aba in dias_pub:
                dias_a_mostrar.append(dt)
            if len(dias_a_mostrar) >= 20:
                break

        dias_sem = 0
        for dt in dias_a_mostrar:
            if dias_sem >= 5:
                break
            df_d = loader.carregar_escala(dt.strftime("%d-%m"))
            if df_d.empty:
                dias_sem += 1
                continue

            meu = df_d[df_d["id"].astype(str) == str(u_id)]
            if meu.empty:
                dias_sem += 1
                continue

            dias_sem = 0
            row = meu.iloc[0]
            servicos.append({
                "data": dt.strftime("%d/%m/%Y"),
                "aba": dt.strftime("%d-%m"),
                "servico": str(row.get("serviço", "")),
                "horario": str(row.get("horário", "")),
                "viatura": str(row.get("viatura", "")),
                "radio": str(row.get("rádio", "")),
                "indicativo": str(row.get("indicativo rádio", "")),
                "giro": str(row.get("giro", "")),
                "observacoes": str(row.get("observações", "")),
                "is_hoje": dt == hj.date(),
                "is_amanha": dt == (hj.date() + __import__("datetime").timedelta(days=1)),
            })

        return {"servicos": servicos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/publicados")
async def dias_publicados(current_user: dict = Depends(obter_user_atual)):
    """Devolve lista de dias publicados."""
    try:
        loader = get_loader()
        dias = sorted(loader.carregar_dias_publicados())
        return {"dias": dias}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/publicar/{aba}")
async def publicar_dia(aba: str, current_user: dict = Depends(obter_admin)):
    """Publica um dia de escala."""
    try:
        from core.database import GoogleSheetsClient, get_sheet
        sh = get_sheet()
        try:
            ws = sh.worksheet("escala_publicada")
        except Exception:
            ws = sh.add_worksheet(title="escala_publicada", rows=100, cols=1)
            ws.update("A1", [["data"]])
        ws.append_row([aba])
        _cached_load_dias_publicados.clear()
        return {"ok": True, "aba": aba}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/publicar/{aba}")
async def despublicar_dia(aba: str, current_user: dict = Depends(obter_admin)):
    """Despublica um dia de escala."""
    try:
        from core.database import get_sheet
        sh = get_sheet()
        ws = sh.worksheet("escala_publicada")
        vals = ws.get_all_values()
        for i, row in enumerate(vals[1:], start=2):
            if str(row[0]).strip() == aba:
                ws.delete_rows(i)
                break
        return {"ok": True, "aba": aba}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
