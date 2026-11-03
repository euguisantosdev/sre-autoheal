"""
catalogo.py

Fonte única de verdade sobre a "frota" simulada (servidores/serviços) e o
catálogo de tipos de incidente que podem ocorrer nela — usado tanto pelo
gerador de histórico (data/gerar_historico.py) quanto pelos testes, pra
garantir que os dois nunca saiam de sincronia.

Os números de taxa de sucesso de automação e tempo médio de resolução
manual (MTTR) são estimativas plausíveis baseadas em relatos públicos do
setor de SRE/DevOps sobre auto-remediação (ex: Google SRE Workbook, relatórios
anuais de incident management da PagerDuty/Atlassian) — não são de uma empresa
real, mas também não foram inventados sem critério: incidentes "simples"
(serviço travado, disco cheio, certificado expirando) têm taxa de automação
alta; incidentes que exigem julgamento humano (corrupção de dado, pico de
erro sem causa óbvia) propositalmente NÃO são auto-remediáveis — nenhum
sistema de auto-remediação de verdade resolve 100% dos casos, e fingir que
resolveria tornaria o projeto menos honesto, não mais impressionante.
"""

SERVIDORES = [
    # (nome, camada, criticidade)
    ("web-01", "Web", "Alta"),
    ("web-02", "Web", "Alta"),
    ("api-pagamentos", "API", "Crítica"),
    ("api-autenticacao", "API", "Crítica"),
    ("db-primario", "Banco de Dados", "Crítica"),
    ("db-replica-01", "Banco de Dados", "Alta"),
    ("fila-pedidos", "Fila", "Alta"),
    ("cache-sessao", "Cache", "Média"),
    ("worker-relatorios", "Worker", "Baixa"),
    ("storage-logs", "Armazenamento", "Baixa"),
]

# (nome, auto_remediavel, taxa_sucesso_automacao, mttr_manual_minutos, runbook)
TIPOS_INCIDENTE = [
    (
        "Serviço não responde (health check falhou)",
        True, 0.85, 25,
        "reiniciar_servico",
    ),
    (
        "Disco acima de 90% de uso",
        True, 0.75, 40,
        "limpar_arquivos_temporarios",
    ),
    (
        "CPU sustentada acima de 95%",
        True, 0.40, 35,
        "reiniciar_processo_com_vazamento",
    ),
    (
        "Memória esgotada (OOM)",
        True, 0.55, 30,
        "reiniciar_servico",
    ),
    (
        "Timeout de conexão com banco de dados",
        True, 0.50, 45,
        "resetar_pool_conexoes",
    ),
    (
        "Fila de mensagens travada (consumidor parado)",
        True, 0.65, 50,
        "reiniciar_consumidor",
    ),
    (
        "Certificado SSL expirando em breve",
        True, 0.90, 20,
        "renovar_certificado",
    ),
    (
        "Pico de erros 5xx sem causa identificada",
        False, 0.0, 60,
        None,
    ),
    (
        "Corrupção de dados detectada",
        False, 0.0, 120,
        None,
    ),
]

# quantas vezes o auto-healer tenta o runbook antes de escalar pra um analista
MAX_TENTATIVAS_AUTOMACAO = 2

# faixa de tempo (minutos) que uma tentativa automatizada leva — bem mais
# rápido que um humano, porque não tem triagem, não tem fila de atendimento,
# não tem "deixa eu ver o que é isso": só detecção + execução do runbook
TEMPO_TENTATIVA_AUTOMACAO_MIN = (0.5, 3.0)
