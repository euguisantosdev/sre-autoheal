"""Testes do gerador de histórico (data/gerar_historico.py)."""

import sqlite3


def test_todos_os_servidores_foram_criados(banco_teste, gerador):
    conn = sqlite3.connect(banco_teste)
    total = conn.execute("SELECT COUNT(*) FROM servidores").fetchone()[0]
    conn.close()
    assert total == len(gerador.SERVIDORES)


def test_todos_os_tipos_de_incidente_foram_criados(banco_teste, gerador):
    conn = sqlite3.connect(banco_teste)
    total = conn.execute("SELECT COUNT(*) FROM tipos_incidente").fetchone()[0]
    conn.close()
    assert total == len(gerador.TIPOS_INCIDENTE)


def test_gerou_incidentes(banco_teste):
    conn = sqlite3.connect(banco_teste)
    total = conn.execute("SELECT COUNT(*) FROM incidentes").fetchone()[0]
    conn.close()
    assert total > 0


def test_status_sao_validos(banco_teste):
    conn = sqlite3.connect(banco_teste)
    status = {row[0] for row in conn.execute("SELECT DISTINCT status FROM incidentes")}
    conn.close()
    assert status <= {"Aberto", "Em remediação", "Resolvido", "Escalado"}


def test_resolvido_por_eh_valido_ou_nulo(banco_teste):
    conn = sqlite3.connect(banco_teste)
    valores = {row[0] for row in conn.execute("SELECT DISTINCT resolvido_por FROM incidentes")}
    conn.close()
    assert valores <= {"automacao", "analista", None}


def test_incidentes_resolvidos_tem_data_de_resolucao_e_tempo(banco_teste):
    conn = sqlite3.connect(banco_teste)
    linhas = conn.execute(
        "SELECT resolvido_em, tempo_resolucao_minutos FROM incidentes WHERE status = 'Resolvido'"
    ).fetchall()
    conn.close()
    assert linhas, "deveria haver pelo menos um incidente resolvido para testar"
    for resolvido_em, tempo in linhas:
        assert resolvido_em is not None
        assert tempo is not None
        assert tempo >= 0


def test_incidentes_em_aberto_nao_tem_data_de_resolucao(banco_teste):
    conn = sqlite3.connect(banco_teste)
    linhas = conn.execute(
        "SELECT resolvido_em FROM incidentes WHERE status IN ('Aberto', 'Em remediação')"
    ).fetchall()
    conn.close()
    for (resolvido_em,) in linhas:
        assert resolvido_em is None


def test_tipos_nao_auto_remediaveis_nunca_sao_resolvidos_por_automacao(banco_teste):
    """Regressão: um incidente marcado como NÃO auto-remediável (ex: corrupção
    de dado) nunca pode acabar com resolvido_por = 'automacao' — isso
    quebraria a honestidade da métrica de taxa de auto-resolução."""
    conn = sqlite3.connect(banco_teste)
    linhas = conn.execute(
        """
        SELECT COUNT(*)
        FROM incidentes i
        JOIN tipos_incidente ti ON ti.id_tipo = i.id_tipo
        WHERE ti.auto_remediavel = 0 AND i.resolvido_por = 'automacao'
        """
    ).fetchone()
    conn.close()
    assert linhas[0] == 0


def test_ha_incidentes_em_andamento_para_o_dashboard_nao_parecer_estatico(banco_teste):
    conn = sqlite3.connect(banco_teste)
    total = conn.execute(
        "SELECT COUNT(*) FROM incidentes WHERE status IN ('Aberto', 'Em remediação')"
    ).fetchone()[0]
    conn.close()
    assert total > 0


def test_seed_fixa_gera_historico_reprodutivel(tmp_path, gerador):
    import random

    def gerar_total(caminho):
        random.seed(42)
        conn = sqlite3.connect(caminho)
        try:
            gerador.criar_schema(conn)
            gerador.popular_dimensoes(conn)
            gerador.gerar_incidentes(conn)
            return conn.execute("SELECT COUNT(*) FROM incidentes").fetchone()[0]
        finally:
            conn.close()

    total_1 = gerar_total(tmp_path / "db1.db")
    total_2 = gerar_total(tmp_path / "db2.db")
    assert total_1 == total_2
