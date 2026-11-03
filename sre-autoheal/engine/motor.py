"""
motor.py

Motor de resolução de incidentes: dado um incidente (tipo + horário de
detecção), decide se o auto-healer consegue resolver sozinho, quantas
tentativas precisa, e produz o rastro de auditoria (ações de remediação)
de cada tentativa — sucesso ou falha.

Separado do gerador de dados (data/gerar_historico.py) de propósito: aqui
mora só a REGRA DE NEGÓCIO (como um incidente é resolvido), sem nada de
I/O ou SQLite, o que torna possível testar a lógica isoladamente.
"""

import random
from datetime import datetime, timedelta

from engine.catalogo import MAX_TENTATIVAS_AUTOMACAO, TEMPO_TENTATIVA_AUTOMACAO_MIN


def resolver_incidente(tipo_incidente: dict, detectado_em: datetime) -> dict:
    """Decide como um incidente é resolvido e retorna um dicionário com:

    - resolvido_por: 'automacao' | 'analista'
    - tentativas_automacao: int
    - resolvido_em: datetime
    - tempo_resolucao_minutos: float
    - acoes: list[dict] — uma por tentativa de automação (mesmo as que falharam)

    tipo_incidente é um dict com as chaves: nome, auto_remediavel,
    taxa_sucesso_automacao, mttr_manual_minutos, runbook.
    """
    acoes = []
    instante = detectado_em

    if not tipo_incidente["auto_remediavel"]:
        # o auto-healer reconhece que não é um caso pra automação (ex:
        # corrupção de dado) e já escala direto, sem ficar tentando às
        # cegas — registra isso como uma ação de diagnóstico, não de reparo
        acoes.append(
            {
                "executado_em": instante.strftime("%Y-%m-%d %H:%M:%S"),
                "runbook": "diagnostico_automatico",
                "sucesso": False,
            }
        )
        tempo_manual = max(5, random.gauss(tipo_incidente["mttr_manual_minutos"], tipo_incidente["mttr_manual_minutos"] * 0.3))
        resolvido_em = detectado_em + timedelta(minutes=tempo_manual)
        return {
            "resolvido_por": "analista",
            "tentativas_automacao": 0,
            "resolvido_em": resolvido_em,
            "tempo_resolucao_minutos": round(tempo_manual, 1),
            "acoes": acoes,
        }

    tentativas = 0
    resolvido = False

    while tentativas < MAX_TENTATIVAS_AUTOMACAO and not resolvido:
        tentativas += 1
        duracao_tentativa = random.uniform(*TEMPO_TENTATIVA_AUTOMACAO_MIN)
        instante = instante + timedelta(minutes=duracao_tentativa)

        sucesso = random.random() < tipo_incidente["taxa_sucesso_automacao"]
        acoes.append(
            {
                "executado_em": instante.strftime("%Y-%m-%d %H:%M:%S"),
                "runbook": tipo_incidente["runbook"],
                "sucesso": sucesso,
            }
        )
        if sucesso:
            resolvido = True

    if resolvido:
        tempo_total = (instante - detectado_em).total_seconds() / 60
        return {
            "resolvido_por": "automacao",
            "tentativas_automacao": tentativas,
            "resolvido_em": instante,
            "tempo_resolucao_minutos": round(tempo_total, 1),
            "acoes": acoes,
        }

    # automação esgotou as tentativas sem sucesso -> escala pra um analista,
    # que ainda precisa do tempo normal de resolução manual a partir daqui
    tempo_manual = max(5, random.gauss(tipo_incidente["mttr_manual_minutos"], tipo_incidente["mttr_manual_minutos"] * 0.3))
    resolvido_em = instante + timedelta(minutes=tempo_manual)
    tempo_total = (resolvido_em - detectado_em).total_seconds() / 60
    return {
        "resolvido_por": "analista",
        "tentativas_automacao": tentativas,
        "resolvido_em": resolvido_em,
        "tempo_resolucao_minutos": round(tempo_total, 1),
        "acoes": acoes,
    }
