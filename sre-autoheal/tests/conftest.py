import sqlite3
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from data import gerar_historico  # noqa: E402


@pytest.fixture(scope="session")
def gerador():
    return gerar_historico


@pytest.fixture()
def banco_teste(tmp_path, gerador):
    """Gera um banco isolado (mesma lógica do gerador real) num arquivo
    temporário, pra cada teste rodar contra um banco limpo e reprodutível."""
    db_path = tmp_path / "autoheal_teste.db"
    conn = sqlite3.connect(db_path)
    try:
        gerador.criar_schema(conn)
        gerador.popular_dimensoes(conn)
        gerador.gerar_incidentes(conn)
        gerador.gerar_incidentes_recentes_em_andamento(conn)
    finally:
        conn.close()
    return db_path
