"""Serviço de carregamento de dados (FASE 2).

Extrai as responsabilidades de leitura de dados do código monolítico para uma
camada reutilizável e tipada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
import re

import pandas as pd
import streamlit as st

from config.settings import ADMINS, DISPENSA_SLOTS, EXCHANGES_SHEET_NAME, USERS_SHEET_NAME
from core.database import GoogleSheetsClient
from core.utils import normalizar_coluna, normalizar_servico, norm, parse_data_flexivel
from models.troca import Troca
from models.usuario import Usuario

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Funções standalone com @st.cache_data
# Streamlit só cacheia funções de topo — métodos de instância não são cacheados.
# O DataLoader chama estas funções para beneficiar do cache.
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _cached_load(aba_nome: str) -> pd.DataFrame:
    """Carrega aba do Sheets com cache de 5 minutos."""
    return GoogleSheetsClient().load_data(aba_nome)


@st.cache_data(ttl=120)
def _cached_load_trocas() -> pd.DataFrame:
    """Carrega trocas com cache de 2 minutos."""
    return GoogleSheetsClient().load_data(EXCHANGES_SHEET_NAME)


@st.cache_data(ttl=300)
def _cached_load_usuarios() -> pd.DataFrame:
    """Carrega utilizadores com cache de 5 minutos."""
    return GoogleSheetsClient().load_data(USERS_SHEET_NAME)


@st.cache_data(ttl=86400)
def _cached_load_feriados(aba_nome: str) -> pd.DataFrame:
    """Carrega feriados com cache de 24 horas."""
    return GoogleSheetsClient().load_data(aba_nome)


@st.cache_data(ttl=3600)
def _cached_load_grupos_folga() -> pd.DataFrame:
    """Carrega grupos de folga com cache de 1 hora."""
    return GoogleSheetsClient().load_data("grupos_folga")


@st.cache_data(ttl=3600)
def _cached_load_folgas(aba_nome: str) -> pd.DataFrame:
    """Carrega folgas com cache de 1 hora."""
    return GoogleSheetsClient().load_data(aba_nome)


@st.cache_data(ttl=300)
def _cached_load_licencas() -> pd.DataFrame:
    """Carrega licenças com cache de 5 minutos."""
    return GoogleSheetsClient().load_data("Licenças")


@st.cache_data(ttl=120)
def _cached_load_dias_publicados() -> pd.DataFrame:
    """Carrega dias publicados com cache de 2 minutos."""
    return GoogleSheetsClient().load_data("escala_publicada")


@st.cache_data(ttl=60)
def _cached_lista_abas() -> list[str]:
    """Lista abas da spreadsheet com cache de 1 minuto."""
    try:
        sh = GoogleSheetsClient().get_sheet()
        return [ws.title for ws in sh.worksheets()]
    except Exception:
        return []


@dataclass(slots=True)
class DataLoader:
    """Camada de leitura de dados a partir do Google Sheets.

    Args:
        sheets_client: Instância de cliente de dados.
    """

    sheets_client: GoogleSheetsClient

    def carregar_escala(self, data_ref: date | datetime | str) -> pd.DataFrame:
        """Carrega escala de um dia (`DD-MM`)."""
        if isinstance(data_ref, (date, datetime)):
            aba = data_ref.strftime("%d-%m")
        else:
            aba = str(data_ref).strip()
        logger.debug("A carregar escala para aba '%s'", aba)
        return _cached_load(aba)

    def carregar_escalas(
        self,
        data_inicio: date | datetime,
        data_fim: date | datetime,
        *,
        batch: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """Carrega escalas por período."""
        if data_fim < data_inicio:
            raise ValueError("data_fim não pode ser anterior a data_inicio")

        datas: list[date] = []
        cursor = data_inicio.date() if isinstance(data_inicio, datetime) else data_inicio
        fim = data_fim.date() if isinstance(data_fim, datetime) else data_fim
        while cursor <= fim:
            datas.append(cursor)
            cursor += timedelta(days=1)

        if batch:
            return self.carregar_escalas_batch(datas)

        return {d.strftime("%d-%m"): self.carregar_escala(d) for d in datas}

    def carregar_escalas_batch(self, datas: list[date]) -> dict[str, pd.DataFrame]:
        """Carrega múltiplas escalas usando cache por aba."""
        if not datas:
            return {}
        resultado: dict[str, pd.DataFrame] = {}
        for d in datas:
            aba = d.strftime("%d-%m")
            try:
                resultado[aba] = _cached_load(aba)
            except Exception as exc:
                logger.warning("Falha a carregar aba '%s': %s", aba, exc)
                resultado[aba] = pd.DataFrame()
        return resultado

    def carregar_usuarios(self) -> pd.DataFrame:
        """Carrega utilizadores da worksheet padrão."""
        logger.debug("A carregar utilizadores")
        return _cached_load_usuarios()

    def carregar_usuarios_model(self) -> list[Usuario]:
        """Carrega utilizadores como modelos de domínio."""
        df = self.carregar_usuarios()
        if df.empty:
            return []
        admins = {a.lower() for a in ADMINS}
        return [Usuario.from_row(row.to_dict(), admin_emails=admins) for _, row in df.iterrows()]

    def carregar_trocas(self) -> pd.DataFrame:
        """Carrega registos de trocas."""
        logger.debug("A carregar trocas")
        return _cached_load_trocas()

    def carregar_trocas_model(self) -> list[Troca]:
        """Carrega trocas como modelos de domínio."""
        df = self.carregar_trocas()
        if df.empty:
            return []
        return [Troca.from_row(row.to_dict(), idx=idx) for idx, (_, row) in enumerate(df.iterrows())]

    def carregar_ferias(self, ano: int) -> pd.DataFrame:
        """Carrega férias do ano (`ferias_YYYY`)."""
        df = _cached_load(f"ferias_{ano}")
        if df.empty:
            return df
        return df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]

    def carregar_folgas(self, ano: int) -> pd.DataFrame:
        """Carrega folgas do ano (`folgas_YYYY`)."""
        df = _cached_load_folgas(f"folgas_{ano}")
        if df.empty:
            return df

        rename_map: dict[str, str] = {}
        for col in df.columns:
            col_n = str(col).strip().lower()
            if col_n in ("servico", "serviço", "service"):
                rename_map[col] = "serviço"
            elif col_n in ("excecoes", "exceções", "exceçoes"):
                rename_map[col] = "exceções"
            elif col_n in ("grupo", "group"):
                rename_map[col] = "grupo"
            elif col_n in ("fds",):
                rename_map[col] = "fds"
        if rename_map:
            df = df.rename(columns=rename_map)
        return df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]

    def carregar_licencas(self) -> pd.DataFrame:
        """Carrega aba de licenças e normaliza o tipo de ausência."""
        df = _cached_load_licencas()
        if df.empty:
            return df
        col_tipo = next((c for c in df.columns if "tipo" in str(c).lower()), None)
        if col_tipo:
            df[col_tipo] = df[col_tipo].apply(normalizar_servico)
        return df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]

    def carregar_grupos_folga(self) -> dict[str, dict[str, list[str]]]:
        """Carrega grupos de folga no formato legado."""
        df = _cached_load_grupos_folga()
        if df.empty:
            return {}

        headers = [str(c).strip() for c in df.columns]
        col_grupo = next((c for c in headers if normalizar_coluna(c) == "grupo"), None)
        if not col_grupo:
            return {}

        tipos = [h for h in headers if h != col_grupo]
        result: dict[str, dict[str, list[str]]] = {}
        for _, row in df.iterrows():
            grupo = str(row.get(col_grupo, "") or "").strip()
            if not grupo:
                continue
            result[grupo] = {}
            for tipo in tipos:
                dias_str = str(row.get(tipo, "") or "").strip()
                result[grupo][tipo] = [d.strip() for d in re.split(r"[;,]+", dias_str) if d.strip()]
        return result

    def carregar_servicos(self) -> dict[str, list[str]]:
        """Carrega a matriz de serviços por militar ({id: [serviços]})."""
        try:
            ws = self.sheets_client.get_worksheet("serviços")
            vals = ws.get_all_values()
            if not vals:
                return {}
            headers = [str(h).strip() for h in vals[0]]
            result: dict[str, list[str]] = {}
            for col in headers:
                idx = headers.index(col)
                for row in vals[1:]:
                    mid = str(row[idx]).strip() if idx < len(row) else ""
                    if mid and mid != "nan":
                        result.setdefault(mid, []).append(col)
            return result
        except Exception as exc:
            logger.warning("Falha a carregar serviços: %s", exc)
            return {}

    def carregar_feriados(self, ano: int) -> list[date]:
        """Carrega feriados de um ano a partir da aba `feriados`."""
        try:
            ws = self.sheets_client.get_worksheet("feriados")
            valores = ws.get_all_values()
            if not valores:
                return []

            feriados: list[date] = []
            num_cols = max(len(r) for r in valores)
            for ci in range(num_cols):
                col = [str(r[ci]).strip() if ci < len(r) else "" for r in valores]
                col = [v for v in col if v]
                if not col:
                    continue
                try:
                    ano_col = int(col[0])
                except Exception:
                    continue
                if ano_col != ano:
                    continue
                for valor in col[1:]:
                    dt = parse_data_flexivel(valor)
                    if dt:
                        feriados.append(dt)
            return feriados
        except Exception as exc:
            logger.warning("Falha a carregar feriados: %s", exc)
            return []

    def carregar_lista_abas(self) -> list[str]:
        """Lista títulos de worksheets (com cache de 1 minuto)."""
        result = _cached_lista_abas()
        if result:
            return result
        # Fallback sem cache
        try:
            return [ws.title for ws in self.sheets_client.get_sheet().worksheets()]
        except Exception as exc:
            logger.warning("Falha a carregar lista de abas: %s", exc)
            return []

    def carregar_listas(self) -> dict[str, list[str]]:
        """Carrega aba `listas` no formato `{coluna: [valores]}`."""
        try:
            ws = self.sheets_client.get_worksheet("listas")
            vals = ws.get_all_values()
            if not vals:
                return {}
            hdrs = [str(h).strip() for h in vals[0]]
            result: dict[str, list[str]] = {}
            for h in hdrs:
                idx = hdrs.index(h)
                result[h] = [""] + [
                    str(row[idx]).strip()
                    for row in vals[1:]
                    if idx < len(row) and str(row[idx]).strip()
                ]
            return result
        except Exception as exc:
            logger.warning("Erro ao carregar listas: %s", exc)
            return {}

    def carregar_dias_publicados(self) -> set[str]:
        """Carrega dias publicados no formato ``DD-MM``.

        Tenta primeiro o cache rápido; se vazio, usa fallback por worksheet.
        """
        # Tentativa rápida via cache
        df = _cached_load_dias_publicados()
        if not df.empty:
            col = df.columns[0]
            dias = {str(v).strip() for v in df[col] if str(v).strip() and str(v).strip() != "data"}
            if dias:
                return dias

        # Fallback: procurar em múltiplas abas
        for worksheet_name in ("dias_publicados", "escala_publicada"):
            try:
                ws = self.sheets_client.get_worksheet(worksheet_name)
                vals = ws.get_all_values()
                dias_set: set[str] = set()
                for row in vals:
                    if not row:
                        continue
                    val = str(row[0]).strip()
                    if re.match(r"^\d{2}-\d{2}$", val):
                        dias_set.add(val)
                if dias_set:
                    return dias_set
            except Exception:
                continue
        return set()

    def limpar_cache(self) -> None:
        """Limpa todos os caches de leitura."""
        for fn in [
            _cached_load,
            _cached_load_trocas,
            _cached_load_usuarios,
            _cached_load_feriados,
            _cached_load_grupos_folga,
            _cached_load_folgas,
            _cached_load_licencas,
            _cached_load_dias_publicados,
            _cached_lista_abas,
        ]:
            try:
                fn.clear()
            except Exception as exc:
                logger.debug("Falha ao limpar cache (ignorado): %s", exc)

    def limpar_cache_escala(self) -> None:
        """Limpa só o cache de escalas diárias."""
        try:
            _cached_load.clear()
        except Exception:
            pass

    def _atualizar_ordem_escala_dia(self, sh, aba_dia: str, d_gerar: date | datetime) -> None:
        """Atualiza o ``ordem_escala`` do dia seguinte com base na escala do dia atual."""
        slots_auto = {
            ("atendimento", "00-08"): "Atendimento 00-08",
            ("atendimento", "08-16"): "Atendimento 08-16",
            ("atendimento", "16-24"): "Atendimento 16-24",
            ("patrulha ocorrencias", "00-08"): "Patrulha Ocorrências 00-08",
            ("patrulha ocorrencias", "08-16"): "Patrulha Ocorrências 08-16",
            ("patrulha ocorrencias", "16-24"): "Patrulha Ocorrências 16-24",
            ("apoio atendimento", "08-16"): "Apoio Atendimento 08-16",
            ("apoio atendimento", "16-24"): "Apoio Atendimento 16-24",
            ("apoio ao atendimento", "08-16"): "Apoio Atendimento 08-16",
            ("apoio ao atendimento", "16-24"): "Apoio Atendimento 16-24",
        }

        try:
            d_ref = d_gerar.date() if isinstance(d_gerar, datetime) else d_gerar
            abas = self.carregar_lista_abas()
            aba_ord = f"ordem_escala {aba_dia}"
            aba_ord_ant = f"ordem_escala {(d_ref - timedelta(days=1)).strftime('%d-%m')}"

            ws_base = None
            for nome in (aba_ord, aba_ord_ant):
                if nome in abas:
                    ws_base = sh.worksheet(nome)
                    break
            if ws_base is None:
                return

            vals = ws_base.get_all_values()
            if not vals:
                return

            headers = [str(h).strip() for h in vals[0]]
            ordem: dict[str, list[str]] = {h: [] for h in headers}
            for row in vals[1:]:
                for i, h in enumerate(headers):
                    v = str(row[i]).strip() if i < len(row) else ""
                    if v:
                        ordem[h].append(v)

            ws_dia = sh.worksheet(aba_dia)
            vals_dia = ws_dia.get_all_values()
            if not vals_dia:
                return

            hdrs_dia = [str(h).strip().lower() for h in vals_dia[0]]
            ix_id = hdrs_dia.index("id") if "id" in hdrs_dia else 0
            ix_sv = hdrs_dia.index("serviço") if "serviço" in hdrs_dia else 1
            ix_hr = hdrs_dia.index("horário") if "horário" in hdrs_dia else 2

            escalados_por_slot: dict[str, list[str]] = {}
            for row in vals_dia[1:]:
                sv = normalizar_coluna(str(row[ix_sv]).strip()) if ix_sv < len(row) else ""
                hr = str(row[ix_hr]).strip() if ix_hr < len(row) else ""
                ids = str(row[ix_id]).strip() if ix_id < len(row) else ""
                col_key = slots_auto.get((sv, hr))
                if not col_key or not ids or ids == "nan":
                    continue
                for mid in re.split(r"[;,]+", ids):
                    mid = mid.strip()
                    if mid:
                        escalados_por_slot.setdefault(col_key, []).append(mid)

            for col_key, mids in escalados_por_slot.items():
                if col_key not in ordem:
                    continue
                for mid in mids:
                    if mid in ordem[col_key]:
                        ordem[col_key].remove(mid)
                        ordem[col_key].append(mid)

            nome_prox = f"ordem_escala {(d_ref + timedelta(days=1)).strftime('%d-%m')}"
            nova = [headers]
            max_len = max((len(v) for v in ordem.values()), default=1)
            for i in range(max_len):
                nova.append([ordem[h][i] if i < len(ordem[h]) else "" for h in headers])

            if nome_prox in abas:
                ws_prox = sh.worksheet(nome_prox)
                ws_prox.clear()
                ws_prox.update("A1", nova)
            else:
                ws_prox = sh.add_worksheet(title=nome_prox, rows=100, cols=max(1, len(headers)))
                ws_prox.update("A1", nova)

            try:
                ws_prox.hide()
            except Exception:
                pass

        except Exception as exc:
            logger.warning("Erro ao atualizar ordem_escala dia '%s': %s", aba_dia, exc)

    def atualizar_ordem_escala_em_cadeia(
        self,
        sh,
        aba_dia: str,
        d_gerar: date | datetime,
        max_dias: int = 9,
    ) -> None:
        """Usado ao EDITAR escala existente.

        Actualiza em cadeia os ``ordem_escala`` dos dias seguintes que já têm
        aba de escala.
        """
        import time as _time

        d_gerar_d = d_gerar.date() if isinstance(d_gerar, datetime) else d_gerar
        abas = self.carregar_lista_abas()

        # Sempre gerar ordem_escala do dia seguinte
        self._atualizar_ordem_escala_dia(sh, aba_dia, d_gerar_d)
        _time.sleep(1)

        # Continuar em cadeia apenas para dias que já têm aba de escala criada
        d_atual = d_gerar_d + timedelta(days=1)
        for _ in range(max_dias - 1):
            aba_atual = d_atual.strftime("%d-%m")
            if aba_atual not in abas:
                break

            self._atualizar_ordem_escala_dia(sh, aba_atual, d_atual)
            _time.sleep(1)
            d_atual = d_atual + timedelta(days=1)
            abas = self.carregar_lista_abas()

    def gerar_ordem_escala_dia_seguinte(
        self,
        sh,
        aba_dia: str,
        d_gerar: date | datetime,
    ) -> None:
        """Usado ao CONFIRMAR escala nova.

        Gera apenas o ``ordem_escala`` do dia seguinte — sem cadeia.
        """
        d_gerar_d = d_gerar.date() if isinstance(d_gerar, datetime) else d_gerar
        self._atualizar_ordem_escala_dia(sh, aba_dia, d_gerar_d)

    @staticmethod
    def militar_de_ferias(
        militar_id: str,
        data_ref: date | datetime,
        df_ferias: pd.DataFrame,
        feriados_list: list[date] | None = None,
    ) -> bool:
        """Replica a regra de férias do legado (inclui extensão por fds/feriados)."""
        if df_ferias.empty:
            return False
        feriados = feriados_list or []
        cols = df_ferias.columns.tolist()
        ini_cols = [c for c in cols if "ini" in str(c).lower()]
        fim_cols = [c for c in cols if "fim" in str(c).lower()]
        id_col = "id" if "id" in cols else cols[0]

        data_d = data_ref.date() if isinstance(data_ref, datetime) else data_ref
        ano_data = data_d.year

        mil = df_ferias[df_ferias[id_col].astype(str).str.strip() == str(militar_id).strip()]
        if mil.empty:
            return False

        for ini_c, fim_c in zip(ini_cols, fim_cols):
            for _, row in mil.iterrows():
                ini_s = str(row.get(ini_c, "") or "").strip()
                fim_s = str(row.get(fim_c, "") or "").strip()
                if not ini_s or not fim_s or ini_s == "nan" or fim_s == "nan":
                    continue
                ini_d = parse_data_flexivel(ini_s, ano_data)
                fim_d = parse_data_flexivel(fim_s, ano_data)
                if not ini_d or not fim_d:
                    continue

                fim_real = fim_d
                while True:
                    prox = fim_real + timedelta(days=1)
                    if prox.weekday() >= 5 or prox in feriados:
                        fim_real = prox
                    else:
                        break

                if ini_d <= data_d <= fim_real:
                    return True

        return False

    @staticmethod
    def militar_de_folga(
        militar_id: str,
        data_ref: date | datetime,
        df_folgas: pd.DataFrame,
        grupos_folga: dict[str, dict[str, list[str]]],
        feriados: list[date],
    ) -> str:
        """Replica a lógica de identificação de folga do código legado."""
        if df_folgas.empty:
            return ""

        data_d = data_ref.date() if isinstance(data_ref, datetime) else data_ref
        aba = data_d.strftime("%d-%m")

        col_id = "id" if "id" in df_folgas.columns else df_folgas.columns[0]
        mid_norm = str(militar_id).strip().lstrip("0") or "0"
        linha = df_folgas[
            df_folgas[col_id]
            .astype(str)
            .str.strip()
            .str.lstrip("0")
            .apply(lambda x: x or "0")
            == mid_norm
        ]
        if linha.empty:
            return ""

        row = linha.iloc[0]
        excecoes_str = str(row.get("exceções", "") or row.get("excecoes", "")).strip()
        if excecoes_str and excecoes_str != "nan":
            for exc in re.split(r"[;]+", excecoes_str):
                exc = exc.strip()
                if not exc:
                    continue
                m_exc = re.match(r"(\d{2}-\d{2})\(([^)]+)\)→(\d{2}-\d{2})", exc)
                if m_exc:
                    dia_orig, tipo_exc, dia_novo = m_exc.group(1), m_exc.group(2), m_exc.group(3)
                    if dia_novo == aba:
                        return tipo_exc
                    if dia_orig == aba:
                        return ""

        fds = str(row.get("fds", "")).strip().lower()
        if fds in ("sim", "yes", "1", "true"):
            if data_d.weekday() >= 5:
                return "Folga Semanal"
            if aba in [f.strftime("%d-%m") for f in feriados]:
                return "Folga Semanal"

        grupo = str(row.get("grupo", "")).strip()
        if grupo and grupo in grupos_folga:
            for tipo, dias in grupos_folga[grupo].items():
                if aba in dias:
                    return tipo

        return ""

    @staticmethod
    def militar_de_licenca(militar_id: str, data_ref: date | datetime, df_licencas: pd.DataFrame) -> str:
        """Replica a lógica de licença/dispensa usada no monólito."""
        if df_licencas.empty:
            return ""

        cols = df_licencas.columns.tolist()
        col_id = "id" if "id" in cols else cols[0]
        col_tp = "tipo" if "tipo" in cols else (cols[1] if len(cols) > 1 else None)
        col_ini = next((c for c in cols if "ini" in str(c).lower()), None)
        col_fim = next((c for c in cols if "fim" in str(c).lower()), None)
        col_obs = next((c for c in cols if "obs" in str(c).lower()), None)
        if not col_ini or not col_fim:
            return ""

        data_d = data_ref.date() if isinstance(data_ref, datetime) else data_ref
        linhas = df_licencas[df_licencas[col_id].astype(str).str.strip() == str(militar_id).strip()]

        dispensa_slots = set(DISPENSA_SLOTS.keys())
        for _, row in linhas.iterrows():
            ini_s = str(row.get(col_ini, "") or "").strip()
            fim_s = str(row.get(col_fim, "") or "").strip()
            if not ini_s or not fim_s or ini_s == "nan" or fim_s == "nan":
                continue

            tipo = str(row.get(col_tp, "Licença") or "Licença").strip() if col_tp else "Licença"
            codigos = [c.strip().upper() for c in tipo.replace(";", ",").split(",")]
            if all(c in dispensa_slots for c in codigos if c):
                continue

            ini_d = parse_data_flexivel(ini_s, data_d.year)
            fim_d = parse_data_flexivel(fim_s, data_d.year)
            if not ini_d or not fim_d:
                continue
            if ini_d <= data_d <= fim_d:
                obs = str(row.get(col_obs, "") or "").strip() if col_obs else ""
                obs = "" if obs == "nan" else obs
                return f"{tipo}|{obs}" if obs else tipo

        return ""

    @staticmethod
    def militar_tem_dispensa_slot(
        militar_id: str,
        data_ref: date | datetime,
        df_licencas: pd.DataFrame,
        servico: str,
        horario: str,
    ) -> bool:
        """Valida dispensa por slot (A1/PO2/AA3...)."""
        if df_licencas.empty:
            return False

        dispensa_slots = DISPENSA_SLOTS

        cols = df_licencas.columns.tolist()
        col_id = "id" if "id" in cols else cols[0]
        col_tp = "tipo" if "tipo" in cols else (cols[1] if len(cols) > 1 else None)
        col_ini = next((c for c in cols if "ini" in str(c).lower()), None)
        col_fim = next((c for c in cols if "fim" in str(c).lower()), None)
        if not col_ini or not col_fim or not col_tp:
            return False

        data_d = data_ref.date() if isinstance(data_ref, datetime) else data_ref
        serv_n = norm(servico)
        hor_n = str(horario).strip()

        linhas = df_licencas[df_licencas[col_id].astype(str).str.strip() == str(militar_id).strip()]
        for _, row in linhas.iterrows():
            tipo = str(row.get(col_tp, "") or "").strip()
            codigos = [c.strip().upper() for c in tipo.replace(";", ",").split(",")]
            for codigo in codigos:
                if codigo not in dispensa_slots:
                    continue
                sv_slot, hr_slot = dispensa_slots[codigo]
                sv_slot_n = norm(sv_slot)
                serv_n_cmp = serv_n.replace(" ao ", " ")
                if sv_slot_n not in {serv_n, serv_n_cmp} or hr_slot != hor_n:
                    continue

                ini_s = str(row.get(col_ini, "") or "").strip()
                fim_s = str(row.get(col_fim, "") or "").strip()
                if not ini_s or not fim_s or ini_s == "nan" or fim_s == "nan":
                    continue
                ini_d = parse_data_flexivel(ini_s, data_d.year)
                fim_d = parse_data_flexivel(fim_s, data_d.year)
                if ini_d and fim_d and ini_d <= data_d <= fim_d:
                    return True

        return False
