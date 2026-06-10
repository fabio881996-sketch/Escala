"""Router de trocas."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.database import GoogleSheetsClient
from services.data_loader import DataLoader
from portal.api.auth import obter_user_atual, obter_admin

router = APIRouter()

# ── Impedimentos ────────────────────────────────────────────
IMPEDIMENTOS = [
    "férias", "ferias", "licença", "licenca", "doente",
    "diligência", "diligencia", "tribunal", "pronto",
    "secretaria", "inquérito", "inquerito", "baixa", "convalescença", "convalescenca",
]
IMPEDIMENTOS_RE = re.compile("|".join(IMPEDIMENTOS), re.IGNORECASE)

FOLGAS_RE = re.compile(r"folga\s*(semanal|complementar)", re.IGNORECASE)


def _norm(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def _parse_horario(h: str):
    """Devolve (ini_min, fim_min) ou None. Suporta '08-16', '00-08', '20-04'."""
    m = re.match(r"(\d{1,2})[:\-hH](\d{0,2})[\s\-–]+(\d{1,2})[:\-hH]?(\d{0,2})", str(h))
    if not m:
        return None
    h1, m1 = int(m.group(1)), int(m.group(2) or 0)
    h2, m2 = int(m.group(3)), int(m.group(4) or 0)
    ini = h1 * 60 + m1
    fim = h2 * 60 + m2
    if fim <= ini:
        fim += 1440  # passa meia-noite
    return ini, fim


def _verificar_descanso(u_id: str, data_str: str, novo_horario: str, loader: DataLoader, novo_servico: str = "") -> tuple[bool, str]:
    """Verifica 8h de descanso em relação a serviços no dia anterior e seguinte."""
    MIN_DESCANSO = 480  # 8 horas em minutos
    novo = _parse_horario(novo_horario)
    if not novo:
        return True, ""
    ini_novo, fim_novo = novo

    try:
        dt = datetime.strptime(data_str, "%d/%m/%Y")
    except ValueError:
        return True, ""

    for delta_days, lado in [(-1, "anterior"), (+1, "seguinte")]:
        dt_adj = dt + timedelta(days=delta_days)
        aba_adj = dt_adj.strftime("%d-%m")
        try:
            df_adj = loader.carregar_escala(aba_adj)
            if df_adj.empty:
                continue
            linhas = df_adj[df_adj["id"].astype(str).str.strip() == str(u_id)]
            for _, row in linhas.iterrows():
                serv_adj = str(row.get("serviço", "")).strip()
                if IMPEDIMENTOS_RE.search(serv_adj) or FOLGAS_RE.search(serv_adj):
                    continue
                adj = _parse_horario(str(row.get("horário", "")))
                if not adj:
                    continue
                ini_adj, fim_adj = adj
                if delta_days == -1:
                    # serviço anterior: descanso = ini_novo - fim_adj (ajustado para dia seguinte)
                    descanso = ini_novo + 1440 - fim_adj if fim_adj > ini_novo else ini_novo - fim_adj
                else:
                    # serviço seguinte: descanso = ini_adj + 1440 - fim_novo
                    descanso = ini_adj + 1440 - fim_novo if ini_adj < fim_novo else ini_adj - fim_novo
                if descanso < MIN_DESCANSO:
                    # Excepção: atendimento/apoio permite consecutivos 16-24 + 00-08
                    _AT = re.compile(r'atendimento|apoio ao atendimento', re.IGNORECASE)
                    if _AT.search(serv_adj) or _AT.search(novo_servico):
                        continue  # permitido
                    horas = descanso // 60
                    mins = descanso % 60
                    return False, f"Apenas {horas}h{mins:02d}m de descanso em relação ao serviço {lado}"
        except Exception:
            continue

    return True, ""


def get_loader() -> DataLoader:
    return DataLoader(sheets_client=GoogleSheetsClient())


# ── Endpoints existentes ─────────────────────────────────────

@router.get("/minhas")
async def minhas_trocas(current_user: dict = Depends(obter_user_atual)):
    """Devolve trocas do utilizador autenticado."""
    u_id = current_user.get("sub")
    try:
        loader = get_loader()
        df = loader.carregar_trocas()
        if df.empty:
            return {"trocas": []}
        df_reset = df.reset_index(drop=True)
        mask = (
            (df_reset["id_origem"].astype(str) == str(u_id)) |
            (df_reset["id_destino"].astype(str) == str(u_id))
        )
        minhas = df_reset[mask].copy()
        minhas["__row_index"] = minhas.index + 2
        trocas = minhas.fillna("").to_dict(orient="records")
        # Enriquecer com nomes
        df_util = loader.carregar_usuarios()
        nomes = {str(r["id"]).strip(): str(r.get("nome", r.get("id", ""))).strip()
                 for _, r in df_util.iterrows()}
        for t in trocas:
            t["nome_origem"] = nomes.get(str(t.get("id_origem", "")), str(t.get("id_origem", "")))
            t["nome_destino"] = nomes.get(str(t.get("id_destino", "")), str(t.get("id_destino", "")))
        return {"trocas": trocas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pendentes")
async def trocas_pendentes(current_user: dict = Depends(obter_user_atual)):
    """Devolve trocas pendentes de resposta do utilizador."""
    u_id = current_user.get("sub")
    try:
        loader = get_loader()
        df = loader.carregar_trocas()
        if df.empty:
            return {"trocas": []}
        # Adicionar índice real da linha na sheet (1-based, incluindo cabeçalho)
        df_reset = df.reset_index(drop=True)
        mask = (
            (df_reset["status"] == "Pendente_Militar") &
            (df_reset["id_destino"].astype(str) == str(u_id))
        )
        pendentes = df_reset[mask].copy()
        # índice na sheet = posição no df + 2 (1 para cabeçalho, 1 para base-1)
        pendentes["__row_index"] = pendentes.index + 2
        trocas = pendentes.fillna("").to_dict(orient="records")
        df_util = loader.carregar_usuarios()
        nomes = {str(r["id"]).strip(): str(r.get("nome", r.get("id", ""))).strip()
                 for _, r in df_util.iterrows()}
        for t in trocas:
            t["nome_origem"] = nomes.get(str(t.get("id_origem", "")), str(t.get("id_origem", "")))
        return {"trocas": trocas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _consecutivos_permitidos(serv1: str, serv2: str) -> bool:
    """Verifica se dois serviços podem ser consecutivos (16-24 + 00-08).
    Só permitido se um deles for Atendimento ou Apoio ao Atendimento."""
    _AT = re.compile(r'atendimento|apoio ao atendimento', re.IGNORECASE)
    h1 = _parse_horario(serv1)
    h2 = _parse_horario(serv2)
    if not h1 or not h2:
        return True  # sem horário definido, não bloquear
    ini1, fim1 = h1
    ini2, fim2 = h2
    # Consecutivos = fim de um é início do outro (sem descanso)
    # 16-24 (fim=1440) seguido de 00-08 (ini=0) — diferença de 0 minutos
    gap = (ini2 - fim1) % 1440
    if gap > 60:  # mais de 1h de intervalo — não são consecutivos
        return True
    # São consecutivos — só permitido se um for atendimento/apoio
    return bool(_AT.search(serv1) or _AT.search(serv2))


# ── Novo endpoint: disponíveis para troca num dia ─────────────

@router.get("/disponíveis")
async def disponiveis(
    data: str = Query(..., description="DD-MM (aba da escala)"),
    tipo: str = Query("simples", description="simples | folga | dar_remunerado | fazer_remunerado"),
    current_user: dict = Depends(obter_user_atual),
):
    """
    Devolve:
      - meu_servico: serviço do utilizador no dia
      - disponiveis: lista de militares disponíveis para o tipo de troca pedido
    """
    u_id = str(current_user.get("sub"))
    try:
        loader = get_loader()
        df_dia = loader.carregar_escala(data)
        df_util = loader.carregar_usuarios()
        df_trocas = loader.carregar_trocas()

        nomes = {str(r["id"]).strip(): str(r.get("nome", r.get("id", ""))).strip()
                 for _, r in df_util.iterrows()}

        # ── IDs com trocas já aprovadas hoje (não aparecem) ──
        data_fmt = ""
        try:
            dt = datetime.strptime(data, "%d-%m")
            data_fmt = dt.strftime(f"%d/%m/{datetime.now().year}")
        except Exception:
            pass

        ids_com_troca: set[str] = set()
        if not df_trocas.empty and data_fmt:
            aprovadas = df_trocas[
                (df_trocas["data"] == data_fmt) &
                (df_trocas["status"] == "Aprovada")
            ]
            ids_com_troca = set(
                aprovadas["id_origem"].astype(str).tolist() +
                aprovadas["id_destino"].astype(str).tolist()
            )

        # ── Militares com "Pronto" em folgas (nunca aparecem) ──
        ids_pronto: set[str] = set()
        try:
            ano = datetime.now().year
            df_folgas = loader.carregar_folgas(ano)
            if not df_folgas.empty:
                col_status = next((c for c in df_folgas.columns if "status" in c.lower() or "pronto" in c.lower()), None)
                if col_status:
                    ids_pronto = set(
                        df_folgas[df_folgas[col_status].astype(str).str.lower() == "pronto"]["id"].astype(str).tolist()
                    )
        except Exception:
            pass

        # ── Meu serviço no dia ──
        meu_servico = None
        meu_horario = None
        if not df_dia.empty:
            minha_linha = df_dia[df_dia["id"].astype(str).str.strip() == u_id]
            if not minha_linha.empty:
                row = minha_linha.iloc[0]
                meu_servico = str(row.get("serviço", "")).strip()
                meu_horario = str(row.get("horário", "")).strip()

        # ── Filtrar disponíveis consoante o tipo ──
        disponiveis_lista = []

        if df_dia.empty:
            return {"meu_servico": meu_servico, "meu_horario": meu_horario, "disponiveis": []}

        for _, row in df_dia.iterrows():
            mid = str(row.get("id", "")).strip()
            if not mid or mid == u_id or mid in ids_com_troca or mid in ids_pronto:
                continue

            servico = str(row.get("serviço", "")).strip()
            horario = str(row.get("horário", "")).strip()
            servico_norm = _norm(servico)

            # Sempre excluir impedimentos absolutos
            if IMPEDIMENTOS_RE.search(servico):
                continue

            e_folga = bool(FOLGAS_RE.search(servico))
            e_remunerado = bool(re.search(r"remun|gratif", servico_norm))

            if tipo == "simples":
                # Só militares com serviço normal (não folga, não remunerado não cedido)
                if e_folga:
                    continue
                if e_remunerado:
                    cedeu = False
                    if not df_trocas.empty and data_fmt:
                        cedeu = not df_trocas[
                            (df_trocas["data"] == data_fmt) &
                            (df_trocas["status"] == "Aprovada") &
                            (df_trocas["servico_origem"].str.upper() == "MATAR_REMUNERADO") &
                            (df_trocas["id_destino"].astype(str) == mid)
                        ].empty
                    if not cedeu:
                        continue
                # Verificar descanso
                ok, motivo = _verificar_descanso(mid, data_fmt, horario, loader, servico)
                if not ok:
                    continue
                # Verificar consecutivos ilegais
                if meu_horario and horario:
                    _bloquear = False
                    try:
                        dt_obj = datetime.strptime(data_fmt, "%d/%m/%Y")
                        serv_eu_vou_fazer = f"{servico} ({horario})"
                        serv_outro_vai_fazer = f"{meu_servico} ({meu_horario})"
                        for delta in [-1, 1]:
                            if _bloquear: break
                            aba_adj = (dt_obj + timedelta(days=delta)).strftime("%d-%m")
                            try:
                                df_adj = loader.carregar_escala(aba_adj)
                            except Exception:
                                continue
                            if df_adj.empty: continue
                            # Verificar se EU fico com consecutivos ilegais
                            for _, r_adj in df_adj[df_adj["id"].astype(str).str.strip() == u_id].iterrows():
                                s_adj = str(r_adj.get("serviço",""))
                                h_adj = str(r_adj.get("horário",""))
                                if not _consecutivos_permitidos(f"{s_adj} ({h_adj})", serv_eu_vou_fazer):
                                    _bloquear = True; break
                            if _bloquear: break
                            # Verificar se O OUTRO fica com consecutivos ilegais
                            for _, r_adj in df_adj[df_adj["id"].astype(str).str.strip() == mid].iterrows():
                                s_adj = str(r_adj.get("serviço",""))
                                h_adj = str(r_adj.get("horário",""))
                                if not _consecutivos_permitidos(f"{s_adj} ({h_adj})", serv_outro_vai_fazer):
                                    _bloquear = True; break
                    except Exception:
                        pass
                    if _bloquear:
                        continue

            elif tipo == "folga":
                # Eu tenho folga, quero trocar com quem tem serviço
                if e_folga or e_remunerado:
                    continue
                ok, _ = _verificar_descanso(mid, data_fmt, meu_horario or "", loader, meu_servico or "")
                if not ok:
                    continue

            elif tipo == "dar_remunerado":
                # Eu tenho remunerado e quero ceder — o destino deve ter serviço normal
                if e_folga or e_remunerado:
                    continue
                ok, _ = _verificar_descanso(mid, data_fmt, meu_horario or "", loader, meu_servico or "")
                if not ok:
                    continue

            elif tipo == "fazer_remunerado":
                # Quero fazer o remunerado de outro — só militares com remunerado não cedido
                if not e_remunerado:
                    continue
                cedeu = False
                if not df_trocas.empty and data_fmt:
                    cedeu = not df_trocas[
                        (df_trocas["data"] == data_fmt) &
                        (df_trocas["status"] == "Aprovada") &
                        (df_trocas["servico_origem"].str.upper() == "MATAR_REMUNERADO") &
                        (df_trocas["id_destino"].astype(str) == mid)
                    ].empty
                if cedeu:
                    continue

            # Verificar se este militar tem também remunerado nesse dia
            tem_rem = False
            rem_serv = ""
            rem_hor = ""
            if tipo == "simples" and not df_dia.empty:
                for _, row_rem in df_dia[df_dia["id"].astype(str).str.strip() == mid].iterrows():
                    s_rem = str(row_rem.get("serviço","")).strip()
                    if re.search(r"remun|gratif", _norm(s_rem)):
                        # Verificar se não cedeu já
                        cedeu_rem = False
                        if not df_trocas.empty and data_fmt:
                            cedeu_rem = not df_trocas[
                                (df_trocas["data"] == data_fmt) &
                                (df_trocas["status"] == "Aprovada") &
                                (df_trocas["servico_origem"].str.upper() == "MATAR_REMUNERADO") &
                                (df_trocas["id_destino"].astype(str) == mid)
                            ].empty
                        if not cedeu_rem:
                            tem_rem = True
                            rem_serv = s_rem
                            rem_hor = str(row_rem.get("horário","")).strip()

            disponiveis_lista.append({
                "id": mid,
                "nome": nomes.get(mid, mid),
                "servico": servico,
                "horario": horario,
                "tem_remunerado": tem_rem,
                "remunerado_servico": rem_serv,
                "remunerado_horario": rem_hor,
            })

        return {
            "meu_servico": meu_servico,
            "meu_horario": meu_horario,
            "disponiveis": disponiveis_lista,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Solicitar troca ──────────────────────────────────────────

class PedidoTroca(BaseModel):
    tipo: str
    data: str          # DD/MM/YYYY
    id_destino: str
    servico_origem: str
    servico_destino: str
    observacoes: Optional[str] = ""
    incluir_remunerado: Optional[bool] = False


@router.post("/solicitar")
async def solicitar_troca(pedido: PedidoTroca, current_user: dict = Depends(obter_user_atual)):
    """Cria pedido de troca."""
    u_id = current_user.get("sub")
    try:
        from core.database import get_sheet
        sh = get_sheet()
        ws = sh.worksheet("registos_trocas")
        from datetime import datetime as _dt
        ws.append_row([
            pedido.data, u_id, pedido.servico_origem,
            pedido.id_destino, pedido.servico_destino,
            "Pendente_Militar", pedido.observacoes or "",
            "",  # validador (col H)
            _dt.now().strftime("%d/%m/%Y %H:%M"),  # data_pedido (col I)
            "",  # data_aceitacao (col J)
        ])
        # Notificar o destinatário
        try:
            from portal.api.notificacoes import enviar_push
            enviar_push(
                u_ids=[pedido.id_destino],
                titulo="🔄 Novo pedido de troca",
                corpo=f"Tens um pedido de troca para {pedido.data}.",
                url="/trocas",
            )
        except Exception:
            pass
        # Se pedido, criar também pedido MATAR_REMUNERADO
        if pedido.incluir_remunerado:
            try:
                from datetime import datetime as _dt3
                ws.append_row([
                    pedido.data, u_id, "MATAR_REMUNERADO",
                    pedido.id_destino, pedido.servico_destino,
                    "Pendente_Militar", "",
                    "",
                    _dt3.now().strftime("%d/%m/%Y %H:%M"),
                    "",
                ])
            except Exception:
                pass

        get_loader().limpar_cache()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancelar-aprovada")
async def cancelar_troca_aprovada(payload: CancelarTroca, current_user: dict = Depends(obter_user_atual)):
    """Cancela uma troca já aprovada — notifica ambos os militares."""
    try:
        loader = get_loader()
        sh = loader.sheets_client.get_spreadsheet()
        ws = sh.worksheet("registos_trocas")
        rows = ws.get_all_values()
        row = rows[payload.row_index - 1]

        # Verificar que está Aprovada
        status_actual = str(row[5]).strip() if len(row) > 5 else ""
        if status_actual != "Aprovada":
            raise HTTPException(status_code=400, detail="Troca não está aprovada")

        ws.update_cell(payload.row_index, 6, "Cancelada")
        loader.limpar_cache()

        # Notificar ambos os militares
        try:
            from portal.api.notificacoes import enviar_push
            id_origem  = str(row[1]).strip() if len(row) > 1 else ""
            id_destino = str(row[3]).strip() if len(row) > 3 else ""
            data_troca = str(row[0]).strip() if len(row) > 0 else ""
            admin_nome = f"{current_user.get('nome','Admin')}"
            if id_origem or id_destino:
                enviar_push(
                    u_ids=[_id for _id in [id_origem, id_destino] if _id],
                    titulo="🚫 Troca cancelada",
                    corpo=f"A troca de {data_troca} foi cancelada pelo admin ({admin_nome}).",
                    url="/trocas",
                    tag="troca-cancelada",
                )
        except Exception:
            pass

        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Cancelar pedido (só o autor pode cancelar) ───────────────

class CancelarTroca(BaseModel):
    row_index: int


@router.post("/cancelar")
async def cancelar_troca(payload: CancelarTroca, current_user: dict = Depends(obter_user_atual)):
    """Cancela um pedido de troca feito pelo próprio utilizador."""
    u_id = str(current_user.get("sub"))
    try:
        from core.database import get_sheet
        sh = get_sheet()
        ws = sh.worksheet("registos_trocas")
        rows = ws.get_all_values()
        row_arr_idx = payload.row_index - 1
        if row_arr_idx < 1 or row_arr_idx >= len(rows):
            raise HTTPException(status_code=404, detail="Linha não encontrada")
        row = rows[row_arr_idx]
        id_origem = str(row[1]).strip() if len(row) > 1 else ""
        if id_origem != u_id:
            raise HTTPException(status_code=403, detail="Só o autor pode cancelar")
        ws.update_cell(payload.row_index, 6, "Cancelada")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Responder a pedido (aceitar/rejeitar) ────────────────────

class RespostaTroca(BaseModel):
    row_index: int   # índice da linha na sheet (1-based, incluindo cabeçalho)
    acao: str        # "aceitar" | "rejeitar"


@router.post("/responder")
async def responder_troca(resposta: RespostaTroca, current_user: dict = Depends(obter_user_atual)):
    """Aceita ou rejeita um pedido de troca pendente."""
    u_id = str(current_user.get("sub"))
    try:
        from core.database import get_sheet
        sh = get_sheet()
        ws = sh.worksheet("registos_trocas")
        rows = ws.get_all_values()
        # row_index é 1-based incluindo cabeçalho
        # rows[0] = cabeçalho, rows[1] = linha 2 da sheet
        row_arr_idx = resposta.row_index - 1
        if row_arr_idx < 1 or row_arr_idx >= len(rows):
            raise HTTPException(status_code=404, detail="Linha não encontrada")
        row = rows[row_arr_idx]
        # Colunas: data, id_origem, servico_origem, id_destino, servico_destino, status, obs
        id_destino = str(row[3]).strip() if len(row) > 3 else ""
        if id_destino != u_id:
            raise HTTPException(status_code=403, detail="Não és o destinatário desta troca")

        # Militar aceita → Pendente_Admin (aguarda validação do admin)
        # Militar rejeita → Rejeitada
        from datetime import datetime as _dt
        novo_status = "Pendente_Admin" if resposta.acao == "aceitar" else "Rejeitada"
        col_status = 6
        updates = [{"range": f"F{resposta.row_index}", "values": [[novo_status]]}]
        if resposta.acao == "aceitar":
            updates.append({"range": f"J{resposta.row_index}", "values": [[_dt.now().strftime("%d/%m/%Y %H:%M")]]})
        ws.batch_update(updates)
        # Notificar o autor original
        try:
            from portal.api.notificacoes import enviar_push
            id_origem = str(row[1]).strip()
            if resposta.acao == "aceitar":
                enviar_push(
                    u_ids=[id_origem],
                    titulo="🔄 Troca aceite — aguarda validação",
                    corpo=f"A tua troca de {row[0]} foi aceite e aguarda validação do admin.",
                    url="/trocas",
                )
                # Notificar admins
                try:
                    from services.data_loader import DataLoader
                    from core.database import GoogleSheetsClient
                    _loader_notif = DataLoader(sheets_client=GoogleSheetsClient())
                    df_util_notif = _loader_notif.carregar_usuarios()
                    admin_ids = df_util_notif[df_util_notif["is_admin"].astype(str).str.lower().isin(["true","1","sim"])]["id"].astype(str).str.strip().tolist()
                    if admin_ids:
                        enviar_push(
                            u_ids=admin_ids,
                            titulo="⚖️ Troca aguarda validação",
                            corpo=f"Troca de {row[0]} aguarda a tua validação.",
                            url="/trocas",
                            tag="validar-troca",
                        )
                except Exception:
                    pass
            else:
                enviar_push(
                    u_ids=[id_origem],
                    titulo="❌ Troca recusada",
                    corpo=f"A tua troca de {row[0]} foi recusada.",
                    url="/trocas",
                )
        except Exception:
            pass
        return {"ok": True, "status": novo_status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pendentes-admin")
async def trocas_pendentes_admin(current_user: dict = Depends(obter_admin)):
    """Devolve trocas Pendente_Admin para validação pelo admin."""
    try:
        loader = get_loader()
        df = loader.carregar_trocas()
        df_util = loader.carregar_usuarios()
        id_nome = {str(r["id"]).strip(): f"{r.get('posto','')} {r.get('nome','')}".strip()
                   for _, r in df_util.iterrows() if str(r.get("id","")).strip()}
        if df.empty:
            return {"trocas": []}
        pend = df[df["status"] == "Pendente_Admin"].copy()
        trocas = []
        for i, (idx, row) in enumerate(pend.iterrows()):
            trocas.append({
                "data":            str(row.get("data", "")),
                "id_origem":       str(row.get("id_origem", "")),
                "nome_origem":     id_nome.get(str(row.get("id_origem","")), str(row.get("id_origem",""))),
                "servico_origem":  str(row.get("servico_origem", "")),
                "id_destino":      str(row.get("id_destino", "")),
                "nome_destino":    id_nome.get(str(row.get("id_destino","")), str(row.get("id_destino",""))),
                "servico_destino": str(row.get("servico_destino", "")),
                "observacoes":     str(row.get("observacoes", "")),
                "data_pedido":     str(row.get("data_pedido", "")),
                "data_aceitacao":  str(row.get("data_aceitacao", "")),
                "__row_index":     idx + 2,
            })
        return {"trocas": trocas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Admin: validar trocas ────────────────────────────────────

@router.post("/validar")
async def validar_troca(resposta: RespostaTroca, current_user: dict = Depends(obter_admin)):
    """Admin valida ou rejeita definitivamente uma troca já aceite pelo militar."""
    try:
        from core.database import get_sheet
        sh = get_sheet()
        ws = sh.worksheet("registos_trocas")
        rows = ws.get_all_values()
        if resposta.row_index < 1 or resposta.row_index >= len(rows):
            raise HTTPException(status_code=404, detail="Linha não encontrada")

        novo_status = "Aprovada" if resposta.acao == "aceitar" else "Rejeitada"
        ws.update_cell(resposta.row_index, 6, novo_status)
        get_loader().limpar_cache()

        # Gerar e guardar PDF no Drive se aprovada
        if novo_status == "Aprovada":
            try:
                from reportlab.pdfgen import canvas as _canvas
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.units import mm
                from reportlab.lib.colors import HexColor
                from reportlab.lib.styles import ParagraphStyle
                from reportlab.platypus import Paragraph
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                from googleapiclient.http import MediaIoBaseUpload
                import base64 as _b64, tempfile as _tmp, os as _os, io as _io, json as _json, re as _re2
                from datetime import datetime as _dt2

                row_data = rows[resposta.row_index - 1]
                _data      = str(row_data[0]).strip() if len(row_data) > 0 else ""
                _id_orig   = str(row_data[1]).strip() if len(row_data) > 1 else ""
                _serv_orig = str(row_data[2]).strip() if len(row_data) > 2 else ""
                _id_dest   = str(row_data[3]).strip() if len(row_data) > 3 else ""
                _serv_dest = str(row_data[4]).strip() if len(row_data) > 4 else ""
                _validador = f"{current_user.get('posto','')} {current_user.get('nome','')}".strip()
                _data_val  = _dt2.now().strftime("%d/%m/%Y %H:%M")
                _data_ped  = str(row_data[8]).strip() if len(row_data) > 8 else ""
                _data_ace  = str(row_data[9]).strip() if len(row_data) > 9 else ""

                # Nomes dos militares
                loader_pdf = get_loader()
                df_u = loader_pdf.carregar_usuarios()
                _id_nome = {str(r["id"]).strip(): f"{r.get('posto','')} {r.get('nome','')}".strip()
                            for _, r in df_u.iterrows() if str(r.get("id","")).strip()}
                _nome_orig = _id_nome.get(_id_orig, _id_orig)
                _nome_dest = _id_nome.get(_id_dest, _id_dest)
                filename = f"Troca_{_data.replace('/','_')}_{_id_orig}_{_id_dest}.pdf"

                # Gerar PDF
                try:
                    pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
                    pdfmetrics.registerFont(TTFont('DejaVu-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
                    pdfmetrics.registerFont(TTFont('DejaVu-Italic', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf'))
                    fn, fn_bold, fn_it = 'DejaVu', 'DejaVu-Bold', 'DejaVu-Italic'
                except Exception:
                    fn, fn_bold, fn_it = 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique'

                _CAB_B64 = os.environ.get("PDF_CABECALHO_B64", "")
                buf = _io.BytesIO()
                cv = _canvas.Canvas(buf, pagesize=A4)
                w, h = A4

                if _CAB_B64:
                    try:
                        _cb = _b64.b64decode(_CAB_B64)
                        with _tmp.NamedTemporaryFile(suffix='.jpg', delete=False) as _tf:
                            _tf.write(_cb); _cp = _tf.name
                        cab_w = 95*mm; cab_h = cab_w * (235/398)
                        cv.drawImage(_cp, 20*mm, h-8*mm-cab_h, width=cab_w, height=cab_h, preserveAspectRatio=True)
                        _os.unlink(_cp)
                        cv.setFillColor(HexColor('#000000')); cv.setFont(fn_bold, 15)
                        cv.drawString(20*mm+cab_w+10*mm, h-8*mm-cab_h/2, "TROCA DE SERVIÇO")
                        y = h-8*mm-cab_h-10*mm
                    except Exception:
                        cv.setFont(fn_bold, 14); cv.drawCentredString(w/2, h-20*mm, "TROCA DE SERVIÇO")
                        y = h-35*mm
                else:
                    cv.setFont(fn_bold, 14); cv.drawCentredString(w/2, h-20*mm, "TROCA DE SERVIÇO")
                    y = h-35*mm

                style = ParagraphStyle('body', fontName=fn, fontSize=11, leading=18)
                texto = (
                    f"O militar <b>{_nome_orig}</b> (ID {_id_orig}), solicitou a autorização "
                    f"para a troca do serviço <b>'{_serv_orig}'</b> pelo serviço <b>'{_serv_dest}'</b> "
                    f"do militar <b>{_nome_dest}</b> (ID {_id_dest}), para o dia <b>{_data}</b>."
                )
                p = Paragraph(texto, style)
                pw, ph = p.wrap(170*mm, h); p.drawOn(cv, 20*mm, y-ph); y -= ph+10*mm

                # Aviso consecutivos
                def _hf(serv, g):
                    m = _re2.search(r'\((\d{2})-(\d{2})\)', str(serv))
                    return int(m.group(g)) if m else None
                _av = []
                if _hf(_serv_orig, 2) in (0,24) and _hf(_serv_dest, 1) == 0:
                    _av.append(f"Nota: <b>{_nome_orig}</b> ficará com serviços consecutivos: <b>{_serv_orig}</b> seguido de <b>{_serv_dest}</b>.")
                if _hf(_serv_dest, 2) in (0,24) and _hf(_serv_orig, 1) == 0:
                    _av.append(f"Nota: <b>{_nome_dest}</b> ficará com serviços consecutivos: <b>{_serv_dest}</b> seguido de <b>{_serv_orig}</b>.")
                if _av:
                    style_av = ParagraphStyle('av', fontName=fn_bold, fontSize=10, leading=14, textColor=HexColor('#b45309'))
                    for av in _av:
                        cv.setFillColor(HexColor('#FFFBEB')); cv.setStrokeColor(HexColor('#f59e0b')); cv.setLineWidth(0.8)
                        p_av = Paragraph(av, style_av); pw_av, ph_av = p_av.wrap(162*mm, h)
                        cv.rect(20*mm, y-ph_av-4*mm, 170*mm, ph_av+8*mm, fill=1, stroke=1)
                        p_av.drawOn(cv, 24*mm, y-ph_av-1*mm); y -= ph_av+14*mm

                cv.setFont(fn_bold, 10); cv.setFillColor(HexColor('#1a2b4a'))
                cv.drawString(20*mm, y, "REGISTO DE CONFIRMAÇÕES"); y -= 6*mm
                cv.setStrokeColor(HexColor('#1a2b4a')); cv.setLineWidth(0.8)
                cv.line(20*mm, y, w-20*mm, y); y -= 8*mm

                def _bloco(y, num, tit, nome, data, cor):
                    bh = 22*mm
                    cv.setFillColor(HexColor(cor)); cv.rect(20*mm, y-bh, 170*mm, bh, fill=1, stroke=0)
                    cv.setFillColor(HexColor('#1a2b4a')); cv.rect(20*mm, y-bh, 3*mm, bh, fill=1, stroke=0)
                    cv.setFont(fn_bold, 14); cv.setFillColor(HexColor('#1a2b4a')); cv.drawString(26*mm, y-14*mm, num)
                    cv.setFont(fn_bold, 9); cv.setFillColor(HexColor('#64748b')); cv.drawString(35*mm, y-8*mm, tit.upper())
                    cv.setFont(fn_bold, 11); cv.setFillColor(HexColor('#1e293b')); cv.drawString(35*mm, y-15*mm, nome)
                    cv.setFont(fn_it, 9); cv.setFillColor(HexColor('#64748b')); cv.drawRightString(w-22*mm, y-15*mm, data or "—")
                    return y-bh-4*mm

                y = _bloco(y, "①", "Solicitante", f"{_nome_orig} (ID {_id_orig})", _data_ped, '#F8FAFC')
                y = _bloco(y, "②", "Aceite pelo militar de destino", f"{_nome_dest} (ID {_id_dest})", _data_ace, '#F0FDF4')
                y = _bloco(y, "③", "Autorizado superiormente", _validador, _data_val, '#EFF6FF')

                cv.setStrokeColor(HexColor('#cccccc')); cv.setLineWidth(0.5)
                cv.line(20*mm, 22*mm, w-20*mm, 22*mm)
                cv.setFont(fn_it, 8); cv.setFillColor(HexColor('#646464'))
                cv.drawRightString(w-20*mm, 15*mm, f"Gerado em: {_dt2.now().strftime('%d/%m/%Y %H:%M')}")
                cv.save()
                pdf_bytes = buf.getvalue()

                # Upload Drive
                creds_raw = _os.environ.get("GOOGLE_CREDENTIALS", "")
                if creds_raw:
                    info = _json.loads(creds_raw)
                    creds = service_account.Credentials.from_service_account_info(
                        info, scopes=["https://www.googleapis.com/auth/drive"])
                    service = build("drive", "v3", credentials=creds)
                    folder_name = "Trocas GNR"
                    q = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                    res = service.files().list(q=q, fields="files(id)").execute()
                    files = res.get("files", [])
                    folder_id = files[0]["id"] if files else service.files().create(
                        body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
                        fields="id").execute()["id"]
                    file_meta = {"name": filename, "parents": [folder_id]}
                    media = MediaIoBaseUpload(_io.BytesIO(pdf_bytes), mimetype="application/pdf")
                    service.files().create(body=file_meta, media_body=media, fields="id").execute()
            except Exception:
                pass

        # Notificar ambos os militares
        try:
            from portal.api.notificacoes import enviar_push
            rows_all = ws.get_all_values()
            row_data = rows_all[resposta.row_index] if resposta.row_index < len(rows_all) else []
            id_origem = str(row_data[1]).strip() if len(row_data) > 1 else ""
            id_destino = str(row_data[3]).strip() if len(row_data) > 3 else ""
            data_troca = str(row_data[0]).strip() if row_data else ""
            emoji = "✅" if novo_status == "Aprovada" else "❌"
            titulo = f"{emoji} Troca {novo_status.lower()}"
            corpo = f"A troca de {data_troca} foi {novo_status.lower()} pelo admin."
            ids = [i for i in [id_origem, id_destino] if i]
            if ids:
                enviar_push(u_ids=ids, titulo=titulo, corpo=corpo, url="/trocas")
        except Exception:
            pass
        return {"ok": True, "status": novo_status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
