"""
GNR – Portal de Escalas
=======================
Aplicação principal Streamlit.  Integra autenticação por PIN, navegação
lateral e roteamento para todas as páginas modulares.

Autor: Equipa GNR / Refactoring
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Any, Set

# ── Módulos internos ──
from config.settings import (
    ADMINS,
    SESSION_LOGGED_IN,
    SESSION_USER_ID,
    SESSION_USER_NAME,
    SESSION_USER_EMAIL,
    SESSION_IS_ADMIN,
    SESSION_PIN_ATTEMPTS,
    SESSION_PIN_BLOCKED_UNTIL,
    SESSION_PIN_BUFFER,
    SESSION_PIN_ERROR,
    SESSION_LOGIN_MODE,
    LOGIN_MAX_ATTEMPTS,
    LOGIN_BLOCK_SECONDS,
)
from core.auth import hash_pin, verify_pin, migrate_legacy_pin
from core.database import GoogleSheetsClient, get_sheet, load_data
from core.utils import norm
from models.usuario import Usuario
from services.data_loader import DataLoader
from ui.components.styles import apply_custom_css

# Render functions (via ui/pages/__init__)
from ui.pages import (
    PAGE_ROUTES,
    render_dashboard,
    render_minha_escala,
    render_trocas,
    render_validar_trocas,
    render_trocas_validadas,
    render_remunerados,
    render_ferias,
    render_gerar_escala,
    render_escala_geral,
    render_gestao_usuarios,
    render_dispensas,
    render_publicar_escala,
    render_alertas,
    render_giros,
    render_efetivo,
)


# ====================================================================
# 1. PAGE CONFIG
# ====================================================================
st.set_page_config(
    page_title="GNR - Portal de Escalas",
    page_icon="🚓",
    layout="wide",
    initial_sidebar_state=st.session_state.get("sidebar_state", "expanded"),
)


# ====================================================================
# 2. ESTILOS CSS
# ====================================================================
apply_custom_css()


# ====================================================================
# 3. INICIALIZAÇÃO DO SESSION STATE
# ====================================================================
_DEFAULT_STATE: dict[str, Any] = {
    SESSION_LOGGED_IN:        False,
    SESSION_LOGIN_MODE:       "pin",
    SESSION_PIN_BUFFER:       "",
    SESSION_PIN_ERROR:        False,
    SESSION_PIN_ATTEMPTS:     0,
    SESSION_PIN_BLOCKED_UNTIL: None,
}

for key, default in _DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ====================================================================
# 4. FUNÇÕES AUXILIARES
# ====================================================================

@st.cache_data(ttl=300)
def _load_utilizadores() -> pd.DataFrame:
    """Carrega utilizadores com cache de 5 min e retry."""
    import time
    for tentativa in range(3):
        try:
            sh = get_sheet()
            if sh is None:
                return pd.DataFrame()
            vals = sh.worksheet("utilizadores").get_all_values()
            if not vals or len(vals) < 2:
                return pd.DataFrame()
            hdrs = [str(h).strip().lower() for h in vals[0]]
            rows = []
            for row in vals[1:]:
                row_ext = list(row) + [""] * (len(hdrs) - len(row))
                rows.append({hdrs[i]: str(row_ext[i]).strip() for i in range(len(hdrs))})
            return pd.DataFrame(rows).fillna("")
        except Exception:
            if tentativa < 2:
                time.sleep(1)
    return pd.DataFrame()


def _fazer_login(user_row: pd.Series, u_email: str) -> None:
    """Autentica o utilizador e popula o session_state."""
    u_id = str(user_row["id"])
    if (
        "posto" in user_row.index
        and "nome" in user_row.index
        and str(user_row.get("posto", "")).strip()
    ):
        u_nome = f"{user_row['posto']} {user_row['nome']}"
    else:
        df_u = _load_utilizadores()
        row_sheet = df_u[df_u["id"].astype(str).str.strip() == u_id]
        u_nome = (
            f"{row_sheet.iloc[0]['posto']} {row_sheet.iloc[0]['nome']}"
            if not row_sheet.empty
            else u_email
        )
    st.session_state.update(
        {
            SESSION_LOGGED_IN: True,
            SESSION_USER_ID: u_id,
            SESSION_USER_NAME: u_nome,
            SESSION_USER_EMAIL: u_email,
            SESSION_IS_ADMIN: u_email in ADMINS,
            SESSION_PIN_ATTEMPTS: 0,
            SESSION_PIN_BLOCKED_UNTIL: None,
            SESSION_PIN_BUFFER: "",
            SESSION_PIN_ERROR: False,
        }
    )


# ====================================================================
# 5. ECRÃ DE LOGIN (PIN KEYPAD)
# ====================================================================

def _render_login() -> None:
    """Renderiza o ecrã de login com teclado numérico PIN."""

    buf: str = st.session_state[SESSION_PIN_BUFFER]
    err: bool = st.session_state[SESSION_PIN_ERROR]
    n = len(buf)

    bloqueado = (
        st.session_state[SESSION_PIN_BLOCKED_UNTIL]
        and datetime.now() < st.session_state[SESSION_PIN_BLOCKED_UNTIL]
    )
    err_msg = "PIN incorreto. Tenta novamente." if err else ""
    if bloqueado:
        resto = int(
            (st.session_state[SESSION_PIN_BLOCKED_UNTIL] - datetime.now()).total_seconds()
        )
        err_msg = f"🔒 Bloqueado. Aguarda {resto}s."

    # ── CSS específico do login ──
    st.markdown(
        """
        <style>
        .stApp { background:#FFFFFF !important; }
        header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stStatusWidget"], #MainMenu { display:none !important; }
        .block-container { padding:0 !important; max-width:100% !important; }
        div[data-testid="stButton"]>button {
            width:76px !important; height:76px !important; border-radius:50% !important;
            background:#F1F5F9 !important; color:#0F172A !important;
            font-size:24px !important; font-weight:300 !important;
            border:none !important; box-shadow:0 2px 8px rgba(0,0,0,0.08) !important;
            padding:0 !important; margin:0 auto !important;
            transition:transform 0.08s ease, background 0.08s ease !important; }
        div[data-testid="stButton"]>button:hover {
            background:#E2E8F0 !important; transform:scale(0.95) !important; }
        div[data-testid="stButton"]>button:active {
            background:#CBD5E1 !important; transform:scale(0.90) !important; }
        [data-testid="stHorizontalBlock"] {
            display:flex !important; flex-direction:row !important;
            justify-content:center !important; gap:14px !important; flex-wrap:nowrap !important; }
        [data-testid="stHorizontalBlock"]>[data-testid="stColumn"] {
            flex:0 0 76px !important; min-width:76px !important;
            max-width:76px !important; width:76px !important; padding:0 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Header + dots ──
    dots_html = '<div style="display:flex;gap:16px;justify-content:center;margin-bottom:10px;">'
    for i in range(4):
        if err:
            style = "background:#EF4444;border:2px solid #EF4444;"
        elif i < n:
            style = "background:#0F172A;border:2px solid #0F172A;"
        else:
            style = "background:transparent;border:2px solid #CBD5E1;"
        dots_html += (
            f'<div style="width:14px;height:14px;border-radius:50%;{style}'
            f'transition:all 0.15s ease;"></div>'
        )
    dots_html += "</div>"

    st.markdown(
        f"""
        <div style="display:flex;flex-direction:column;align-items:center;padding:48px 0 24px 0;">
            <div style="font-size:2.8rem;margin-bottom:6px;
                 filter:drop-shadow(0 4px 8px rgba(30,58,138,0.25))">🚓</div>
            <div style="font-size:1.4rem;font-weight:800;color:#1A2B4A;
                 letter-spacing:-0.02em;margin-bottom:2px">Portal de Escalas</div>
            <div style="font-size:0.72rem;font-weight:600;color:#2563EB;
                 letter-spacing:0.04em;text-transform:uppercase;margin-bottom:2px">
                Guarda Nacional Republicana</div>
            <div style="font-size:0.68rem;color:#64748B;margin-bottom:28px">
                Posto Territorial de Famalicão</div>
            {dots_html}
            <div style="min-height:20px;font-size:13px;font-weight:600;color:#EF4444;
                 text-align:center;margin-bottom:16px;">{err_msg}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Teclado numérico ──
    rows = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["_", "0", "⌫"]]
    for row in rows:
        c1, c2, c3 = st.columns(3)
        for col, val in zip([c1, c2, c3], row):
            with col:
                if val == "_":
                    st.markdown("<div style='height:76px'></div>", unsafe_allow_html=True)
                elif st.button(val, key=f"pk_{val}"):
                    if not bloqueado:
                        if val == "⌫":
                            st.session_state[SESSION_PIN_BUFFER] = buf[:-1]
                            st.session_state[SESSION_PIN_ERROR] = False
                        else:
                            new = buf + val
                            st.session_state[SESSION_PIN_ERROR] = False
                            if len(new) == 4:
                                _verificar_pin(new)
                            else:
                                st.session_state[SESSION_PIN_BUFFER] = new
                    st.rerun()


def _verificar_pin(pin: str) -> None:
    """Verifica o PIN introduzido contra a lista de utilizadores."""
    df_u = _load_utilizadores()
    if df_u.empty or "pin" not in df_u.columns:
        st.session_state[SESSION_PIN_ERROR] = True
        st.session_state[SESSION_PIN_BUFFER] = ""
        return

    user = None
    for _, row_u in df_u.iterrows():
        if verify_pin(pin, str(row_u.get("pin", ""))):
            user = row_u
            break

    if user is not None:
        # Migrar PIN para hash se ainda for texto simples
        pin_guardado = str(user.get("pin", "")).strip()
        if ":" not in pin_guardado or len(pin_guardado) <= 10:
            migrate_legacy_pin(str(user.get("email", "")), pin, GoogleSheetsClient())
        _fazer_login(user, user["email"])
        st.rerun()
    else:
        st.session_state[SESSION_PIN_ATTEMPTS] += 1
        if st.session_state[SESSION_PIN_ATTEMPTS] >= LOGIN_MAX_ATTEMPTS:
            st.session_state[SESSION_PIN_BLOCKED_UNTIL] = datetime.now() + timedelta(
                seconds=LOGIN_BLOCK_SECONDS
            )
            st.session_state[SESSION_PIN_ATTEMPTS] = 0
        st.session_state[SESSION_PIN_ERROR] = True
        st.session_state[SESSION_PIN_BUFFER] = ""


# ====================================================================
# 6. HELPER – nome_militar (compatibilidade)
# ====================================================================

def _get_nome_militar(df_util: pd.DataFrame, mid: str) -> str:
    """Devolve nome curto de um militar a partir do DataFrame de utilizadores."""
    if df_util.empty:
        return str(mid)
    row = df_util[df_util["id"].astype(str).str.strip() == str(mid).strip()]
    if row.empty:
        return str(mid)
    r = row.iloc[0]
    return f"{r.get('posto', '')} {r.get('nome', '')}".strip() or str(mid)


# ====================================================================
# 7. APP PRINCIPAL (pós-login)
# ====================================================================

def _render_app() -> None:
    """Renderiza a aplicação principal após autenticação."""

    # ── Expiração de sessão (4 horas) ──
    if "login_time" not in st.session_state:
        st.session_state["login_time"] = datetime.now()
    elif (datetime.now() - st.session_state["login_time"]).total_seconds() > 4 * 3600:
        st.session_state[SESSION_LOGGED_IN] = False
        st.warning("⏱️ Sessão expirada. Por favor volta a fazer login.")
        st.stop()

    # ── Dados globais ──
    try:
        sheets_client = GoogleSheetsClient()
        data_loader = DataLoader(sheets_client=sheets_client)
    except Exception as exc:
        st.error(f"❌ Erro ao inicializar serviços: {exc}")
        st.stop()

    df_util = _load_utilizadores()
    ano_atual = datetime.now().year

    try:
        df_trocas = data_loader.carregar_trocas()
    except Exception:
        df_trocas = pd.DataFrame()

    try:
        df_ferias = data_loader.carregar_ferias(ano_atual)
    except Exception:
        df_ferias = pd.DataFrame()

    try:
        feriados = data_loader.carregar_feriados(ano_atual)
    except Exception:
        feriados = []

    try:
        df_folgas = data_loader.carregar_folgas(ano_atual)
    except Exception:
        df_folgas = pd.DataFrame()

    try:
        grupos_folga = data_loader.carregar_grupos_folga()
    except Exception:
        grupos_folga = {}

    try:
        df_licencas = data_loader.carregar_licencas()
    except Exception:
        df_licencas = pd.DataFrame()

    try:
        dias_publicados = set()
        sh = get_sheet()
        if sh:
            ws = sh.worksheet("escala_publicada")
            vals = ws.col_values(1)
            dias_publicados = {str(v).strip() for v in vals if str(v).strip() and str(v).strip() != "data"}
    except Exception:
        dias_publicados = set()

    # ── Info do utilizador ──
    u_id: str = str(st.session_state[SESSION_USER_ID])
    u_nome: str = st.session_state[SESSION_USER_NAME]
    is_admin: bool = st.session_state.get(SESSION_IS_ADMIN, False)

    # Construir objecto Usuario
    u_row = df_util[df_util["id"].astype(str).str.strip() == u_id]
    if not u_row.empty:
        usuario = Usuario.from_row(u_row.iloc[0].to_dict())
    else:
        usuario = Usuario(
            id=u_id,
            nome=u_nome,
            email=st.session_state.get(SESSION_USER_EMAIL, ""),
            is_admin=is_admin,
        )

    feriados_set: Set = set(feriados) if isinstance(feriados, list) else feriados

    # ── Sidebar ──
    with st.sidebar:
        # Badge institucional
        st.markdown(
            """
            <div style='text-align:center;padding:12px 4px 16px 4px;margin-bottom:14px;
                 background:linear-gradient(180deg,rgba(30,58,138,0.4) 0%,rgba(15,23,42,0) 100%);
                 border-radius:10px'>
                <div style='font-size:2rem;line-height:1;margin-bottom:8px;
                     filter:drop-shadow(0 2px 6px rgba(147,197,253,0.4))'>🚓</div>
                <div style='font-size:0.85rem;font-weight:800;color:#F1F5F9;
                     letter-spacing:0.08em;text-transform:uppercase;line-height:1.2'>
                    Portal de Escalas</div>
                <div style='width:40px;height:2px;
                     background:linear-gradient(90deg,transparent,#3B82F6,transparent);
                     margin:6px auto 5px auto;border-radius:2px'></div>
                <div style='font-size:0.72rem;color:#93C5FD;font-weight:600;
                     letter-spacing:0.04em'>Guarda Nacional Republicana</div>
                <div style='font-size:0.67rem;color:#64748B;margin-top:3px;
                     letter-spacing:0.02em'>Posto Territorial de Famalicão</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        role_label = "⭐ Administrador" if is_admin else "👮 Militar"
        st.markdown(
            f"""
            <div class="user-badge">
                <div class="nome">👤 {u_nome}</div>
                <div class="id">ID: {u_id}</div>
                <div class="role">{role_label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Contador de pedidos pendentes
        if not df_trocas.empty and "status" in df_trocas.columns:
            n_pendentes = len(
                df_trocas[
                    (df_trocas["status"] == "Pendente_Militar")
                    & (df_trocas["id_destino"].astype(str) == u_id)
                ]
            )
            n_admin = (
                len(df_trocas[df_trocas["status"] == "Pendente_Admin"])
                if is_admin
                else 0
            )
            if n_pendentes > 0:
                st.warning(f"🔔 {n_pendentes} pedido(s) de troca por responder")
            if n_admin > 0:
                st.warning(f"⚖️ {n_admin} troca(s) aguardam validação")

        st.markdown("---")

        # ── Menu ──
        menu_opt = [
            "📅 Minha Escala",
            "🔄 Trocas",
            "🔍 Escala Geral",
            "🔄 Giros",
            "👥 Efetivo",
        ]
        if is_admin:
            menu_opt += [
                "",
                "🏖️ Férias",
                "🏥 Dispensas",
                "⚖️ Validar Trocas",
                "📜 Trocas Validadas",
                "🚨 Alertas",
                "⚙️ Gerar Escala",
                "📢 Publicar Escala",
                "👤 Gerir Utilizadores",
            ]

        st.markdown(
            "<p style='font-size:0.75rem;letter-spacing:0.08em;color:#94A3B8;"
            "margin:0 0 4px 0;'>MENU</p>",
            unsafe_allow_html=True,
        )

        menu = st.radio(
            "MENU",
            menu_opt,
            label_visibility="collapsed",
            format_func=lambda x: "──────────" if x == "" else x,
        )

        st.markdown("---")
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state[SESSION_LOGGED_IN] = False
            st.rerun()

    # ── Fechar sidebar no mobile após seleção ──
    if "menu_anterior" not in st.session_state:
        st.session_state["menu_anterior"] = menu
    elif st.session_state["menu_anterior"] != menu:
        st.session_state["menu_anterior"] = menu
        st.session_state["sidebar_state"] = "collapsed"
        st.rerun()

    # ── Banner de notificações ──
    if not df_trocas.empty and "status" in df_trocas.columns:
        n_pend = len(
            df_trocas[
                (df_trocas["status"] == "Pendente_Militar")
                & (df_trocas["id_destino"].astype(str) == u_id)
            ]
        )
        if n_pend > 0:
            st.warning(
                f"🔔 Tens **{n_pend} pedido(s) de troca** por responder! "
                "Vai a **📥 Pedidos Recebidos**."
            )

    # ── Roteamento de páginas ──
    _route_page(
        menu=menu,
        usuario=usuario,
        data_loader=data_loader,
        df_util=df_util,
        df_trocas=df_trocas,
        df_ferias=df_ferias,
        df_folgas=df_folgas,
        df_licencas=df_licencas,
        feriados=feriados_set,
        grupos_folga=grupos_folga,
        dias_publicados=dias_publicados,
        is_admin=is_admin,
    )


def _route_page(
    *,
    menu: str,
    usuario: Usuario,
    data_loader: DataLoader,
    df_util: pd.DataFrame,
    df_trocas: pd.DataFrame,
    df_ferias: pd.DataFrame,
    df_folgas: pd.DataFrame,
    df_licencas: pd.DataFrame,
    feriados: Set,
    grupos_folga: Any,
    dias_publicados: Set[str],
    is_admin: bool,
) -> None:
    """Encaminha para a render function correcta com base na selecção do menu."""

    try:
        if menu == "📅 Minha Escala":
            render_minha_escala(usuario)

        elif menu == "🔄 Trocas":
            render_trocas(usuario)

        elif menu == "🔍 Escala Geral":
            render_escala_geral(
                usuario=usuario,
                data_loader=data_loader,
                df_util=df_util,
                df_trocas=df_trocas,
                df_ferias=df_ferias,
                feriados=feriados,
                dias_publicados=dias_publicados,
                is_admin=is_admin,
            )

        elif menu == "🔄 Giros":
            render_giros(data_loader)

        elif menu == "👥 Efetivo":
            render_efetivo(df_util)

        elif menu == "🏖️ Férias":
            render_ferias(
                usuario=usuario,
                data_loader=data_loader,
                df_util=df_util,
                is_admin=is_admin,
            )

        elif menu == "🏥 Dispensas":
            render_dispensas(
                usuario=usuario,
                data_loader=data_loader,
                df_util=df_util,
                is_admin=is_admin,
            )

        elif menu == "⚖️ Validar Trocas":
            render_validar_trocas(usuario)

        elif menu == "📜 Trocas Validadas":
            render_trocas_validadas(usuario)

        elif menu == "🚨 Alertas":
            render_alertas(
                usuario=usuario,
                data_loader=data_loader,
                df_util=df_util,
                df_ferias=df_ferias,
                feriados=feriados,
                is_admin=is_admin,
            )

        elif menu == "⚙️ Gerar Escala":
            render_gerar_escala(
                usuario=usuario,
                data_loader=data_loader,
                df_util=df_util,
                df_trocas=df_trocas,
                df_ferias=df_ferias,
                df_folgas=df_folgas,
                df_licencas=df_licencas,
                feriados=feriados,
                grupos_folga=grupos_folga,
                is_admin=is_admin,
            )

        elif menu == "📢 Publicar Escala":
            render_publicar_escala(
                usuario=usuario,
                data_loader=data_loader,
                is_admin=is_admin,
            )

        elif menu == "👤 Gerir Utilizadores":
            render_gestao_usuarios(
                usuario=usuario,
                df_util=df_util,
                is_admin=is_admin,
            )

        elif menu == "" or menu == "──────────":
            # Separador de menu — não faz nada
            pass

        else:
            st.info(f"Página «{menu}» em construção.")

    except Exception as exc:
        st.error(f"❌ Erro ao carregar a página: {exc}")
        if is_admin:
            import traceback
            st.expander("Detalhes técnicos").code(traceback.format_exc())


# ====================================================================
# 8. ENTRYPOINT
# ====================================================================

if not st.session_state[SESSION_LOGGED_IN]:
    _render_login()
else:
    _render_app()
