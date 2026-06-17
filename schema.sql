-- Portal de Escalas GNR — Schema PostgreSQL
-- Criado para migração do Google Sheets

-- Extensões
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Utilizadores ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS utilizadores (
    id          TEXT PRIMARY KEY,
    nome        TEXT NOT NULL,
    posto       TEXT,
    nim         TEXT,
    email       TEXT,
    pin         TEXT,
    giro        TEXT,
    nascimento  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Escalas (uma linha por entrada) ───────────────────────────
CREATE TABLE IF NOT EXISTS escalas (
    id          SERIAL PRIMARY KEY,
    aba         TEXT NOT NULL,          -- ex: "16-06"
    militar_id  TEXT NOT NULL,          -- pode ser "797;1076" para multi
    servico     TEXT,
    horario     TEXT,
    viatura     TEXT,
    radio       TEXT,
    indicativo  TEXT,
    giro        TEXT,
    observacoes TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_escalas_aba ON escalas(aba);
CREATE INDEX IF NOT EXISTS idx_escalas_militar ON escalas(militar_id);

-- ── Dias publicados ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dias_publicados (
    aba         TEXT PRIMARY KEY,       -- ex: "16-06"
    publicado_em TIMESTAMPTZ DEFAULT NOW()
);

-- ── Trocas ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trocas (
    id              SERIAL PRIMARY KEY,
    data            TEXT NOT NULL,      -- DD/MM/YYYY
    id_origem       TEXT NOT NULL,
    servico_origem  TEXT,
    id_destino      TEXT NOT NULL,
    servico_destino TEXT,
    status          TEXT DEFAULT 'Pendente_Militar',
    observacoes     TEXT,
    data_pedido     TEXT,
    data_aceitacao  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trocas_data ON trocas(data);
CREATE INDEX IF NOT EXISTS idx_trocas_status ON trocas(status);

-- ── Férias ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ferias (
    id          SERIAL PRIMARY KEY,
    militar_id  TEXT NOT NULL,
    ano         INTEGER NOT NULL,
    inicio      TEXT,
    fim         TEXT,
    dias        INTEGER,
    obs         TEXT
);
CREATE INDEX IF NOT EXISTS idx_ferias_militar ON ferias(militar_id);
CREATE INDEX IF NOT EXISTS idx_ferias_ano ON ferias(ano);

-- ── Licenças/Dispensas ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dispensas (
    id          SERIAL PRIMARY KEY,
    militar_id  TEXT NOT NULL,
    tipo        TEXT NOT NULL,
    inicio      TEXT,
    fim         TEXT,
    observacoes TEXT,
    activa      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dispensas_militar ON dispensas(militar_id);
CREATE INDEX IF NOT EXISTS idx_dispensas_activa ON dispensas(activa);

-- ── Ordem Remunerados ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ordem_remunerados (
    militar_id          TEXT PRIMARY KEY,
    disponivel          BOOLEAN DEFAULT TRUE,
    voluntario          BOOLEAN DEFAULT FALSE,
    folga               BOOLEAN DEFAULT FALSE,
    prescinde_descanso  BOOLEAN DEFAULT FALSE,
    total_ano_a_semana  INTEGER DEFAULT 0,
    total_ano_a_fds     INTEGER DEFAULT 0,
    total_ano_b         INTEGER DEFAULT 0,
    ultimo_a_semana     TIMESTAMPTZ,
    ultimo_a_fds        TIMESTAMPTZ,
    ultimo_b            TIMESTAMPTZ
);

-- ── Grupos de folga ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS grupos_folga (
    militar_id  TEXT PRIMARY KEY,
    grupo       TEXT NOT NULL
);

-- ── Push subscriptions ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id          SERIAL PRIMARY KEY,
    militar_id  TEXT NOT NULL,
    endpoint    TEXT NOT NULL UNIQUE,
    p256dh      TEXT,
    auth        TEXT,
    platform    TEXT DEFAULT 'web',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_push_militar ON push_subscriptions(militar_id);

-- ── Serviços (lista de serviços possíveis) ────────────────────
CREATE TABLE IF NOT EXISTS servicos (
    id      SERIAL PRIMARY KEY,
    nome    TEXT NOT NULL UNIQUE,
    tipo    TEXT   -- 'patrulha', 'atendimento', 'adm', 'ausencia', etc.
);

-- ── Ordem Escala ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ordem_escala (
    id          SERIAL PRIMARY KEY,
    aba         TEXT NOT NULL,
    slot        TEXT NOT NULL,
    militar_id  TEXT NOT NULL,
    posicao     INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ordem_escala_unique ON ordem_escala(aba, slot, militar_id);
CREATE INDEX IF NOT EXISTS idx_ordem_escala_aba ON ordem_escala(aba);

COMMENT ON TABLE escalas IS 'Uma linha por entrada na escala diária. militar_id pode conter múltiplos IDs separados por ;';
COMMENT ON TABLE dias_publicados IS 'Dias visíveis para os militares na app';
