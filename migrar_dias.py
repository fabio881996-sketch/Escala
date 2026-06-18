"""
Corre localmente: py migrar_dias.py
Precisa de: gcp_service_account.json na mesma pasta
"""
import psycopg2, re, gspread
from google.oauth2.service_account import Credentials
from psycopg2.extras import execute_values

# ── Configura aqui ────────────────────────────────────────────
DATABASE_URL = "COLA_AQUI_O_DATABASE_URL_DO_RAILWAY"
GSHEET_URL   = "https://docs.google.com/spreadsheets/d/1y40O14e-pZRFn92Dyn3JkE5gshWZl7XOwVvlP1uBazg/edit"
CREDS_FILE   = "gcp_service_account.json"

DIAS_ESCALA   = ["27-06", "28-06"]
DIAS_ORDEM    = ["26-06", "27-06", "28-06", "29-06"]
# ─────────────────────────────────────────────────────────────

creds = Credentials.from_service_account_file(CREDS_FILE, scopes=[
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
])
client = gspread.authorize(creds)
sh = client.open_by_url(GSHEET_URL)
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# ── Dias de escala ────────────────────────────────────────────
for dia in DIAS_ESCALA:
    try:
        ws = sh.worksheet(dia)
    except Exception:
        print(f"Aba '{dia}' não encontrada na Sheet")
        continue
    vals = ws.get_all_values()
    if not vals or len(vals) < 2:
        print(f"{dia}: vazio")
        continue
    hdrs = [h.strip().lower() for h in vals[0]]
    cur.execute("DELETE FROM escalas WHERE aba=%s", (dia,))
    rows = []
    for row in vals[1:]:
        d = {hdrs[i]: (row[i].strip() if i < len(row) else '') for i in range(len(hdrs))}
        id_raw = d.get('id', d.get('militares', ''))
        if not id_raw or id_raw == 'nan': continue
        for mid in re.split(r'[;,]+', id_raw):
            mid = mid.strip()
            if not mid: continue
            rows.append((
                dia, mid,
                d.get('serviço', d.get('servico', '')),
                d.get('horário', d.get('horario', '')),
                d.get('indicativo', '') or None,
                d.get('rádio', d.get('radio', '')) or None,
                d.get('viatura', '') or None,
                d.get('giro', '') or None,
                d.get('observações', d.get('observacoes', '')) or None,
            ))
    if rows:
        execute_values(cur, """
            INSERT INTO escalas (aba, id, servico, horario, indicativo, radio, viatura, giro, observacoes)
            VALUES %s ON CONFLICT DO NOTHING
        """, rows)
        conn.commit()
        print(f"Escala {dia}: {len(rows)} linhas inseridas")
    else:
        print(f"Escala {dia}: sem dados")

# ── Ordem escala ──────────────────────────────────────────────
for dia in DIAS_ORDEM:
    try:
        ws = sh.worksheet(f"ordem_escala {dia}")
    except Exception:
        print(f"Aba 'ordem_escala {dia}' não encontrada na Sheet")
        continue
    vals = ws.get_all_values()
    if not vals or len(vals) < 2:
        print(f"ordem_escala {dia}: vazio")
        continue
    hdrs = [h.strip() for h in vals[0]]
    cur.execute("DELETE FROM ordem_escala WHERE aba=%s", (dia,))
    rows = []
    for ci, slot in enumerate(hdrs):
        if not slot or slot.lower() == 'nan': continue
        for pi, row in enumerate(vals[1:]):
            mid = row[ci].strip() if ci < len(row) else ''
            if not mid or mid.lower() == 'nan': continue
            rows.append((dia, slot, mid, pi))
    if rows:
        execute_values(cur, """
            INSERT INTO ordem_escala (aba, slot, militar_id, posicao)
            VALUES %s ON CONFLICT DO NOTHING
        """, rows)
        conn.commit()
        print(f"ordem_escala {dia}: {len(rows)} entradas inseridas")
    else:
        print(f"ordem_escala {dia}: sem dados")

cur.close()
conn.close()
print("Feito!")
