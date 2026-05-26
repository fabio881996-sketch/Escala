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


def _verificar_descanso(u_id: str, data_str: str, novo_horario: str, loader: DataLoader) -> tuple[bool, str]:
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
        minhas = df[
            (df["id_origem"].astype(str) == str(u_id)) |
            (df["id_destino"].astype(str) == str(u_id))
        ]
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
        pendentes = df[
            (df["status"] == "Pendente_Militar") &
            (df["id_destino"].astype(str) == str(u_id))
        ]
        trocas = pendentes.fillna("").to_dict(orient="records")
        df_util = loader.carregar_usuarios()
        nomes = {str(r["id"]).strip(): str(r.get("nome", r.get("id", ""))).strip()
                 for _, r in df_util.iterrows()}
        for t in trocas:
            t["nome_origem"] = nomes.get(str(t.get("id_origem", "")), str(t.get("id_origem", "")))
        return {"trocas": trocas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
                    # Verificar se cedeu o remunerado
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
                ok, motivo = _verificar_descanso(mid, data_fmt, horario, loader)
                if not ok:
                    continue

            elif tipo == "folga":
                # Eu tenho folga, quero trocar com quem tem serviço
                if e_folga or e_remunerado:
                    continue
                ok, _ = _verificar_descanso(mid, data_fmt, meu_horario or "", loader)
                if not ok:
                    continue

            elif tipo == "dar_remunerado":
                # Eu tenho remunerado e quero ceder — o destino deve ter serviço normal
                if e_folga or e_remunerado:
                    continue
                ok, _ = _verificar_descanso(mid, data_fmt, meu_horario or "", loader)
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

            disponiveis_lista.append({
                "id": mid,
                "nome": nomes.get(mid, mid),
                "servico": servico,
                "horario": horario,
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


@router.post("/solicitar")
async def solicitar_troca(pedido: PedidoTroca, current_user: dict = Depends(obter_user_atual)):
    """Cria pedido de troca."""
    u_id = current_user.get("sub")
    try:
        from core.database import get_sheet
        sh = get_sheet()
        ws = sh.worksheet("registos_trocas")
        ws.append_row([
            pedido.data, u_id, pedido.servico_origem,
            pedido.id_destino, pedido.servico_destino,
            "Pendente_Militar", pedido.observacoes or ""
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
        return {"ok": True}
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
        if resposta.row_index < 1 or resposta.row_index >= len(rows):
            raise HTTPException(status_code=404, detail="Linha não encontrada")

        row = rows[resposta.row_index]
        # Colunas: data, id_origem, servico_origem, id_destino, servico_destino, status, obs
        id_destino = str(row[3]).strip() if len(row) > 3 else ""
        if id_destino != u_id:
            raise HTTPException(status_code=403, detail="Não és o destinatário desta troca")

        novo_status = "Aprovada" if resposta.acao == "aceitar" else "Rejeitada"
        # Coluna status = coluna F = índice 6 (1-based para gspread)
        col_status = 6
        ws.update_cell(resposta.row_index + 1, col_status, novo_status)
        # Notificar o autor original
        try:
            from portal.api.notificacoes import enviar_push
            id_origem = str(row[1]).strip()
            emoji = "✅" if novo_status == "Aprovada" else "❌"
            enviar_push(
                u_ids=[id_origem],
                titulo=f"{emoji} Troca {novo_status.lower()}",
                corpo=f"A tua troca de {row[0]} foi {novo_status.lower()}.",
                url="/trocas",
            )
        except Exception:
            pass
        return {"ok": True, "status": novo_status}
    except HTTPException:
        raise
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
        ws.update_cell(resposta.row_index + 1, 6, novo_status)
        return {"ok": True, "status": novo_status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
