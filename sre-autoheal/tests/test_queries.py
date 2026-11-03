"""Testes das queries de análise (sql/queries_analise.sql)."""

import re
import sqlite3
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
QUERIES_PATH = BASE_DIR / "sql" / "queries_analise.sql"


def _carregar_queries():
    sql = QUERIES_PATH.read_text(encoding="utf-8")
    blocos = re.split(r"(?=-- \d\))", sql)
    return [b.strip() for b in blocos if re.match(r"^-- \d\)", b.strip())]


QUERIES = _carregar_queries()


def test_arquivo_tem_as_9_queries_esperadas():
    assert len(QUERIES) == 9


@pytest.mark.parametrize("query", QUERIES, ids=[q.splitlines()[0] for q in QUERIES])
def test_query_roda_sem_erro(query, banco_teste):
    conn = sqlite3.connect(banco_teste)
    try:
        conn.execute(query).fetchall()
    finally:
        conn.close()


def test_query_taxa_auto_resolucao_retorna_percentual_valido(banco_teste):
    conn = sqlite3.connect(banco_teste)
    linha = conn.execute(QUERIES[0]).fetchone()
    conn.close()
    pct, total = linha
    assert 0 <= pct <= 100
    assert total > 0


def test_query_mttr_mostra_automacao_mais_rapida_que_analista(banco_teste):
    conn = sqlite3.connect(banco_teste)
    linhas = dict((row[0], row[1]) for row in conn.execute(QUERIES[1]).fetchall())
    conn.close()
    if "automacao" in linhas and "analista" in linhas:
        assert linhas["automacao"] < linhas["analista"]
