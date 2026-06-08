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


# ── Gerar Escala ─────────────────────────────────────────────
@router.post("/gerar-escala")
async def gerar_escala_endpoint(body: dict, current_user: dict = Depends(obter_admin)):
    """Gera escala automática para um ou mais dias."""
    try:
        # Importar a lógica de geração do Streamlit
        import sys
        sys.path.insert(0, '/app')
        from portal.api.escala import gerar_escala_auto_dia
        
        dias = body.get("dias", [])
        resultados = []
        for aba in dias:
            try:
                res = await gerar_escala_auto_dia(aba)
                resultados.append(res)
            except Exception as e:
                resultados.append({"aba": aba, "erro": str(e), "escalados": [], "avisos": []})
        
        return {"resultados": resultados}
    except ImportError:
        # Fallback: retornar estrutura vazia com mensagem
        raise HTTPException(status_code=501, detail="Endpoint gerar-escala em implementação — use o Streamlit por agora")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/guardar-escala")
async def guardar_escala_endpoint(body: dict, current_user: dict = Depends(obter_admin)):
    """Guarda escala gerada no Sheets."""
    try:
        raise HTTPException(status_code=501, detail="Endpoint guardar-escala em implementação — use o Streamlit por agora")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Remunerados calcular/confirmar ──────────────────────────
@router.post("/remunerados/calcular")
async def calc_remunerados(body: dict, current_user: dict = Depends(obter_admin)):
    """Calcula nomeação de remunerados multi-slot."""
    try:
        import re
        loader = get_loader()
        df_dia = loader.carregar_escala(body["aba"])
        df_util = loader.carregar_usuarios()
        df_trocas = loader.carregar_trocas()
        df_ord_rem = loader.carregar_ordem_remunerados()
        df_ferias = loader.carregar_ferias()
        df_licencas = loader.carregar_licencas()
        feriados = loader.carregar_feriados()

        from datetime import datetime as _dt
        dt_rem = _dt.strptime(body["data"], "%d/%m/%Y")
        is_fds = dt_rem.weekday() >= 5

        id_nome = {str(r["id"]).strip(): f"{r.get('posto','')} {r.get('nome','')}".strip()
                   for _, r in df_util.iterrows()}

        def _norm(t): return str(t).lower().strip()
        def _parse_h(h):
            try:
                p = str(h).strip().split('-')
                return int(p[0])*60, int(p[1])*60
            except: return None, None

        def _cols_tab(tab):
            if tab == "B": return "total_ano_b","ultimo_b"
            elif is_fds: return "total_ano_a_fds","ultimo_a_fds"
            else: return "total_ano_a_semana","ultimo_a_semana"

        _IMP_ABS = r'ferias|licen|convalesc|fcaa|cter|dilig|pronto'
        militares_de_folga, servicos_dia, ausentes_dia = set(), {}, set()
        if not df_dia.empty:
            for _, row in df_dia.iterrows():
                mid = str(row.get("id","")).strip()
                serv = str(row.get("serviço","")).strip()
                hor  = str(row.get("horário","")).strip()
                sn = _norm(serv)
                if re.search(r'folga semanal|folga complementar', sn): militares_de_folga.add(mid)
                elif re.search(_IMP_ABS, sn): ausentes_dia.add(mid)
                elif not re.search(r'remu|grat', sn):
                    hi, hf = _parse_h(hor)
                    servicos_dia.setdefault(mid,[]).append((hi,hf,serv))
        for mid in (df_util["id"].astype(str).str.strip() if not df_util.empty else []):
            # férias
            pass

        def _pode(row_r, mid, slot, ja_nom):
            if mid in ausentes_dia: return False
            hi_n, hf_n = _parse_h(slot["hor"])
            todos = list(servicos_dia.get(mid,[]))
            for (si,mi) in ja_nom:
                if mi == mid:
                    sp = slots_p[si]
                    hi2,hf2 = _parse_h(sp["hor"])
                    todos.append((hi2,hf2,f"Rem {sp['hor']}"))
            for hi_s,hf_s,_ in todos:
                if None in (hi_s,hf_s,hi_n,hf_n): continue
                e1=hf_s if hf_s>hi_s else hf_s+1440
                e2=hf_n if hf_n>hi_n else hf_n+1440
                if hi_s<e2 and hi_n<e1: return False
            prescinde = str(row_r.get("prescinde_descanso","")).lower() in ("true","1","sim")
            if not prescinde:
                for hi_s,hf_s,_ in todos:
                    if None in (hi_s,hf_s,hi_n,hf_n): continue
                    fim_s=hf_s if hf_s>hi_s else hf_s+1440
                    fim_n=hf_n if hf_n>hi_n else hf_n+1440
                    d1=(hi_n+1440-fim_s)%1440
                    d2=(hi_s+1440-fim_n)%1440
                    at = re.compile(r'atendimento|apoio', re.I)
                    if not (d1>=480 or d2>=480) and not at.search(_) if len(_:=_)>0 else True:
                        if not (d1>=480 or d2>=480): return False
            return True

        import pandas as pd
        slots_p = body.get("slots",[])
        resultados = []
        ja_nom = []

        for si, slot in enumerate(slots_p):
            if not slot.get("hor"): continue
            col_t, col_u = _cols_tab(slot.get("tab","A"))
            for col in [col_t,col_u]:
                if col not in df_ord_rem.columns: df_ord_rem[col]=""
            df_ord_rem[col_t] = pd.to_numeric(df_ord_rem[col_t],errors='coerce').fillna(0)
            df_ord_rem[col_u] = pd.to_datetime(df_ord_rem[col_u],dayfirst=True,errors='coerce')
            df_disp = df_ord_rem[df_ord_rem["disponivel"].astype(str).str.lower().isin(["true","1","sim"])].copy()
            df_disp_s = df_disp.sort_values([col_u,col_t],ascending=[True,True],na_position='first')

            nomeados, avisos, skipped = [], [], []

            def _nomear(filtro_fn, label_fn, aviso=False):
                for _, row_r in df_disp_s.iterrows():
                    if len(nomeados) >= slot["n"]: break
                    mid = str(row_r.get("id","")).strip()
                    if not mid or mid in [n["id"] for n in nomeados]: continue
                    if not filtro_fn(row_r, mid): continue
                    sk = []
                    if _pode(row_r, mid, slot, ja_nom):
                        if aviso: avisos.append(f"⚠️ <b>{id_nome.get(mid,mid)}</b> nomeado fora dos voluntários")
                        nomeados.append({"id":mid,"nome":id_nome.get(mid,mid),"grupo":label_fn(mid),"total":int(row_r[col_t])})
                        ja_nom.append((si,mid))
                    else:
                        skipped.extend(sk)

            vol = lambda r,m: str(r.get("voluntario","")).lower() in ("true","1","sim")
            folga_ok = lambda r,m: str(r.get("folga","")).lower() in ("true","1","sim")
            ja_n = lambda m: any(m==mi for _,mi in ja_nom)

            _nomear(lambda r,m: vol(r,m) and m not in ausentes_dia and m not in militares_de_folga and not ja_n(m),
                    lambda m: "Voluntário c/ serviço" if m in servicos_dia else "Voluntário disponível")
            _nomear(lambda r,m: vol(r,m) and m in militares_de_folga and folga_ok(r,m) and m not in ausentes_dia and not ja_n(m),
                    lambda m: "Voluntário de folga")
            _nomear(lambda r,m: not vol(r,m) and m not in ausentes_dia and m not in militares_de_folga and not ja_n(m),
                    lambda m: "Não voluntário", aviso=True)
            _nomear(lambda r,m: vol(r,m) and m not in ausentes_dia and m not in militares_de_folga and ja_n(m),
                    lambda m: "Voluntário (já nomeado noutro remunerado)")
            _nomear(lambda r,m: vol(r,m) and m in militares_de_folga and folga_ok(r,m) and m not in ausentes_dia and ja_n(m),
                    lambda m: "Voluntário de folga (já nomeado noutro remunerado)")

            resultados.append({"slot":slot,"nomeados":nomeados,"avisos":avisos,"skipped":skipped})

        return {"resultados": resultados, "data": body["data"], "aba": body["aba"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/remunerados/confirmar")
async def conf_remunerados(body: dict, current_user: dict = Depends(obter_admin)):
    """Confirma nomeação e escreve na escala."""
    try:
        import requests as _req
        secret = os.environ.get("RAILWAY_NOTIFY_SECRET","")
        railway_url = "https://portal-escalas-gnr-production.up.railway.app"

        from core.database import GoogleSheetsClient
        sh = GoogleSheetsClient().get_spreadsheet()
        resultado = body.get("resultado",{})

        for res in resultado.get("resultados",[]):
            if not res.get("nomeados"): continue
            slot = res["slot"]
            ids = [n["id"] for n in res["nomeados"]]
            aba = resultado["aba"]
            ws_dia = sh.worksheet(aba)
            ws_dia.append_row([
                ";".join(ids),
                f"Svç Remunerado - Tabela {slot.get('tab','A')}",
                slot["hor"], "", "", "", slot.get("obs",""),
            ])
            # Atualizar ordem_remunerados
            loader = get_loader()
            df_ord = loader.carregar_ordem_remunerados()
            # Notificar
            try:
                _req.post(f"{railway_url}/api/notificacoes/notificar-interno", json={
                    "secret": secret,
                    "u_ids": ids,
                    "titulo": "💶 Nomeação para Remunerado",
                    "corpo": f"Foste nomeado para Remunerado Tabela {slot.get('tab','A')} — {slot['hor']} — {resultado['data']}.",
                    "url": "/home", "tag": "remunerado",
                }, timeout=5)
            except: pass

        get_loader().limpar_cache()
        return {"ok": True}
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
