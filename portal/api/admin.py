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


# ── Escala Geral ─────────────────────────────────────────────
@router.get("/escala-dia/{aba}")
async def escala_dia_admin(aba: str, current_user: dict = Depends(obter_admin)):
    """Devolve escala de um dia com trocas aplicadas e nomes formatados."""
    try:
        from portal.api.escala import _get_dia_com_trocas
        data = await _get_dia_com_trocas(aba)
        return data
    except Exception:
        # Fallback directo
        loader = get_loader()
        df = loader.carregar_escala(aba)
        df_util = loader.carregar_usuarios()
        id_nome = {str(r["id"]).strip(): f"{r.get('posto','')} {r.get('nome','')}".strip()
                   for _, r in df_util.iterrows()}
        if df.empty:
            return {"entradas": [], "data": aba}
        entradas = []
        for _, r in df.iterrows():
            mid = str(r.get("id","")).strip()
            entradas.append({
                "id":       mid,
                "nome":     id_nome.get(mid, mid),
                "servico":  str(r.get("serviço","")).strip(),
                "horario":  str(r.get("horário","")).strip(),
                "viatura":  str(r.get("viatura","")).strip(),
                "radio":    str(r.get("rádio","")).strip(),
                "indicativo": str(r.get("indicativo rádio","")).strip(),
                "giro":     str(r.get("giro","")).strip(),
                "obs":      str(r.get("observações","")).strip(),
            })
        return {"entradas": entradas, "data": aba}


@router.get("/escala-pdf/{aba}")
async def escala_pdf(aba: str, current_user: dict = Depends(obter_admin)):
    """Gera e devolve PDF da escala de um dia."""
    try:
        import io, sys
        from fastapi.responses import Response
        # Importar função do app.py (Streamlit) — se não disponível, gerar simples
        sys.path.insert(0, '/app')
        loader = get_loader()
        df = loader.carregar_escala(aba)
        df_util = loader.carregar_usuarios()
        df_trocas = loader.carregar_trocas()

        if df.empty:
            raise HTTPException(status_code=404, detail="Escala não encontrada")

        # Aplicar trocas
        data_fmt = f"{aba[3:5]}/{aba[:2]}/{__import__('datetime').datetime.now().year}"
        df_at = df.copy()
        df_at['id_disp'] = df_at['id'].astype(str)
        if not df_trocas.empty:
            import re
            tr_v = df_trocas[
                (df_trocas['status'] == 'Aprovada') &
                (df_trocas['servico_origem'] != 'MATAR_REMUNERADO')
            ]
            for _, t in tr_v.iterrows():
                m_o = df_at['id'].astype(str) == str(t['id_origem'])
                if m_o.any():
                    df_at.loc[m_o, 'id_disp'] = f"{t['id_destino']} 🔄 {t['id_origem']}"
                m_d = df_at['id'].astype(str) == str(t['id_destino'])
                if m_d.any():
                    df_at.loc[m_d, 'id_disp'] = f"{t['id_origem']} 🔄 {t['id_destino']}"

        # Gerar PDF simples com ReportLab
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import tempfile, base64 as _b64

        try:
            pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVu-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
            fn, fn_bold = 'DejaVu', 'DejaVu-Bold'
        except Exception:
            fn, fn_bold = 'Helvetica', 'Helvetica-Bold'

        id_nome = {str(r["id"]).strip(): f"{r.get('posto','')} {r.get('nome','')}".strip()
                   for _, r in df_util.iterrows()}

        buf = io.BytesIO()
        cv = rl_canvas.Canvas(buf, pagesize=A4)
        w, h = A4

        # Cabeçalho
        _cab_b64 = os.environ.get("PDF_CABECALHO_B64", "")
        y = h - 10*mm
        if _cab_b64:
            try:
                import tempfile as _tmp
                _cb = _b64.b64decode(_cab_b64)
                with _tmp.NamedTemporaryFile(suffix='.jpg', delete=False) as _tf:
                    _tf.write(_cb); _cp = _tf.name
                cab_w = 170*mm; cab_h = cab_w * (235/398)
                cv.drawImage(_cp, 20*mm, h-8*mm-cab_h, width=cab_w, height=cab_h, preserveAspectRatio=True)
                os.unlink(_cp)
                y = h - 8*mm - cab_h - 8*mm
            except Exception:
                pass

        # Título
        cv.setFont(fn_bold, 14)
        cv.setFillColor(HexColor('#0B1929'))
        dia_fmt = f"{aba[3:5]}/{aba[:2]}"
        cv.drawCentredString(w/2, y - 8*mm, f"ESCALA — {dia_fmt}")
        y -= 20*mm

        # Agrupar por serviço
        from collections import defaultdict
        grupos = defaultdict(list)
        for _, r in df_at.iterrows():
            serv = str(r.get('serviço','')).strip()
            hor  = str(r.get('horário','')).strip()
            mid  = str(r.get('id','')).strip()
            nome = id_nome.get(mid, mid)
            id_d = str(r.get('id_disp', mid)).strip()
            grupos[f"{serv}|{hor}"].append(f"{nome} ({id_d})")

        cv.setFont(fn_bold, 10)
        for chave, militares in sorted(grupos.items()):
            serv, hor = chave.split('|', 1)
            if not serv: continue
            cv.setFillColor(HexColor('#0B1929'))
            cv.setFont(fn_bold, 9)
            label = f"{serv}" + (f" — {hor}" if hor else "")
            cv.drawString(20*mm, y, label)
            y -= 5*mm
            cv.setFont(fn, 9)
            cv.setFillColor(HexColor('#334155'))
            for m in militares:
                cv.drawString(25*mm, y, m)
                y -= 5*mm
            y -= 2*mm
            if y < 30*mm:
                cv.showPage()
                y = h - 20*mm

        cv.save()
        pdf_bytes = buf.getvalue()
        return Response(content=pdf_bytes, media_type="application/pdf",
                       headers={"Content-Disposition": f"attachment; filename=Escala_{aba}.pdf"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Lista abas ───────────────────────────────────────────────
@router.get("/lista-abas")
async def lista_abas(current_user: dict = Depends(obter_admin)):
    try:
        loader = get_loader()
        abas = loader.carregar_lista_abas()
        return {"abas": abas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Despublicar ───────────────────────────────────────────────
@router.post("/despublicar/{aba}")
async def despublicar(aba: str, current_user: dict = Depends(obter_admin)):
    try:
        from core.database import GoogleSheetsClient
        sh = GoogleSheetsClient().get_spreadsheet()
        ws_pub = sh.worksheet("dias_publicados")
        vals = ws_pub.col_values(1)
        for i, v in enumerate(vals, start=1):
            if str(v).strip() == aba:
                ws_pub.delete_rows(i)
                get_loader().limpar_cache()
                return {"ok": True}
        return {"ok": True, "msg": "Não encontrado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
