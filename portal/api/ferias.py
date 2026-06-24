"""Router de férias — plano do utilizador autenticado."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from portal.api.auth import obter_user_atual
from services.data_loader_pg import DataLoader

router = APIRouter()


def get_loader() -> DataLoader:
    return DataLoader()


def _parse_data(valor: str, ano: int) -> str | None:
    """Converte MM/DD ou DD/MM para DD/MM/YYYY."""
    v = str(valor).strip()
    if not v or v in ("", "nan"):
        return None
    for fmt in ("%m/%d", "%d/%m", "%m-%d", "%d-%m"):
        try:
            dt = datetime.strptime(v, fmt)
            return f"{dt.day:02d}/{dt.month:02d}/{ano}"
        except ValueError:
            continue
    return None


def _dias_corridos(ini_str: str, fim_str: str, ano: int) -> int:
    """Calcula dias corridos entre duas datas DD/MM/YYYY."""
    try:
        ini = datetime.strptime(ini_str, "%d/%m/%Y")
        fim = datetime.strptime(fim_str, "%d/%m/%Y")
        return (fim - ini).days + 1
    except Exception:
        return 0


@router.get("/meu")
async def minhas_ferias(current_user: dict = Depends(obter_user_atual)):
    """Devolve o plano de férias do utilizador autenticado."""
    u_id = str(current_user.get("sub"))
    ano = datetime.now().year

    try:
        loader = get_loader()
        df = loader.carregar_ferias(ano)

        if df.empty:
            return {"ano": ano, "periodos": [], "total_dias_uteis": 0}

        # Encontrar linha do utilizador
        # PG: usar método específico para períodos individuais
        periodos_raw = loader.carregar_ferias_periodos(ano, u_id)
        if not periodos_raw:
            return {"ano": ano, "periodos": [], "total_dias_uteis": 0}

        periodos: list[dict[str, Any]] = []
        total_uteis = 0

        for row in periodos_raw:
            ini_raw = str(row.get("inicio", "")).strip()
            fim_raw = str(row.get("fim", "")).strip()
            if not ini_raw or ini_raw == "nan":
                continue
            ini_fmt = _parse_data(ini_raw, ano)
            fim_fmt = _parse_data(fim_raw, ano) if fim_raw and fim_raw != "nan" else ini_fmt
            if not ini_fmt:
                continue
            dias_uteis = 0
            try:
                dias_uteis = int(float(str(row.get("dias", 0))))
            except (ValueError, TypeError):
                dias_uteis = 0
            n = int(row.get("periodo", len(periodos) + 1))
            dias_corr = _dias_corridos(ini_fmt, fim_fmt, ano)
            total_uteis += dias_uteis
            periodos.append({
                "numero": n,
                "inicio": ini_fmt,
                "fim": fim_fmt,
                "dias_corridos": dias_corr,
                "dias_uteis": dias_uteis,
            })

        return {
            "ano": ano,
            "periodos": periodos,
            "total_dias_uteis": total_uteis,
        }

    except Exception as e:
        logger.error("Erro interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@router.get("/escala-ics")
async def escala_ics(token: str = None, current_user: dict = Depends(obter_user_atual)):
    """Devolve os serviços publicados do utilizador em formato ICS."""
    u_id = str(current_user.get("sub"))
    try:
        loader = get_loader()
        hj = datetime.now()
        dias_pub = loader.carregar_dias_publicados()
        df_trocas = loader.carregar_trocas()

        dias_a_mostrar = []
        for delta in range(90):
            dt = (hj + timedelta(days=delta)).date()
            if dt.strftime("%d-%m") in dias_pub:
                dias_a_mostrar.append(dt)
            if len(dias_a_mostrar) >= 60:
                break

        escalas = loader.carregar_escalas_batch(dias_a_mostrar)

        linhas = [
            "BEGIN:VCALENDAR", "VERSION:2.0",
            "PRODID:-//GNR Famalicao//Escala//PT",
            "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
            "X-WR-CALNAME:Escala GNR Famalicao",
        ]

        AUSENCIAS = {"folga", "ferias", "licen", "doente", "conval", "dilig", "tribunal", "pronto"}

        for dt in dias_a_mostrar:
            aba = dt.strftime("%d-%m")
            df_d = escalas.get(aba)
            if df_d is None or df_d.empty:
                continue
            meu = df_d[df_d["id"].astype(str).str.strip() == u_id]
            if meu.empty:
                continue

            row = meu.iloc[0]
            d_s = dt.strftime("%d/%m/%Y")
            servico = str(row.get("serviço", "")).strip()
            horario = str(row.get("horário", "")).strip()

            # Aplicar trocas
            if not df_trocas.empty:
                tr = df_trocas[
                    (df_trocas["data"] == d_s) &
                    (df_trocas["status"] == "Aprovada") &
                    (df_trocas["servico_origem"] != "MATAR_REMUNERADO")
                ]
                for _, t in tr.iterrows():
                    if str(t["id_origem"]).strip() == u_id:
                        s = str(t["servico_destino"])
                        servico = s.rsplit("(", 1)[0].strip()
                        horario = s.rsplit("(", 1)[1].rstrip(")") if "(" in s else horario
                    elif str(t["id_destino"]).strip() == u_id:
                        s = str(t["servico_origem"])
                        servico = s.rsplit("(", 1)[0].strip()
                        horario = s.rsplit("(", 1)[1].rstrip(")") if "(" in s else horario

            # Excluir ausências
            sv_norm = servico.lower()
            if any(a in sv_norm for a in AUSENCIAS):
                continue

            dtstr = dt.strftime("%Y%m%d")
            # Evento com horário
            if horario and "-" in horario:
                partes = horario.split("-")
                try:
                    h_ini = int(partes[0].strip()[:2])
                    h_fim = int(partes[1].strip()[:2])
                    dt_ini = datetime(dt.year, dt.month, dt.day, h_ini, 0)
                    dt_fim = datetime(dt.year, dt.month, dt.day, h_fim, 0)
                    if dt_fim <= dt_ini:
                        dt_fim = dt_fim + timedelta(days=1)
                    fmt = lambda d: d.strftime("%Y%m%dT%H%M%S")
                    linhas += [
                        "BEGIN:VEVENT",
                        f"UID:escala-{u_id}-{dtstr}@gnr",
                        f"DTSTART:{fmt(dt_ini)}",
                        f"DTEND:{fmt(dt_fim)}",
                        f"SUMMARY:{servico}",
                        "END:VEVENT",
                    ]
                except Exception:
                    pass
            else:
                linhas += [
                    "BEGIN:VEVENT",
                    f"UID:escala-{u_id}-{dtstr}@gnr",
                    f"DTSTART;VALUE=DATE:{dtstr}",
                    f"DTEND;VALUE=DATE:{datetime(dt.year, dt.month, dt.day + 1 if dt.day < 28 else 1).strftime('%Y%m%d')}",
                    f"SUMMARY:{servico}",
                    "END:VEVENT",
                ]

        linhas.append("END:VCALENDAR")
        from fastapi.responses import Response
        return Response(
            content="\r\n".join(linhas).encode("utf-8"),
            media_type="text/calendar",
            headers={"Content-Disposition": f"attachment; filename=escala_{u_id}.ics"},
        )
    except Exception as e:
        logger.error("Erro interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@router.get("/folgas-ics")
async def folgas_ics(token: str = None, current_user: dict = Depends(obter_user_atual)):
    """Devolve todas as folgas do ano em formato ICS."""
    u_id = str(current_user.get("sub"))
    ano = datetime.now().year
    try:
        loader = get_loader()
        df_folgas = loader.carregar_folgas(ano)
        grupos_folga = loader.carregar_grupos_folga()

        # Feriados (PG devolve lista de date objects)
        feriados = []
        try:
            feriados_raw = loader.carregar_feriados(ano)
            if isinstance(feriados_raw, list):
                feriados = feriados_raw
            elif hasattr(feriados_raw, 'iterrows'):
                for _, r in feriados_raw.iterrows():
                    try:
                        feriados.append(datetime.strptime(str(r.get("data", "")), "%d-%m").replace(year=ano).date())
                    except Exception:
                        pass
        except Exception:
            pass

        linhas = [
            "BEGIN:VCALENDAR", "VERSION:2.0",
            "PRODID:-//GNR Famalicao//Folgas//PT",
            "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
            "X-WR-CALNAME:Folgas GNR Famalicao",
        ]

        for m in range(1, 13):
            _, n_dias = monthrange(ano, m)
            for d in range(1, n_dias + 1):
                dt = date(ano, m, d)
                tipo = loader.militar_de_folga(u_id, dt, df_folgas, grupos_folga, feriados)
                if not tipo:
                    continue
                dtstr = dt.strftime("%Y%m%d")
                dtend = (dt + timedelta(days=1)).strftime("%Y%m%d")
                emoji = "\U0001f634" if "Semanal" in tipo else "\U0001f33f"
                linhas += [
                    "BEGIN:VEVENT",
                    f"UID:folga-{u_id}-{dtstr}@gnr",
                    f"DTSTART;VALUE=DATE:{dtstr}",
                    f"DTEND;VALUE=DATE:{dtend}",
                    f"SUMMARY:{emoji} {tipo}",
                    "END:VEVENT",
                ]

        linhas.append("END:VCALENDAR")
        from fastapi.responses import Response
        return Response(
            content="\r\n".join(linhas).encode("utf-8"),
            media_type="text/calendar",
            headers={"Content-Disposition": f"attachment; filename=folgas_{u_id}_{ano}.ics"},
        )
    except Exception as e:
        logger.error("Erro interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno do servidor")
