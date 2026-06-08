"""Portal de Escalas GNR — Admin API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from portal.api.auth import obter_admin
from core.database import GoogleSheetsClient
from services.data_loader import DataLoader


def get_loader() -> DataLoader:
    return DataLoader(sheets_client=GoogleSheetsClient())

router = APIRouter()


# ── Efetivo ──────────────────────────────────────────────────
@router.get("/efetivo")
async def efetivo(current_user: dict = Depends(obter_admin)):
    try:
        loader = get_loader()
        df = loader.carregar_usuarios()
        militares = []
        for _, r in df.iterrows():
            militares.append({
                "id":         str(r.get("id", "")).strip(),
                "nome":       str(r.get("nome", "")).strip(),
                "posto":      str(r.get("posto", "")).strip(),
                "disponivel": str(r.get("disponivel", "")).strip().lower() in ("true", "1", "sim"),
            })
        return {"militares": militares}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Utilizadores ─────────────────────────────────────────────
@router.get("/utilizadores")
async def utilizadores(current_user: dict = Depends(obter_admin)):
    try:
        loader = get_loader()
        df = loader.carregar_usuarios()
        result = []
        for _, r in df.iterrows():
            pin_val = str(r.get("pin", "")).strip()
            result.append({
                "id":       str(r.get("id", "")).strip(),
                "nome":     str(r.get("nome", "")).strip(),
                "posto":    str(r.get("posto", "")).strip(),
                "email":    str(r.get("email", "")).strip(),
                "is_admin": str(r.get("is_admin", "")).strip().lower() in ("true", "1", "sim"),
                "tem_pin":  bool(pin_val and len(pin_val) > 4),
            })
        return {"utilizadores": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UpdateUtilizador(BaseModel):
    pin: Optional[str] = None
    is_admin: Optional[bool] = None


@router.put("/utilizadores/{uid}")
async def update_utilizador(uid: str, body: UpdateUtilizador, current_user: dict = Depends(obter_admin)):
    try:
        import os, json
        from core.database import GoogleSheetsClient
        from passlib.hash import bcrypt

        sh = GoogleSheetsClient().get_spreadsheet()
        ws = sh.worksheet("utilizadores")
        vals = ws.get_all_values()
        hdrs = [h.strip().lower() for h in vals[0]]
        col_id  = hdrs.index("id")  if "id"  in hdrs else 0
        col_pin = hdrs.index("pin") if "pin" in hdrs else None

        for i, row in enumerate(vals[1:], start=2):
            if str(row[col_id]).strip() == uid.strip():
                if body.pin is not None and col_pin is not None:
                    salt = bcrypt.gen_salt()
                    hashed = bcrypt.using(rounds=12).hash(body.pin)
                    cl = chr(ord('A') + col_pin)
                    ws.update_cell(i, col_pin + 1, f"{salt}:{hashed}")
                get_loader().limpar_cache()
                return {"ok": True}
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Giros ─────────────────────────────────────────────────────
@router.get("/giros")
async def giros(current_user: dict = Depends(obter_admin)):
    try:
        loader = get_loader()
        df = loader.carregar_usuarios()
        result = []
        for _, r in df.iterrows():
            giro = str(r.get("giro", "")).strip()
            if giro:
                result.append({
                    "id":    str(r.get("id", "")).strip(),
                    "nome":  str(r.get("nome", "")).strip(),
                    "posto": str(r.get("posto", "")).strip(),
                    "giro":  giro,
                })
        return {"giros": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Alertas ───────────────────────────────────────────────────
@router.get("/alertas")
async def alertas(aba: str, current_user: dict = Depends(obter_admin)):
    try:
        from datetime import datetime
        loader = get_loader()
        df_dia = loader.carregar_escala(aba)
        df_util = loader.carregar_usuarios()
        df_trocas = loader.carregar_trocas()
        df_licencas = loader.carregar_licencas()
        df_ferias = loader.carregar_ferias()
        feriados = loader.carregar_feriados()

        id_nome = {
            str(r["id"]).strip(): f"{r.get('posto','')} {r.get('nome','')}".strip()
            for _, r in df_util.iterrows()
        }

        alertas_list = []

        if not df_dia.empty:
            # Verificar duplicados
            from collections import Counter
            ids = [str(r["id"]).strip() for _, r in df_dia.iterrows() if str(r.get("id","")).strip()]
            dups = [i for i, c in Counter(ids).items() if c > 1]
            for d in dups:
                alertas_list.append({
                    "tipo": "duplicado",
                    "militar": id_nome.get(d, d),
                    "mensagem": f"Escalado mais de uma vez"
                })

        return {"alertas": alertas_list, "total": len(alertas_list)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Estatísticas ──────────────────────────────────────────────
@router.get("/estatisticas")
async def estatisticas(id: str, ano: int, current_user: dict = Depends(obter_admin)):
    try:
        loader = get_loader()
        df_util = loader.carregar_usuarios()
        nome = id
        for _, r in df_util.iterrows():
            if str(r.get("id","")).strip() == id:
                nome = f"{r.get('posto','')} {r.get('nome','')}".strip()
                break

        # Contar serviços do ano (percorrer abas publicadas)
        dias_publicados = loader.carregar_dias_publicados()
        contagem = {}
        for aba in dias_publicados:
            try:
                df_d = loader.carregar_escala(aba)
                if df_d.empty: continue
                for _, r in df_d[df_d["id"].astype(str).str.strip() == id].iterrows():
                    serv = str(r.get("serviço","")).strip()
                    if serv:
                        contagem[serv] = contagem.get(serv, 0) + 1
            except Exception:
                continue

        total = sum(contagem.values())
        servicos = [{"servico": k, "total": v} for k, v in sorted(contagem.items(), key=lambda x: -x[1])]
        return {"nome": nome, "total": total, "servicos": servicos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Férias ────────────────────────────────────────────────────
@router.get("/ferias")
async def ferias_admin(ano: int, current_user: dict = Depends(obter_admin)):
    try:
        loader = get_loader()
        df = loader.carregar_ferias(ano)
        df_util = loader.carregar_usuarios()
        id_nome = {
            str(r["id"]).strip(): f"{r.get('posto','')} {r.get('nome','')}".strip()
            for _, r in df_util.iterrows()
        }
        ferias = []
        if not df.empty:
            for _, r in df.iterrows():
                ferias.append({
                    "id":     str(r.get("id","")).strip(),
                    "nome":   id_nome.get(str(r.get("id","")).strip(), str(r.get("id","")).strip()),
                    "inicio": str(r.get("inicio","")).strip(),
                    "fim":    str(r.get("fim","")).strip(),
                    "dias":   str(r.get("dias","")).strip(),
                })
        return {"ferias": ferias}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Dispensas ─────────────────────────────────────────────────
@router.get("/dispensas")
async def dispensas(current_user: dict = Depends(obter_admin)):
    try:
        loader = get_loader()
        df = loader.carregar_licencas()
        df_util = loader.carregar_usuarios()
        id_nome = {
            str(r["id"]).strip(): f"{r.get('posto','')} {r.get('nome','')}".strip()
            for _, r in df_util.iterrows()
        }
        result = []
        if not df.empty:
            for idx, r in df.iterrows():
                result.append({
                    "__row": idx + 2,
                    "id":       str(r.get("id","")).strip(),
                    "nome":     id_nome.get(str(r.get("id","")).strip(), str(r.get("id","")).strip()),
                    "tipo":     str(r.get("tipo","")).strip(),
                    "inicio":   str(r.get("inicio","")).strip(),
                    "fim":      str(r.get("fim","")).strip(),
                    "obs":      str(r.get("observacoes","")).strip(),
                })
        return {"dispensas": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class NovaDispensa(BaseModel):
    id: str
    tipo: str
    inicio: str
    fim: str
    obs: Optional[str] = ""


@router.post("/dispensas")
async def add_dispensa(body: NovaDispensa, current_user: dict = Depends(obter_admin)):
    try:
        from core.database import GoogleSheetsClient
        sh = GoogleSheetsClient().get_spreadsheet()
        ws = sh.worksheet("licencas")
        ws.append_row([body.id, body.tipo, body.inicio, body.fim, body.obs or ""])
        get_loader().limpar_cache()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/dispensas/{row}")
async def del_dispensa(row: int, current_user: dict = Depends(obter_admin)):
    try:
        from core.database import GoogleSheetsClient
        sh = GoogleSheetsClient().get_spreadsheet()
        ws = sh.worksheet("licencas")
        ws.delete_rows(row)
        get_loader().limpar_cache()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
