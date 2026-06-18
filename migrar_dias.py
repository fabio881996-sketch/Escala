"""
Migra dias de escala e ordem_escala em falta para o PostgreSQL.
Corre no Console do Railway: python3 migrar_dias.py
"""
import os, re
import psycopg2
from psycopg2.extras import execute_values
import gspread
from google.oauth2.service_account import Credentials

# ── Credenciais (igual ao migrate_sheets_to_pg.py original) ──
try:
    import streamlit as st
    creds_info = dict(st.secrets["gcp_service_account"])
    GSHEET_URL = st.secrets["gsheet_url"]
    DATABASE_URL = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
except Exception:
    import json
    creds_info = json.loads(os.environ["gcp_service_account"])
    GSHEET_URL = os.environ["gsheet_url"]
    DATABASE_URL = os.environ["DATABASE_URL"]

# ── O que migrar ──────────────────────────────────────────────
DIAS_ESCALA = ['27-06', '28-06']
DIAS_ORDEM  = ['26-06', '27-06', '28-06', '29-06']

# ── Ligar ao Google Sheets ────────────────────────────────────
print("A ligar ao Google Sheets...")
creds = Credentials.from_service_account_info(
    creds_info,
    scopes=['https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive']
)
client = gspread.authorize(creds)
sh = client.open_by_url(GSHEET_URL)
print(f"  Sheet: {sh.title}")

# ── Ligar ao PostgreSQL ───────────────────────────────────────
print("A ligar ao PostgreSQL...")
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
print("  Ligado!")

# ── Migrar dias de escala ─────────────────────────────────────
for dia in DIAS_ESCALA:
    try:
        ws = sh.worksheet(dia)
        vals = ws.get_all_values()
        if not vals or len(vals) < 2:
            print(f"  {dia}: vazio, ignorado")
            continue
        hdrs = [h.strip().lower() for h in vals[0]]
        cur.execute("DELETE FROM escalas WHERE aba=%s", (dia,))
        rows = []
        for row in vals[1:]:
            d = {hdrs[i]: (row[i].strip() if i < len(row) else '') for i in range(len(hdrs))}
            id_raw = d.get('id', d.get('militares', ''))
            if not id_raw or id_raw == 'nan':
                continue
            for mid in re.split(r'[;,]+', id_raw):
                mid = mid.strip()
                if not mid:
                    continue
                rows.append((
                    dia, mid,
                    d.get('servico', d.get('servico', '')),
                    d.get('horario', d.get('horario', '')),
                    d.get('indicativo', '') or None,
                    d.get('radio', d.get('radio', '')) or None,
                    d.get('viatura', '') or None,
                    d.get('giro', '') or None,
                    d.get('observacoes', d.get('observacoes', '')) or None,
                ))
        if rows:
            execute_values(cur, """
                INSERT INTO escalas (aba, id, servico, horario, indicativo, radio, viatura, giro, observacoes)
                VALUES %s ON CONFLICT DO NOTHING
            """, rows)
            conn.commit()
            print(f"  Escala {dia}: {len(rows)} linhas migradas")
        else:
            print(f"  Escala {dia}: sem linhas validas")
    except Exception as e:
        print(f"  ERRO escala {dia}: {e}")

# ── Migrar ordem_escala ───────────────────────────────────────
for dia in DIAS_ORDEM:
    try:
        ws = sh.worksheet(f'ordem_escala {dia}')
        vals = ws.get_all_values()
        if not vals or len(vals) < 2:
            print(f"  ordem_escala {dia}: vazio, ignorado")
            continue
        hdrs = [h.strip() for h in vals[0]]
        cur.execute("DELETE FROM ordem_escala WHERE aba=%s", (dia,))
        rows = []
        for ci, slot in enumerate(hdrs):
            if not slot or slot.lower() == 'nan':
                continue
            for pi, row in enumerate(vals[1:]):
                mid = row[ci].strip() if ci < len(row) else ''
                if not mid or mid.lower() == 'nan':
                    continue
                rows.append((dia, slot, mid, pi))
        if rows:
            execute_values(cur, """
                INSERT INTO ordem_escala (aba, slot, militar_id, posicao)
                VALUES %s ON CONFLICT DO NOTHING
            """, rows)
            conn.commit()
            print(f"  ordem_escala {dia}: {len(rows)} entradas migradas")
        else:
            print(f"  ordem_escala {dia}: sem dados")
    except Exception as e:
        print(f"  ERRO ordem_escala {dia}: {e}")

cur.close()
conn.close()
print("\nFeito!")
