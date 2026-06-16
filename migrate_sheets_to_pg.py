"""
migrate_sheets_to_pg.py
Migra todos os dados do Google Sheets para PostgreSQL.
Corre uma vez — pode ser executado no Railway ou localmente com acesso ao Sheets.

Uso:
    DATABASE_URL=postgresql://... python3 migrate_sheets_to_pg.py
"""
import os
import sys
import re
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
log = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    sys.exit('❌ DATABASE_URL não definido')

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    sys.exit('❌ pip install psycopg2-binary')

# ── Ligar ao PostgreSQL ───────────────────────────────────────
log.info('A ligar ao PostgreSQL...')
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur = conn.cursor()
log.info('Ligado!')

# ── Aplicar schema ────────────────────────────────────────────
schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
if os.path.exists(schema_path):
    with open(schema_path) as f:
        cur.execute(f.read())
    conn.commit()
    log.info('Schema aplicado')

# ── Importar DataLoader do Railway ────────────────────────────
sys.path.insert(0, '/app')
try:
    from services.data_loader import DataLoader
    from core.database import GoogleSheetsClient
    loader = DataLoader(sheets_client=GoogleSheetsClient())
    log.info('DataLoader carregado')
except Exception as e:
    log.error('Erro ao carregar DataLoader: %s', e)
    sys.exit(1)

def safe(val):
    v = str(val).strip() if val is not None else ''
    return None if v in ('', 'nan', 'None') else v

# ── 1. Utilizadores ───────────────────────────────────────────
log.info('A migrar utilizadores...')
try:
    df = loader.carregar_usuarios()
    rows = []
    for _, r in df.iterrows():
        mid = safe(r.get('id'))
        if not mid: continue
        rows.append((
            mid, safe(r.get('nome')), safe(r.get('posto')),
            safe(r.get('nim')), safe(r.get('email')), safe(r.get('pin')),
            safe(r.get('giro')), safe(r.get('nascimento')),
        ))
    execute_values(cur, '''
        INSERT INTO utilizadores (id,nome,posto,nim,email,pin,giro,nascimento)
        VALUES %s ON CONFLICT (id) DO UPDATE SET
            nome=EXCLUDED.nome, posto=EXCLUDED.posto, nim=EXCLUDED.nim,
            email=EXCLUDED.email, pin=EXCLUDED.pin, giro=EXCLUDED.giro,
            nascimento=EXCLUDED.nascimento
    ''', rows)
    conn.commit()
    log.info('  %d utilizadores migrados', len(rows))
except Exception as e:
    log.error('  Erro utilizadores: %s', e)
    conn.rollback()

# ── 2. Dias publicados ────────────────────────────────────────
log.info('A migrar dias publicados...')
try:
    dias = loader.carregar_dias_publicados()
    if dias:
        execute_values(cur, '''
            INSERT INTO dias_publicados (aba) VALUES %s
            ON CONFLICT (aba) DO NOTHING
        ''', [(d,) for d in dias])
        conn.commit()
        log.info('  %d dias publicados migrados', len(dias))
except Exception as e:
    log.error('  Erro dias publicados: %s', e)
    conn.rollback()

# ── 3. Escalas ────────────────────────────────────────────────
log.info('A migrar escalas diárias...')
try:
    sh = GoogleSheetsClient().get_sheet()
    ws_list = sh.worksheets()
    abas_dia = [ws.title for ws in ws_list if re.match(r'^\d{2}-\d{2}$', ws.title)]
    log.info('  %d abas de escala encontradas', len(abas_dia))

    total_linhas = 0
    for aba in abas_dia:
        try:
            df = loader.carregar_escala(aba)
            if df.empty: continue
            rows = []
            for _, r in df.iterrows():
                mid = safe(r.get('id'))
                if not mid: continue
                rows.append((
                    aba, mid,
                    safe(r.get('serviço')), safe(r.get('horário')),
                    safe(r.get('viatura')), safe(r.get('rádio')),
                    safe(r.get('indicativo rádio')), safe(r.get('giro')),
                    safe(r.get('observações')),
                ))
            if rows:
                execute_values(cur, '''
                    INSERT INTO escalas (aba,militar_id,servico,horario,viatura,radio,indicativo,giro,observacoes)
                    VALUES %s
                ''', rows)
                total_linhas += len(rows)
        except Exception as e:
            log.warning('  Aba %s: %s', aba, e)
    conn.commit()
    log.info('  %d linhas de escala migradas', total_linhas)
except Exception as e:
    log.error('  Erro escalas: %s', e)
    conn.rollback()

# ── 4. Trocas ─────────────────────────────────────────────────
log.info('A migrar trocas...')
try:
    df = loader.carregar_trocas()
    rows = []
    for _, r in df.iterrows():
        rows.append((
            safe(r.get('data')), safe(r.get('id_origem')), safe(r.get('servico_origem')),
            safe(r.get('id_destino')), safe(r.get('servico_destino')),
            safe(r.get('status')) or 'Pendente_Militar',
            safe(r.get('observacoes')), safe(r.get('data_pedido')), safe(r.get('data_aceitacao')),
        ))
    if rows:
        execute_values(cur, '''
            INSERT INTO trocas (data,id_origem,servico_origem,id_destino,servico_destino,status,observacoes,data_pedido,data_aceitacao)
            VALUES %s
        ''', rows)
        conn.commit()
    log.info('  %d trocas migradas', len(rows))
except Exception as e:
    log.error('  Erro trocas: %s', e)
    conn.rollback()

# ── 5. Férias ─────────────────────────────────────────────────
log.info('A migrar férias...')
try:
    ano = datetime.now().year
    for a in [ano-1, ano, ano+1]:
        try:
            df = loader.carregar_ferias(a)
            if df.empty: continue
            rows = []
            for _, r in df.iterrows():
                mid = safe(r.get('id'))
                if not mid: continue
                rows.append((mid, a, safe(r.get('inicio')), safe(r.get('fim')), safe(r.get('dias')), safe(r.get('obs'))))
            if rows:
                execute_values(cur, '''
                    INSERT INTO ferias (militar_id,ano,inicio,fim,dias,obs) VALUES %s
                ''', rows)
                conn.commit()
                log.info('  %d férias %d migradas', len(rows), a)
        except Exception:
            pass
except Exception as e:
    log.error('  Erro férias: %s', e)
    conn.rollback()

# ── 6. Dispensas ──────────────────────────────────────────────
log.info('A migrar dispensas...')
try:
    df = loader.carregar_licencas()
    rows = []
    from datetime import datetime as _dt
    hoje = _dt.now()
    for _, r in df.iterrows():
        mid = safe(r.get('id'))
        if not mid: continue
        fim_str = safe(r.get('fim'))
        try:
            activa = not fim_str or _dt.strptime(fim_str, '%d/%m/%Y') >= hoje
        except Exception:
            activa = True
        rows.append((mid, safe(r.get('tipo')), safe(r.get('inicio')), fim_str, safe(r.get('observacoes')), activa))
    if rows:
        execute_values(cur, '''
            INSERT INTO dispensas (militar_id,tipo,inicio,fim,observacoes,activa) VALUES %s
        ''', rows)
        conn.commit()
    log.info('  %d dispensas migradas', len(rows))
except Exception as e:
    log.error('  Erro dispensas: %s', e)
    conn.rollback()

# ── 7. Ordem Remunerados ──────────────────────────────────────
log.info('A migrar ordem remunerados...')
try:
    df = loader.carregar_ordem_remunerados()
    rows = []
    for _, r in df.iterrows():
        mid = safe(r.get('id'))
        if not mid: continue
        def _bool(v): return str(v).lower().strip() in ('true','1','sim','yes')
        rows.append((
            mid, _bool(r.get('disponivel')), _bool(r.get('voluntario')),
            _bool(r.get('folga')), _bool(r.get('prescinde_descanso')),
        ))
    if rows:
        execute_values(cur, '''
            INSERT INTO ordem_remunerados (militar_id,disponivel,voluntario,folga,prescinde_descanso)
            VALUES %s ON CONFLICT (militar_id) DO UPDATE SET
                disponivel=EXCLUDED.disponivel, voluntario=EXCLUDED.voluntario,
                folga=EXCLUDED.folga, prescinde_descanso=EXCLUDED.prescinde_descanso
        ''', rows)
        conn.commit()
    log.info('  %d militares ordem_remunerados migrados', len(rows))
except Exception as e:
    log.error('  Erro ordem_remunerados: %s', e)
    conn.rollback()

# ── 8. Push Subscriptions ─────────────────────────────────────
log.info('A migrar push subscriptions...')
try:
    df = loader.carregar_push_subscriptions() if hasattr(loader, 'carregar_push_subscriptions') else None
    if df is not None and not df.empty:
        rows = []
        for _, r in df.iterrows():
            rows.append((safe(r.get('id')), safe(r.get('endpoint')), safe(r.get('p256dh')), safe(r.get('auth')), safe(r.get('platform','web'))))
        execute_values(cur, '''
            INSERT INTO push_subscriptions (militar_id,endpoint,p256dh,auth,platform)
            VALUES %s ON CONFLICT (endpoint) DO NOTHING
        ''', rows)
        conn.commit()
        log.info('  %d subscriptions migradas', len(rows))
except Exception as e:
    log.warning('  Push subscriptions: %s', e)

# ── Fim ───────────────────────────────────────────────────────
cur.close()
conn.close()
log.info('✅ Migração completa!')
