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
    """Gera PDF da escala de um dia."""
    import io, os, base64 as _b64, tempfile as _tmp, re as _re
    from fastapi.responses import Response
    from reportlab.pdfgen import canvas as _canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from collections import defaultdict

    try:
        pdfmetrics.registerFont(TTFont('DV', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DV-B', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
        fn, fb = 'DV', 'DV-B'
    except Exception:
        fn, fb = 'Helvetica', 'Helvetica-Bold'

    try:
        loader = get_loader()
        df = loader.carregar_escala(aba)
        if df.empty:
            raise HTTPException(status_code=404, detail="Escala não encontrada para " + aba)

        df_util = loader.carregar_usuarios()
        id_nome = {str(r["id"]).strip(): f"{r.get('posto','')} {r.get('nome','')}".strip()
                   for _, r in df_util.iterrows()}

        # Aplicar trocas aprovadas
        try:
            df_trocas = loader.carregar_trocas()
            df_at = df.copy()
            df_at['id_disp'] = df_at['id'].astype(str)
            if not df_trocas.empty:
                ano = __import__('datetime').datetime.now().year
                data_fmt = f"{aba[:2]}/{aba[3:5]}/{ano}"
                tr_v = df_trocas[
                    (df_trocas['data'] == data_fmt) &
                    (df_trocas['status'] == 'Aprovada') &
                    (df_trocas['servico_origem'] != 'MATAR_REMUNERADO')
                ]
                for _, t in tr_v.iterrows():
                    m_o = df_at['id'].astype(str) == str(t['id_origem'])
                    if m_o.any(): df_at.loc[m_o, 'id_disp'] = f"{t['id_destino']} ↔ {t['id_origem']}"
                    m_d = df_at['id'].astype(str) == str(t['id_destino'])
                    if m_d.any(): df_at.loc[m_d, 'id_disp'] = f"{t['id_origem']} ↔ {t['id_destino']}"
        except Exception:
            df_at = df.copy()
            df_at['id_disp'] = df_at['id'].astype(str)

        buf = io.BytesIO()
        cv = _canvas.Canvas(buf, pagesize=A4)
        w, h = A4

        # Cabeçalho com imagem
        y = h - 10*mm
        _cab = os.environ.get("PDF_CABECALHO_B64", "")
        if _cab:
            try:
                _cb = _b64.b64decode(_cab)
                with _tmp.NamedTemporaryFile(suffix='.jpg', delete=False) as _tf:
                    _tf.write(_cb); _cp = _tf.name
                cw = 160*mm; ch = cw * (235/398)
                cv.drawImage(_cp, 20*mm, h-8*mm-ch, width=cw, height=ch, preserveAspectRatio=True)
                os.unlink(_cp)
                y = h - 8*mm - ch - 6*mm
            except Exception:
                pass

        cv.setFont(fb, 13); cv.setFillColor(HexColor('#0f2540'))
        dia_fmt = f"{aba[:2]}/{aba[3:5]}"
        cv.drawCentredString(w/2, y, f"ESCALA DE SERVIÇO — {dia_fmt}")
        y -= 12*mm

        # Agrupar por serviço/horário
        grupos = defaultdict(list)
        for _, r in df_at.iterrows():
            mid = str(r.get('id','')).strip()
            if not mid: continue
            serv = str(r.get('serviço','')).strip()
            hor  = str(r.get('horário','')).strip()
            id_d = str(r.get('id_disp', mid)).strip()
            nome = id_nome.get(mid, mid)
            label = nome + (f" ({id_d})" if id_d != mid else "")
            grupos[f"{serv}|||{hor}"].append(label)

        CATS = [
            (r'ferias|licen|convalesc|folga|fcaa', 'Ausências / Folgas'),
            (r'pronto|secretaria|dilig|tribunal|instrução', 'ADM / Outras'),
            (r'atendimento', 'Atendimento'),
            (r'apoio', 'Apoio ao Atendimento'),
            (r'patrulha ocorr', 'Patrulha Ocorrências'),
            (r'patrulha|ronda', 'Patrulhas'),
            (r'remun|gratif', 'Remunerados'),
        ]

        def _cat(serv):
            s = serv.lower()
            for pat, lbl in CATS:
                if _re.search(pat, s): return lbl
            return 'Outros'

        por_cat = defaultdict(list)
        for chave, nomes in grupos.items():
            serv, hor = chave.split('|||')
            por_cat[_cat(serv)].append((serv, hor, nomes))

        for cat_label in [c2 for _,c2 in CATS] + ['Outros']:
            items = por_cat.get(cat_label, [])
            if not items: continue

            # Header categoria
            cv.setFillColor(HexColor('#0f2540'))
            cv.rect(20*mm, y-5*mm, 170*mm, 5.5*mm, fill=1, stroke=0)
            cv.setFillColor(HexColor('#ffffff'))
            cv.setFont(fb, 8)
            cv.drawString(22*mm, y-3.8*mm, cat_label.upper())
            y -= 7*mm

            for serv, hor, nomes in sorted(items, key=lambda x: x[1]):
                cv.setFont(fb, 8.5); cv.setFillColor(HexColor('#0f2540'))
                label = serv + (f" ({hor})" if hor else "")
                cv.drawString(22*mm, y, label)
                cv.setFont(fn, 8.5); cv.setFillColor(HexColor('#212529'))
                nomes_str = '   '.join(nomes)
                if len(nomes_str) > 110:
                    mid_i = len(nomes)//2
                    cv.drawString(55*mm, y, '   '.join(nomes[:mid_i]))
                    y -= 4.5*mm
                    cv.drawString(55*mm, y, '   '.join(nomes[mid_i:]))
                else:
                    cv.drawString(55*mm, y, nomes_str)
                y -= 5.5*mm
                if y < 25*mm:
                    cv.showPage(); y = h - 20*mm

            y -= 2*mm

        cv.setFont(fn, 7); cv.setFillColor(HexColor('#adb5bd'))
        cv.drawRightString(w-20*mm, 12*mm, "Portal de Escalas GNR — Posto Territorial de Famalicão")
        cv.save()

        return Response(content=buf.getvalue(), media_type="application/pdf",
                       headers={"Content-Disposition": f"attachment; filename=Escala_{aba}.pdf"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        from datetime import datetime as _dt_a
        _ano_a = _dt_a.now().year
        df_dia = loader.carregar_escala(aba)
        df_util = loader.carregar_usuarios()
        df_trocas = loader.carregar_trocas()
        df_licencas = loader.carregar_licencas()
        df_ferias = loader.carregar_ferias(_ano_a)
        feriados = loader.carregar_feriados(_ano_a)

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
        from datetime import datetime as _dt_d
        hoje_d = _dt_d.now().strftime("%d/%m/%Y")
        result = []
        if not df.empty:
            for idx, r in df.iterrows():
                fim_str = str(r.get("fim","")).strip()
                # Comparar datas no formato DD/MM/YYYY
                try:
                    activa = not fim_str or _dt_d.strptime(fim_str, "%d/%m/%Y") >= _dt_d.strptime(hoje_d, "%d/%m/%Y")
                except Exception:
                    activa = True
                result.append({
                    "__row": idx + 2,
                    "id":       str(r.get("id","")).strip(),
                    "nome":     id_nome.get(str(r.get("id","")).strip(), str(r.get("id","")).strip()),
                    "tipo":     str(r.get("tipo","")).strip(),
                    "inicio":   str(r.get("inicio","")).strip(),
                    "fim":      fim_str,
                    "obs":      str(r.get("observacoes","")).strip(),
                    "activa":   activa,
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
