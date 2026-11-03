-- queries_analise.sql
-- Queries de análise sobre o histórico de incidentes e remediação
-- automática do SRE Auto-Heal.

-- 1) Taxa de auto-resolução geral (só considerando incidentes já resolvidos)
SELECT
    ROUND(100.0 * SUM(CASE WHEN resolvido_por = 'automacao' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_resolvido_por_automacao,
    COUNT(*) AS total_resolvidos
FROM incidentes
WHERE status = 'Resolvido';

-- 2) MTTR (tempo médio de resolução) comparando automação vs analista
SELECT
    resolvido_por,
    ROUND(AVG(tempo_resolucao_minutos), 1) AS mttr_minutos,
    COUNT(*) AS total
FROM incidentes
WHERE status = 'Resolvido'
GROUP BY resolvido_por;

-- 3) Volume de incidentes por dia (últimos 30 dias)
SELECT
    DATE(detectado_em) AS dia,
    COUNT(*) AS total_incidentes
FROM incidentes
GROUP BY DATE(detectado_em)
ORDER BY dia;

-- 4) Taxa de auto-resolução por tipo de incidente
SELECT
    ti.nome AS tipo_incidente,
    ti.auto_remediavel,
    COUNT(i.id_incidente) AS total,
    ROUND(100.0 * SUM(CASE WHEN i.resolvido_por = 'automacao' THEN 1 ELSE 0 END) / COUNT(i.id_incidente), 1) AS pct_automacao
FROM incidentes i
JOIN tipos_incidente ti ON ti.id_tipo = i.id_tipo
WHERE i.status = 'Resolvido'
GROUP BY ti.nome, ti.auto_remediavel
ORDER BY total DESC;

-- 5) Ranking de servidores com mais incidentes
SELECT
    s.nome AS servidor,
    s.camada,
    s.criticidade,
    COUNT(i.id_incidente) AS total_incidentes
FROM incidentes i
JOIN servidores s ON s.id_servidor = i.id_servidor
GROUP BY s.nome, s.camada, s.criticidade
ORDER BY total_incidentes DESC;

-- 6) Taxa de sucesso por runbook (ações de remediação automática)
SELECT
    runbook,
    COUNT(*) AS total_execucoes,
    ROUND(100.0 * SUM(sucesso) / COUNT(*), 1) AS pct_sucesso
FROM acoes_remediacao
WHERE runbook != 'diagnostico_automatico'
GROUP BY runbook
ORDER BY total_execucoes DESC;

-- 7) Tempo economizado estimado: diferença entre o MTTR manual de referência
-- de cada tipo de incidente e o tempo real gasto nos incidentes resolvidos
-- por automação
SELECT
    ROUND(SUM(ti.mttr_manual_minutos - i.tempo_resolucao_minutos) / 60.0, 1) AS horas_economizadas_estimadas
FROM incidentes i
JOIN tipos_incidente ti ON ti.id_tipo = i.id_tipo
WHERE i.resolvido_por = 'automacao';

-- 8) Status atual da frota: situação do incidente mais recente de cada servidor
SELECT
    s.nome AS servidor,
    s.camada,
    s.criticidade,
    i.status,
    i.detectado_em
FROM servidores s
LEFT JOIN incidentes i ON i.id_servidor = s.id_servidor
WHERE i.id_incidente IS NULL OR i.detectado_em = (
    SELECT MAX(i2.detectado_em) FROM incidentes i2 WHERE i2.id_servidor = s.id_servidor
)
ORDER BY s.nome;

-- 9) Incidentes que a automação tentou e não conseguiu resolver (escalados)
SELECT
    ti.nome AS tipo_incidente,
    COUNT(*) AS total_escalados
FROM incidentes i
JOIN tipos_incidente ti ON ti.id_tipo = i.id_tipo
WHERE i.status = 'Resolvido'
  AND i.resolvido_por = 'analista'
  AND i.tentativas_automacao > 0
GROUP BY ti.nome
ORDER BY total_escalados DESC;
