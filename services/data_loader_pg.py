"""DataLoader PostgreSQL — mesma interface do DataLoader Sheets.

Substitui todas as chamadas gspread por queries psycopg2.
Mantém o sistema de cache em memória para evitar queries repetidas.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timedelta
from threading import Lock

import pandas as pd
import psycopg2
import psycopg2.extras

from config.settings import ADMINS
from core.utils import norm
from models.troca import Troca
from models.usuario import Usuario

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")


# ── Cache ─────────────────────────────────────────────────────
class _Cache:
    def __init__(self):
        self._store: dict = {}
        self._lock = Lock()

    def get(self, key):
        with self._lock:
            e = self._store.get(key)
            if e and time.time() < e["expires"]:
                return e["value"], True
            return None, False

    def set(self, key, value, ttl):
        with self._lock:
            self._store[key] = {"value": value, "expires": time.time() + ttl}

    def clear(self, prefix=""):
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)] if prefix else list(self._store.keys())
            for k in keys:
                del self._store[k]


_cache = _Cache()


def _get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def _query(sql, params=None):
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()


def _execute(sql, params=None):
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()


def _execute_many(sql, rows):
    with _get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, rows)
        conn.commit()


# ── DataLoader ────────────────────────────────────────────────
class DataLoader:
    """DataLoader com backend PostgreSQL."""

    def __init__(self, sheets_client=None):
        # sheets_client ignorado — mantido por compatibilidade
        pass

    def limpar_cache(self):
        _cache.clear()

    # ── Escalas ───────────────────────────────────────────────
    def carregar_escala(self, data_ref) -> pd.DataFrame:
        if isinstance(data_ref, (date, datetime)):
            aba = data_ref.strftime("%d-%m")
        else:
            aba = str(data_ref).strip()

        key = f"escala:{aba}"
        val, hit = _cache.get(key)
        if hit:
            return val

        rows = _query("""
            SELECT militar_id AS id, servico AS "serviço", horario AS "horário",
                   viatura, radio AS "rádio", indicativo AS "indicativo rádio",
                   giro, observacoes AS "observações"
            FROM escalas WHERE aba = %s
        """, (aba,))

        df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        # Expandir IDs múltiplos (ex: "710;797" -> duas linhas)
        if not df.empty and 'id' in df.columns:
            df['id'] = df['id'].astype(str).str.split(r'[;,]')
            df = df.explode('id')
            df['id'] = df['id'].str.strip()
            df = df[df['id'] != ''].reset_index(drop=True)
        _cache.set(key, df, 300)
        return df

    def carregar_escalas_batch(self, datas: list) -> dict:
        resultado = {}
        sem_cache = []

        for d in datas:
            aba = d.strftime("%d-%m") if isinstance(d, (date, datetime)) else str(d)
            val, hit = _cache.get(f"escala:{aba}")
            if hit:
                resultado[aba] = val
            else:
                sem_cache.append(aba)

        if sem_cache:
            rows = _query("""
                SELECT aba, militar_id AS id, servico AS "serviço", horario AS "horário",
                       viatura, radio AS "rádio", indicativo AS "indicativo rádio",
                       giro, observacoes AS "observações"
                FROM escalas WHERE aba = ANY(%s)
            """, (sem_cache,))

            por_aba: dict = {aba: [] for aba in sem_cache}
            for r in rows:
                por_aba[r["aba"]].append({k: v for k, v in r.items() if k != "aba"})

            for aba, linhas in por_aba.items():
                df = pd.DataFrame(linhas) if linhas else pd.DataFrame()
                if not df.empty and 'id' in df.columns:
                    df['id'] = df['id'].astype(str).str.split(r'[;,]')
                    df = df.explode('id')
                    df['id'] = df['id'].str.strip()
                    df = df[df['id'] != ''].reset_index(drop=True)
                _cache.set(f"escala:{aba}", df, 300)
                resultado[aba] = df

        return resultado

    def guardar_escala(self, aba: str, df: pd.DataFrame):
        """Substitui a escala de um dia."""
        _execute("DELETE FROM escalas WHERE aba = %s", (aba,))
        if not df.empty:
            rows = []
            for _, r in df.iterrows():
                rows.append((
                    aba,
                    str(r.get("id", "")).strip(),
                    str(r.get("serviço", "") or "").strip() or None,
                    str(r.get("horário", "") or "").strip() or None,
                    str(r.get("viatura", "") or "").strip() or None,
                    str(r.get("rádio", "") or "").strip() or None,
                    str(r.get("indicativo rádio", "") or "").strip() or None,
                    str(r.get("giro", "") or "").strip() or None,
                    str(r.get("observações", "") or "").strip() or None,
                ))
            _execute_many("""
                INSERT INTO escalas (aba, militar_id, servico, horario, viatura, radio, indicativo, giro, observacoes)
                VALUES %s
            """, rows)
        _cache.clear(f"escala:{aba}")

    def adicionar_linha_escala(self, aba: str, row: dict):
        """Adiciona uma linha à escala (ex: remunerado nomeado)."""
        _execute("""
            INSERT INTO escalas (aba, militar_id, servico, horario, viatura, radio, indicativo, giro, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            aba,
            str(row.get("id", "")).strip(),
            str(row.get("serviço", "") or "").strip() or None,
            str(row.get("horário", "") or "").strip() or None,
            str(row.get("viatura", "") or "").strip() or None,
            str(row.get("rádio", "") or "").strip() or None,
            str(row.get("indicativo rádio", "") or "").strip() or None,
            str(row.get("giro", "") or "").strip() or None,
            str(row.get("observações", "") or "").strip() or None,
        ))
        _cache.clear(f"escala:{aba}")

    # ── Utilizadores ──────────────────────────────────────────
    def carregar_usuarios(self) -> pd.DataFrame:
        val, hit = _cache.get("utilizadores")
        if hit:
            return val
        rows = _query("SELECT id, nome, posto, nim, email, pin, giro, nascimento FROM utilizadores ORDER BY nome")
        df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        _cache.set("utilizadores", df, 60)
        return df

    def carregar_usuarios_model(self) -> list:
        df = self.carregar_usuarios()
        if df.empty:
            return []
        admins = {a.lower() for a in ADMINS}
        return [Usuario.from_row(row.to_dict(), admin_emails=admins) for _, row in df.iterrows()]

    # ── Trocas ────────────────────────────────────────────────
    def carregar_trocas(self) -> pd.DataFrame:
        val, hit = _cache.get("trocas")
        if hit:
            return val
        rows = _query("""
            SELECT id, data, id_origem, servico_origem, id_destino, servico_destino,
                   status, observacoes, data_pedido, data_aceitacao
            FROM trocas ORDER BY id
        """)
        df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        _cache.set("trocas", df, 60)
        return df

    def carregar_trocas_model(self) -> list:
        df = self.carregar_trocas()
        if df.empty:
            return []
        return [Troca.from_row(row.to_dict(), idx=idx) for idx, (_, row) in enumerate(df.iterrows())]

    def guardar_troca(self, row: dict) -> int:
        """Insere nova troca e devolve o ID."""
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trocas (data, id_origem, servico_origem, id_destino, servico_destino, status, observacoes, data_pedido)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """, (
                    row.get("data"), row.get("id_origem"), row.get("servico_origem"),
                    row.get("id_destino"), row.get("servico_destino"),
                    row.get("status", "Pendente_Militar"), row.get("observacoes"),
                    row.get("data_pedido"),
                ))
                new_id = cur.fetchone()[0]
            conn.commit()
        _cache.clear("trocas")
        return new_id

    def actualizar_status_troca(self, troca_id: int, status: str, data_aceitacao: str = None):
        _execute("""
            UPDATE trocas SET status = %s, data_aceitacao = COALESCE(%s, data_aceitacao)
            WHERE id = %s
        """, (status, data_aceitacao, troca_id))
        _cache.clear("trocas")

    # ── Férias ────────────────────────────────────────────────
    def carregar_ferias(self, ano: int) -> pd.DataFrame:
        key = f"ferias:{ano}"
        val, hit = _cache.get(key)
        if hit:
            return val
        rows = _query("""
            SELECT f.militar_id AS id, u.nome, f.inicio, f.fim, f.dias, f.obs
            FROM ferias f LEFT JOIN utilizadores u ON f.militar_id = u.id
            WHERE f.ano = %s ORDER BY f.inicio
        """, (ano,))
        df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        _cache.set(key, df, 300)
        return df

    # ── Licenças / Dispensas ──────────────────────────────────
    def carregar_licencas(self) -> pd.DataFrame:
        val, hit = _cache.get("licencas")
        if hit:
            return val
        rows = _query("""
            SELECT d.id AS __row, d.militar_id AS id, u.nome, d.tipo,
                   d.inicio, d.fim, d.observacoes AS obs, d.observacoes AS "observações", d.activa
            FROM dispensas d LEFT JOIN utilizadores u ON d.militar_id = u.id
            ORDER BY d.activa DESC, d.inicio DESC
        """)
        df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        _cache.set("licencas", df, 60)
        return df

    def adicionar_licenca(self, row: dict):
        _execute("""
            INSERT INTO dispensas (militar_id, tipo, inicio, fim, observacoes, activa)
            VALUES (%s, %s, %s, %s, %s, TRUE)
        """, (row.get("id"), row.get("tipo"), row.get("inicio"), row.get("fim") or None, row.get("obs")))
        _cache.clear("licencas")

    def remover_licenca(self, row_id: int):
        _execute("DELETE FROM dispensas WHERE id = %s", (row_id,))
        _cache.clear("licencas")

    # ── Dias publicados ───────────────────────────────────────
    def carregar_dias_publicados(self) -> set:
        val, hit = _cache.get("dias_pub")
        if hit:
            return val
        rows = _query("SELECT aba FROM dias_publicados")
        dias = {r["aba"] for r in rows}
        _cache.set("dias_pub", dias, 10)
        return dias

    def publicar_dia(self, aba: str):
        _execute("INSERT INTO dias_publicados (aba) VALUES (%s) ON CONFLICT DO NOTHING", (aba,))
        _cache.clear("dias_pub")

    def despublicar_dia(self, aba: str):
        _execute("DELETE FROM dias_publicados WHERE aba = %s", (aba,))
        _cache.clear("dias_pub")

    # ── Lista de abas ─────────────────────────────────────────
    def carregar_lista_abas(self) -> list:
        val, hit = _cache.get("lista_abas")
        if hit:
            return val
        rows = _query("SELECT DISTINCT aba FROM escalas ORDER BY aba")
        abas = [r["aba"] for r in rows]
        _cache.set("lista_abas", abas, 60)
        return abas

    # ── Grupos de folga ───────────────────────────────────────
    def carregar_grupos_folga(self) -> dict:
        val, hit = _cache.get("grupos_folga")
        if hit:
            return val
        # Fallback para Sheets se não estiver no PG
        try:
            rows = _query("SELECT militar_id, grupo FROM grupos_folga")
            grupos: dict = {}
            for r in rows:
                g = r["grupo"]
                if g not in grupos:
                    grupos[g] = []
                grupos[g].append(r["militar_id"])
            result = {"grupos": grupos}
        except Exception:
            result = {"grupos": {}}
        _cache.set("grupos_folga", result, 3600)
        return result

    # ── Giros ────────────────────────────────────────────────
    def carregar_giros(self) -> pd.DataFrame:
        val, hit = _cache.get("giros")
        if hit:
            return val
        rows = _query("""
            SELECT id, nome, posto, giro FROM utilizadores
            WHERE giro IS NOT NULL AND giro != '' ORDER BY giro, nome
        """)
        df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        _cache.set("giros", df, 300)
        return df

    # ── Folgas ────────────────────────────────────────────────
    def carregar_folgas(self, ano: int) -> pd.DataFrame:
        # As folgas derivam da escala — calcular dinamicamente
        return pd.DataFrame()

    # ── Feriados ─────────────────────────────────────────────
    def carregar_feriados(self, ano: int) -> list:
        # Feriados fixos portugueses
        feriados_fixos = [
            date(ano, 1, 1), date(ano, 4, 25), date(ano, 5, 1),
            date(ano, 6, 10), date(ano, 8, 15), date(ano, 10, 5),
            date(ano, 11, 1), date(ano, 12, 1), date(ano, 12, 8), date(ano, 12, 25),
        ]
        return feriados_fixos

    # ── Serviços ──────────────────────────────────────────────
    def carregar_servicos(self) -> dict:
        val, hit = _cache.get("servicos")
        if hit:
            return val
        rows = _query("SELECT nome, tipo FROM servicos ORDER BY nome")
        result = {}
        for r in rows:
            t = r["tipo"] or "outros"
            if t not in result:
                result[t] = []
            result[t].append(r["nome"])
        _cache.set("servicos", result, 3600)
        return result

    # ── Listas ────────────────────────────────────────────────
    def carregar_listas(self) -> dict:
        """Carrega listas do PostgreSQL — devolve dict {coluna: [valores]}."""
        val, hit = _cache.get("listas")
        if hit:
            return val
        rows = _query("SELECT nome, tipo FROM servicos ORDER BY tipo, nome")
        result = {}
        for r in rows:
            col = r["tipo"].capitalize() if r["tipo"] else "outros"
            # Mapear tipo para nome de coluna original
            col_map = {
                "horário": "Horário", "radio": "Rádio", "rádio": "Rádio",
                "indicativo": "Indicativo", "viatura": "Viatura",
                "giro": "Giro", "serviço": "Serviço", "servico": "Serviço",
            }
            col_key = col_map.get(r["tipo"].lower().strip(), r["tipo"])
            if col_key not in result:
                result[col_key] = []
            result[col_key].append(r["nome"])
        _cache.set("listas", result, 3600)
        return result

    # ── Push Subscriptions ────────────────────────────────────
    def carregar_push_subscriptions(self, militar_id: str = None) -> pd.DataFrame:
        if militar_id:
            rows = _query("SELECT * FROM push_subscriptions WHERE militar_id = %s", (militar_id,))
        else:
            rows = _query("SELECT * FROM push_subscriptions")
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()

    def guardar_push_subscription(self, militar_id: str, endpoint: str, p256dh: str, auth: str, platform: str = "web"):
        _execute("""
            INSERT INTO push_subscriptions (militar_id, endpoint, p256dh, auth, platform)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (endpoint) DO UPDATE SET militar_id=EXCLUDED.militar_id, p256dh=EXCLUDED.p256dh, auth=EXCLUDED.auth
        """, (militar_id, endpoint, p256dh, auth, platform))

    def remover_push_subscription(self, endpoint: str):
        _execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (endpoint,))

    # ── Utilizadores — escrita ────────────────────────────────
    def actualizar_pin(self, militar_id: str, pin_hash: str):
        _execute("UPDATE utilizadores SET pin = %s WHERE id = %s", (pin_hash, militar_id))
        _cache.clear("utilizadores")

    # ── Ordem remunerados ─────────────────────────────────────
    def carregar_ordem_remunerados(self) -> pd.DataFrame:
        val, hit = _cache.get("ordem_rem")
        if hit:
            return val
        rows = _query("SELECT * FROM ordem_remunerados")
        df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        _cache.set("ordem_rem", df, 120)
        return df


    # ── Ordem Escala ─────────────────────────────────────────
    def carregar_ordem_escala(self, aba_dia: str) -> dict:
        """Carrega ordem_escala de um dia. Devolve dict {slot: [ids]}."""
        key = f"ordem_escala:{aba_dia}"
        val, hit = _cache.get(key)
        if hit:
            return val
        try:
            rows = _query("""
                SELECT slot, militar_id, posicao
                FROM ordem_escala
                WHERE aba = %s
                ORDER BY slot, posicao
            """, (aba_dia,))
            result = {}
            for r in rows:
                slot = r["slot"]
                if slot not in result:
                    result[slot] = []
                result[slot].append(r["militar_id"])
            _cache.set(key, result, 60)
            return result
        except Exception:
            return {}

    def guardar_ordem_escala(self, aba_dia: str, ordem: dict):
        """Guarda ordem_escala de um dia. ordem = {slot: [ids]}."""
        try:
            _execute("DELETE FROM ordem_escala WHERE aba = %s", (aba_dia,))
            rows = []
            for slot, ids in ordem.items():
                for pos, mid in enumerate(ids):
                    rows.append((aba_dia, slot, str(mid), pos))
            if rows:
                _execute_many("""
                    INSERT INTO ordem_escala (aba, slot, militar_id, posicao)
                    VALUES %s
                """, rows)
            _cache.clear(f"ordem_escala:{aba_dia}")
        except Exception as e:
            logger.warning(f"Erro ao guardar ordem_escala: {e}")
    def actualizar_ordem_remunerado(self, militar_id: str, tabela: str, horas: float, data_ultimo: datetime):
        col_total = f"total_ano_{tabela.lower()}"
        col_ultimo = f"ultimo_{tabela.lower()}"
        _execute(f"""
            INSERT INTO ordem_remunerados (militar_id, {col_total}, {col_ultimo})
            VALUES (%s, %s, %s)
            ON CONFLICT (militar_id) DO UPDATE SET
                {col_total} = ordem_remunerados.{col_total} + EXCLUDED.{col_total},
                {col_ultimo} = EXCLUDED.{col_ultimo}
        """, (militar_id, horas, data_ultimo))
        _cache.clear("ordem_rem")
