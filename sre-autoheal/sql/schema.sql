-- schema.sql
-- Modelagem do banco do SRE Auto-Heal: frota de servidores/serviços,
-- catálogo de tipos de incidente e o histórico de incidentes e
-- ações de remediação automática tomadas sobre eles.

CREATE TABLE servidores (
    id_servidor   INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT NOT NULL UNIQUE,
    camada        TEXT NOT NULL,   -- Web, API, Banco de Dados, Fila, Cache
    criticidade   TEXT NOT NULL    -- Baixa, Média, Alta, Crítica
);

CREATE TABLE tipos_incidente (
    id_tipo                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                      TEXT NOT NULL UNIQUE,
    auto_remediavel           INTEGER NOT NULL,  -- 0 ou 1
    taxa_sucesso_automacao    REAL NOT NULL,     -- 0.0 a 1.0
    mttr_manual_minutos       INTEGER NOT NULL,  -- tempo médio de resolução SEM automação
    runbook                   TEXT               -- nome da ação executada quando auto-remediável
);

CREATE TABLE incidentes (
    id_incidente            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_servidor             INTEGER NOT NULL REFERENCES servidores(id_servidor),
    id_tipo                 INTEGER NOT NULL REFERENCES tipos_incidente(id_tipo),
    detectado_em            TEXT NOT NULL,
    resolvido_em            TEXT,
    resolvido_por           TEXT,     -- 'automacao', 'analista' ou NULL (ainda aberto)
    tentativas_automacao    INTEGER NOT NULL DEFAULT 0,
    tempo_resolucao_minutos REAL,
    status                   TEXT NOT NULL  -- 'Aberto', 'Em remediação', 'Resolvido', 'Escalado'
);

CREATE TABLE acoes_remediacao (
    id_acao       INTEGER PRIMARY KEY AUTOINCREMENT,
    id_incidente  INTEGER NOT NULL REFERENCES incidentes(id_incidente),
    executado_em  TEXT NOT NULL,
    runbook       TEXT NOT NULL,
    sucesso       INTEGER NOT NULL  -- 0 ou 1
);

CREATE INDEX idx_incidentes_servidor ON incidentes(id_servidor);
CREATE INDEX idx_incidentes_tipo ON incidentes(id_tipo);
CREATE INDEX idx_acoes_incidente ON acoes_remediacao(id_incidente);
