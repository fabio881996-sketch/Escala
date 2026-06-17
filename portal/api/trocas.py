"""Router de trocas."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from services.data_loader_factory import get_data_loader as _get_data_loader
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


def get_loader():
    return _get_data_loader()


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
        minhas["__row_index"] = minhas["id"] if "id" in minhas.columns else minhas.index + 2
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
        pendentes["__row_index"] = pendentes["id"] if "id" in pendentes.columns else pendentes.index + 2
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
            # Só trocas de serviço (não remunerados) bloqueiam disponibilidade
            aprovadas = df_trocas[
                (df_trocas["data"] == data_fmt) &
                (df_trocas["status"] == "Aprovada") &
                (~df_trocas["servico_origem"].isin(["MATAR_REMUNERADO","FAZER_REMUNERADO"]))
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
        # Verificar se cedi o remunerado
        _eu_cedi_rem = not df_trocas.empty and data_fmt and not df_trocas[
            (df_trocas["data"] == data_fmt) &
            (df_trocas["status"] == "Aprovada") &
            (df_trocas["servico_origem"] == "MATAR_REMUNERADO") &
            (df_trocas["id_origem"].astype(str).str.strip() == u_id)
        ].empty
        if not df_dia.empty:
            minha_linha = df_dia[df_dia["id"].astype(str).str.strip().apply(
                lambda x: u_id == x or u_id in [i.strip() for i in x.split(";")]
            )]
            for _, row in minha_linha.iterrows():
                sv = str(row.get("serviço","")).strip()
                # Ignorar remunerado se cedeu, ou sempre ignorar remunerado para meu_servico
                if re.search(r"remun|gratif", sv.lower()):
                    continue
                meu_servico = sv
                meu_horario = str(row.get("horário","")).strip()
                break

        # ── Filtrar disponíveis consoante o tipo ──
        disponiveis_lista = []

        if df_dia.empty:
            return {"meu_servico": meu_servico, "meu_horario": meu_horario, "disponiveis": []}

        # Expandir linhas com múltiplos IDs separados por ;
        rows_expandidas = []
        for _, row in df_dia.iterrows():
            raw_id = str(row.get("id", "")).strip()
            ids_linha = [i.strip() for i in raw_id.split(";") if i.strip()]
            for single_id in ids_linha:
                row_copy = row.copy()
                row_copy["id"] = single_id
                rows_expandidas.append(row_copy)

        for row in rows_expandidas:
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
            # Se cedeu o remunerado (MATAR_REMUNERADO), não é remunerado
            if e_remunerado and not df_trocas.empty and data_fmt:
                cedeu = not df_trocas[
                    (df_trocas["data"] == data_fmt) &
                    (df_trocas["status"] == "Aprovada") &
                    (df_trocas["servico_origem"] == "MATAR_REMUNERADO") &
                    (df_trocas["id_origem"].astype(str).str.strip() == mid)
                ].empty
                if cedeu:
                    e_remunerado = False

            # Se tem FAZER_REMUNERADO aprovado, esse remunerado não impede trocas do serviço principal
            if not e_remunerado and not df_trocas.empty and data_fmt:
                pass  # já tratado acima



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
                            (df_trocas["servico_origem"].str.upper().isin(["MATAR_REMUNERADO","FAZER_REMUNERADO"])) &
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
                        (df_trocas["servico_origem"].str.upper().isin(["MATAR_REMUNERADO","FAZER_REMUNERADO"])) &
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
                                (df_trocas["servico_origem"].str.upper().isin(["MATAR_REMUNERADO","FAZER_REMUNERADO"])) &
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
        from datetime import datetime as _dt
        loader = get_loader()
        loader.guardar_troca({
            "data": pedido.data, "id_origem": u_id,
            "servico_origem": pedido.servico_origem,
            "id_destino": pedido.id_destino,
            "servico_destino": pedido.servico_destino,
            "status": "Pendente_Militar",
            "observacoes": pedido.observacoes or "",
            "data_pedido": _dt.now().strftime("%d/%m/%Y %H:%M"),
        })
        # Notificar o destinatário
        try:
            from portal.api.notificacoes import enviar_push
            enviar_push(u_ids=[pedido.id_destino], titulo="🔄 Novo pedido de troca",
                       corpo=f"Tens um pedido de troca para {pedido.data}.", url="/trocas")
        except Exception:
            pass
        # Se pedido, criar também MATAR_REMUNERADO
        if pedido.incluir_remunerado:
            try:
                loader.guardar_troca({
                    "data": pedido.data, "id_origem": u_id,
                    "servico_origem": "MATAR_REMUNERADO",
                    "id_destino": pedido.id_destino,
                    "servico_destino": pedido.servico_destino,
                    "status": "Pendente_Militar", "observacoes": "",
                    "data_pedido": _dt.now().strftime("%d/%m/%Y %H:%M"),
                })
            except Exception:
                pass
        loader.limpar_cache()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancelar-aprovada")
async def cancelar_troca_aprovada(payload: CancelarTroca, current_user: dict = Depends(obter_user_atual)):
    """Cancela uma troca já aprovada — notifica ambos os militares."""
    try:
        loader = get_loader()
        df = loader.carregar_trocas()
        # Encontrar troca pelo row_index (id no PG)
        troca = None
        if not df.empty:
            matches = df[df["id"] == payload.row_index] if "id" in df.columns else df.iloc[payload.row_index-2:payload.row_index-1]
            if not matches.empty:
                troca = matches.iloc[0]
        if troca is None:
            raise HTTPException(status_code=404, detail="Troca não encontrada")
        if str(troca.get("status","")).strip() != "Aprovada":
            raise HTTPException(status_code=400, detail="Troca não está aprovada")

        loader.actualizar_status_troca(int(troca["id"]) if "id" in troca else payload.row_index, "Cancelada")
        loader.limpar_cache()

        try:
            from portal.api.notificacoes import enviar_push
            id_origem  = str(troca.get("id_origem","")).strip()
            id_destino = str(troca.get("id_destino","")).strip()
            data_troca = str(troca.get("data","")).strip()
            enviar_push(
                u_ids=[i for i in [id_origem, id_destino] if i],
                titulo="🚫 Troca cancelada",
                corpo=f"A troca de {data_troca} foi cancelada.",
                url="/trocas", tag="troca-cancelada",
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
        loader = get_loader()
        df = loader.carregar_trocas()
        troca = None
        if not df.empty and "id" in df.columns:
            try:
                matches = df[df["id"].astype(int) == int(payload.row_index)]
            except Exception:
                matches = df[df["id"].astype(str) == str(payload.row_index)]
            if not matches.empty:
                troca = matches.iloc[0]
        if troca is None:
            raise HTTPException(status_code=404, detail="Troca não encontrada")
        if str(troca.get("id_origem","")).strip() != str(u_id).strip():
            raise HTTPException(status_code=403, detail="Só o autor pode cancelar")
        loader.actualizar_status_troca(int(troca["id"]), "Cancelada")
        loader.limpar_cache()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Responder a pedido (aceitar/rejeitar) ────────────────────

class RespostaTroca(BaseModel):
    row_index: int   # índice da linha na sheet (1-based, incluindo cabeçalho)
    acao: str        # "aceitar" | "rejeitar"
    data_troca: Optional[str] = ""      # DD/MM/YYYY para identificar linha exacta
    id_origem_troca: Optional[str] = "" # id_origem para identificar linha exacta


@router.post("/responder")
async def responder_troca(resposta: RespostaTroca, current_user: dict = Depends(obter_user_atual)):
    """Aceita ou rejeita um pedido de troca pendente."""
    u_id = str(current_user.get("sub"))
    try:
        from datetime import datetime as _dt
        loader = get_loader()
        df = loader.carregar_trocas()
        troca = None
        if not df.empty and "id" in df.columns:
            try:
                matches = df[df["id"].astype(int) == int(resposta.row_index)]
            except Exception:
                matches = df[df["id"].astype(str) == str(resposta.row_index)]
            if not matches.empty:
                troca = matches.iloc[0]
        if troca is None:
            raise HTTPException(status_code=404, detail=f"Troca não encontrada (row_index={resposta.row_index})")
        if str(troca.get("id_destino","")).strip() != str(u_id).strip():
            raise HTTPException(status_code=403, detail=f"Não és o destinatário. Esperado: {str(troca.get('id_destino','')).strip()}, Tu: {str(u_id).strip()}")

        novo_status = "Pendente_Admin" if resposta.acao == "aceitar" else "Rejeitada"
        data_aceitacao = _dt.now().strftime("%d/%m/%Y %H:%M") if resposta.acao == "aceitar" else None
        loader.actualizar_status_troca(int(troca["id"]), novo_status, data_aceitacao)
        loader.limpar_cache()

        try:
            from portal.api.notificacoes import enviar_push
            id_origem = str(troca.get("id_origem","")).strip()
            data_troca = str(troca.get("data","")).strip()
            if resposta.acao == "aceitar":
                enviar_push(u_ids=[id_origem], titulo="🔄 Troca aceite — aguarda validação",
                           corpo=f"A tua troca de {data_troca} foi aceite e aguarda validação do admin.", url="/trocas")
                # Notificar admins
                from config.settings import ADMINS
                df_util = loader.carregar_usuarios()
                admin_ids = df_util[df_util["email"].astype(str).str.lower().isin([a.lower() for a in ADMINS])]["id"].astype(str).str.strip().tolist() if not df_util.empty and "email" in df_util.columns else []
                if admin_ids:
                    enviar_push(u_ids=admin_ids, titulo="⚖️ Troca aguarda validação",
                               corpo=f"Troca de {data_troca} aguarda validação.", url="/trocas", tag="validar-troca")
            else:
                enviar_push(u_ids=[id_origem], titulo="❌ Troca recusada",
                           corpo=f"A tua troca de {data_troca} foi recusada.", url="/trocas")
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
        # No PostgreSQL, o id é o identificador real

        def _hor_fim(serv):
            import re as _re
            m = _re.search(r'\((\d{2})-(\d{2})\)', str(serv))
            return int(m.group(2)) if m else None

        def _hor_ini(serv):
            import re as _re
            m = _re.search(r'\((\d{2})-(\d{2})\)', str(serv))
            return int(m.group(1)) if m else None

        def _consecutivo_aviso(id_mil, nome_mil, serv_vai_fazer, data_str):
            """Verifica se o militar vai ficar com serviços consecutivos (16-24 + 00-08 no dia seguinte)."""
            avisos = []
            try:
                from datetime import datetime as _dt, timedelta as _td
                dt = _dt.strptime(data_str, "%d/%m/%Y")
                hf = _hor_fim(serv_vai_fazer)
                hi = _hor_ini(serv_vai_fazer)
                if hf is None: return []

                # Se vai fazer 00-08, verificar se no dia anterior tem 16-24
                if hi == 0:
                    aba_ant = (dt - _td(days=1)).strftime("%d-%m")
                    try:
                        df_ant = loader.carregar_escala(aba_ant)
                        if not df_ant.empty:
                            mil_ant = df_ant[df_ant["id"].astype(str).str.strip() == id_mil]
                            for _, r_ant in mil_ant.iterrows():
                                s_ant = str(r_ant.get("serviço",""))
                                h_ant = str(r_ant.get("horário",""))
                                serv_ant_full = f"{s_ant} ({h_ant})" if h_ant else s_ant
                                if _hor_fim(serv_ant_full) in (0, 24):
                                    avisos.append(f"⚠️ {nome_mil} ficará com serviços consecutivos: <b>{serv_ant_full}</b> seguido de <b>{serv_vai_fazer}</b>")
                    except Exception:
                        pass

                # Se vai fazer 16-24, verificar se no dia seguinte tem 00-08
                if hf in (0, 24):
                    aba_seg = (dt + _td(days=1)).strftime("%d-%m")
                    try:
                        df_seg = loader.carregar_escala(aba_seg)
                        if not df_seg.empty:
                            mil_seg = df_seg[df_seg["id"].astype(str).str.strip() == id_mil]
                            for _, r_seg in mil_seg.iterrows():
                                s_seg = str(r_seg.get("serviço",""))
                                h_seg = str(r_seg.get("horário",""))
                                serv_seg_full = f"{s_seg} ({h_seg})" if h_seg else s_seg
                                if _hor_ini(serv_seg_full) == 0:
                                    avisos.append(f"⚠️ {nome_mil} ficará com serviços consecutivos: <b>{serv_vai_fazer}</b> seguido de <b>{serv_seg_full}</b>")
                    except Exception:
                        pass
            except Exception:
                pass
            return avisos

        for idx, row in pend.iterrows():
            data_str   = str(row.get("data", ""))
            id_orig    = str(row.get("id_origem", ""))
            id_dest    = str(row.get("id_destino", ""))
            serv_orig  = str(row.get("servico_origem", ""))
            serv_dest  = str(row.get("servico_destino", ""))
            nome_orig  = id_nome.get(id_orig, id_orig)
            nome_dest  = id_nome.get(id_dest, id_dest)

            # Após troca: origem vai fazer serv_dest, destino vai fazer serv_orig
            avisos = []
            if serv_orig not in ("MATAR_REMUNERADO", "FAZER_REMUNERADO"):
                avisos += _consecutivo_aviso(id_orig, nome_orig, serv_dest, data_str)
                avisos += _consecutivo_aviso(id_dest, nome_dest, serv_orig, data_str)

            # No PostgreSQL, o id da troca é o identificador real
            real_row = int(row.get("id", idx)) if row.get("id") else int(idx)

            trocas.append({
                "data":            data_str,
                "id_origem":       id_orig,
                "nome_origem":     nome_orig,
                "servico_origem":  serv_orig,
                "id_destino":      id_dest,
                "nome_destino":    nome_dest,
                "servico_destino": serv_dest,
                "observacoes":     str(row.get("observacoes", "")),
                "data_pedido":     str(row.get("data_pedido", "")),
                "data_aceitacao":  str(row.get("data_aceitacao", "")),
                "__row_index":     real_row,
                "avisos_consecutivos": avisos,
            })
        return {"trocas": trocas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Admin: validar trocas ────────────────────────────────────

@router.post("/validar")
async def validar_troca(resposta: RespostaTroca, current_user: dict = Depends(obter_admin)):
    """Admin valida ou rejeita definitivamente uma troca já aceite pelo militar."""
    try:
        loader = get_loader()
        df = loader.carregar_trocas()

        # Encontrar troca por data+id_origem ou por id
        troca = None
        if not df.empty and "id" in df.columns:
            if resposta.data_troca and resposta.id_origem_troca:
                matches = df[
                    (df["data"].astype(str) == resposta.data_troca.strip()) &
                    (df["id_origem"].astype(str) == resposta.id_origem_troca.strip()) &
                    (df["status"].astype(str) == "Pendente_Admin")
                ]
                if not matches.empty:
                    troca = matches.iloc[0]
            if troca is None:
                matches = df[
                    (df["id"] == resposta.row_index) &
                    (df["status"].astype(str) == "Pendente_Admin")
                ]
                if not matches.empty:
                    troca = matches.iloc[0]

        if troca is None:
            raise HTTPException(status_code=404, detail="Linha não encontrada")

        novo_status = "Aprovada" if resposta.acao == "aceitar" else "Rejeitada"
        from datetime import datetime as _dt2
        loader.actualizar_status_troca(int(troca["id"]), novo_status, _dt2.now().strftime("%d/%m/%Y %H:%M"))
        loader.limpar_cache()

        # Gerar PDF no Drive se aprovada
        if novo_status == "Aprovada":
            try:
                _data      = str(troca.get("data","")).strip()
                _id_orig   = str(troca.get("id_origem","")).strip()
                _serv_orig = str(troca.get("servico_origem","")).strip()
                _id_dest   = str(troca.get("id_destino","")).strip()
                _serv_dest = str(troca.get("servico_destino","")).strip()
                _data_ped  = str(troca.get("data_pedido","")).strip()
                _data_ace  = str(troca.get("data_aceitacao","")).strip()

                df_u = loader.carregar_usuarios()
                _id_nome = {str(r["id"]).strip(): f"{r.get('posto','')} {r.get('nome','')}".strip()
                            for _, r in df_u.iterrows() if str(r.get("id","")).strip()}
                _nome_orig = _id_nome.get(_id_orig, _id_orig)
                _nome_dest = _id_nome.get(_id_dest, _id_dest)

                from portal.api.trocas_pdf import gerar_pdf_troca
                gerar_pdf_troca(
                    data=_data, nome_orig=_nome_orig, serv_orig=_serv_orig,
                    nome_dest=_nome_dest, serv_dest=_serv_dest,
                    data_pedido=_data_ped, data_aceitacao=_data_ace,
                    validador=f"{current_user.get('posto','')} {current_user.get('nome','')}".strip(),
                    data_validacao=_dt2.now().strftime("%d/%m/%Y %H:%M"),
                )
            except Exception as _e:
                pass  # PDF é opcional — não bloquear a validação

        # Notificar militares
        try:
            from portal.api.notificacoes import enviar_push
            _data_t = str(troca.get("data","")).strip()
            _id_o = str(troca.get("id_origem","")).strip()
            _id_d = str(troca.get("id_destino","")).strip()
            if novo_status == "Aprovada":
                enviar_push(u_ids=[_id_o, _id_d], titulo="✅ Troca aprovada",
                           corpo=f"A troca de {_data_t} foi aprovada.", url="/trocas", tag="troca-aprovada")
            else:
                enviar_push(u_ids=[_id_o, _id_d], titulo="❌ Troca rejeitada",
                           corpo=f"A troca de {_data_t} foi rejeitada.", url="/trocas", tag="troca-rejeitada")
        except Exception:
            pass

        return {"ok": True, "status": novo_status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
