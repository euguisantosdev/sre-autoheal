"""Testes da lógica de resolução de incidentes (engine/motor.py)."""

import random
from datetime import datetime

from engine.catalogo import MAX_TENTATIVAS_AUTOMACAO
from engine.motor import resolver_incidente


def _tipo(auto_remediavel=True, taxa_sucesso=1.0, mttr_manual=30, runbook="reiniciar_servico"):
    return {
        "nome": "Incidente de teste",
        "auto_remediavel": auto_remediavel,
        "taxa_sucesso_automacao": taxa_sucesso,
        "mttr_manual_minutos": mttr_manual,
        "runbook": runbook,
    }


def test_incidente_nao_auto_remediavel_sempre_vai_pro_analista():
    random.seed(1)
    tipo = _tipo(auto_remediavel=False)
    resultado = resolver_incidente(tipo, datetime(2026, 1, 1, 10, 0, 0))

    assert resultado["resolvido_por"] == "analista"
    assert resultado["tentativas_automacao"] == 0
    # ainda registra UMA ação de diagnóstico, só não tenta "consertar às cegas"
    assert len(resultado["acoes"]) == 1
    assert resultado["acoes"][0]["runbook"] == "diagnostico_automatico"
    assert resultado["acoes"][0]["sucesso"] is False


def test_incidente_com_taxa_de_sucesso_100_por_cento_sempre_resolve_sozinho():
    random.seed(2)
    tipo = _tipo(auto_remediavel=True, taxa_sucesso=1.0)
    for _ in range(50):
        resultado = resolver_incidente(tipo, datetime(2026, 1, 1, 10, 0, 0))
        assert resultado["resolvido_por"] == "automacao"
        assert resultado["tentativas_automacao"] == 1


def test_incidente_com_taxa_de_sucesso_zero_sempre_escala():
    random.seed(3)
    tipo = _tipo(auto_remediavel=True, taxa_sucesso=0.0)
    for _ in range(50):
        resultado = resolver_incidente(tipo, datetime(2026, 1, 1, 10, 0, 0))
        assert resultado["resolvido_por"] == "analista"
        assert resultado["tentativas_automacao"] == MAX_TENTATIVAS_AUTOMACAO
        assert len(resultado["acoes"]) == MAX_TENTATIVAS_AUTOMACAO
        assert all(not acao["sucesso"] for acao in resultado["acoes"])


def test_resolvido_em_nunca_eh_antes_da_deteccao():
    random.seed(4)
    detectado_em = datetime(2026, 1, 1, 10, 0, 0)
    for taxa in (0.0, 0.3, 0.7, 1.0):
        for auto in (True, False):
            tipo = _tipo(auto_remediavel=auto, taxa_sucesso=taxa)
            resultado = resolver_incidente(tipo, detectado_em)
            assert resultado["resolvido_em"] >= detectado_em
            assert resultado["tempo_resolucao_minutos"] >= 0


def test_tempo_resolucao_minutos_bate_com_a_diferenca_de_datas():
    random.seed(5)
    detectado_em = datetime(2026, 1, 1, 10, 0, 0)
    tipo = _tipo(auto_remediavel=True, taxa_sucesso=0.5)
    resultado = resolver_incidente(tipo, detectado_em)

    diferenca_minutos = (resultado["resolvido_em"] - detectado_em).total_seconds() / 60
    # tempo_resolucao_minutos é arredondado pra 1 casa decimal na saída,
    # então a tolerância tem que acomodar esse arredondamento
    assert abs(diferenca_minutos - resultado["tempo_resolucao_minutos"]) < 0.06
