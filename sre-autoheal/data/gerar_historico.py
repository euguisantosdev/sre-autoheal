"""
gerar_historico.py

Gera o banco SQLite com um histórico fictício, porém realista, de
incidentes na frota simulada: quem foi afetado, que tipo de problema,
se o auto-healer resolveu sozinho ou precisou escalar pra um analista,
e o rastro de auditoria de cada tentativa de remediação automática.

Uso:
    python data/gerar_historico.py

Gera: data/autoheal.db
"""

import os
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from engine.catalogo import SERVIDORES, TIPOS_INCIDENTE
from engine.motor import resolver_incidente

random.seed(42)  # reprodutibilidade

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "autoheal.db"
SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql"

DIAS_HISTORICO = 30
INCIDENTES_POR_DIA_MEDIA = 18  # média de incidentes/dia somando toda a frota


def criar_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def popular_dimensoes(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO servidores (nome, camada, criticidade) VALUES (?, ?, ?)",
        SERVIDORES,
    )
    cur.executemany(
        """
        INSERT INTO tipos_incidente (
            nome, auto_remediavel, taxa_sucesso_automacao, mttr_manual_minutos, runbook
        ) VALUES (?, ?, ?, ?, ?)
        """,
        [(n, int(a), t, m, r) for (n, a, t, m, r) in TIPOS_INCIDENTE],
    )
    conn.commit()


def gerar_incidentes(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    cur.execute("SELECT id_servidor FROM servidores")
    servidores_ids = [row[0] for row in cur.fetchall()]

    cur.execute(
        """
        SELECT id_tipo, nome, auto_remediavel, taxa_sucesso_automacao,
               mttr_manual_minutos, runbook
        FROM tipos_incidente
        """
    )
    tipos = cur.fetchall()

    agora = datetime.now()
    inicio = agora - timedelta(days=DIAS_HISTORICO)

    dia_atual = inicio
    while dia_atual < agora:
        n_incidentes_dia = max(
            0, round(random.gauss(INCIDENTES_POR_DIA_MEDIA, INCIDENTES_POR_DIA_MEDIA * 0.3))
        )

        for _ in range(n_incidentes_dia):
            id_servidor = random.choice(servidores_ids)
            tipo = random.choice(tipos)
            id_tipo, nome_tipo, auto_remediavel, taxa_sucesso, mttr_manual, runbook = tipo

            segundos_no_dia = random.randint(0, 24 * 3600 - 1)
            detectado_em = dia_atual + timedelta(seconds=segundos_no_dia)
            if detectado_em >= agora:
                continue

            tipo_dict = {
                "nome": nome_tipo,
                "auto_remediavel": bool(auto_remediavel),
                "taxa_sucesso_automacao": taxa_sucesso,
                "mttr_manual_minutos": mttr_manual,
                "runbook": runbook,
            }

            resultado = resolver_incidente(tipo_dict, detectado_em)

            acoes_ja_ocorridas = [
                acao
                for acao in resultado["acoes"]
                if datetime.strptime(acao["executado_em"], "%Y-%m-%d %H:%M:%S") <= agora
            ]

            if resultado["resolvido_em"] <= agora:
                status = "Resolvido"
                resolvido_em_str = resultado["resolvido_em"].strftime("%Y-%m-%d %H:%M:%S")
                resolvido_por = resultado["resolvido_por"]
                tempo_resolucao = resultado["tempo_resolucao_minutos"]
            else:
                # na linha do tempo simulada, a resolução cairia no futuro —
                # ou seja, "agora" esse incidente ainda estaria em andamento
                status = "Em remediação" if acoes_ja_ocorridas else "Aberto"
                resolvido_em_str = None
                resolvido_por = None
                tempo_resolucao = None

            cur.execute(
                """
                INSERT INTO incidentes (
                    id_servidor, id_tipo, detectado_em, resolvido_em, resolvido_por,
                    tentativas_automacao, tempo_resolucao_minutos, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    id_servidor,
                    id_tipo,
                    detectado_em.strftime("%Y-%m-%d %H:%M:%S"),
                    resolvido_em_str,
                    resolvido_por,
                    len(
                        [a for a in acoes_ja_ocorridas if a["runbook"] != "diagnostico_automatico"]
                    ),
                    tempo_resolucao,
                    status,
                ),
            )
            id_incidente = cur.lastrowid

            for acao in acoes_ja_ocorridas:
                cur.execute(
                    """
                    INSERT INTO acoes_remediacao (id_incidente, executado_em, runbook, sucesso)
                    VALUES (?, ?, ?, ?)
                    """,
                    (id_incidente, acao["executado_em"], acao["runbook"], int(acao["sucesso"])),
                )

        dia_atual += timedelta(days=1)

    conn.commit()


def gerar_incidentes_recentes_em_andamento(conn: sqlite3.Connection) -> None:
    """Garante um punhado de incidentes bem recentes, ainda não resolvidos,
    espalhados pelos últimos ~90 minutos — pra quem abrir o dashboard ver
    uma frota "viva", com coisa em andamento, e não só histórico fechado.

    Vale notar: isso é só pra manter a tela interessante num snapshot (o
    banco é gerado uma vez, na primeira execução do app). Não afeta as
    métricas agregadas de MTTR/taxa de automação, que olham só pros
    incidentes já resolvidos.
    """
    cur = conn.cursor()

    cur.execute("SELECT id_servidor FROM servidores")
    servidores_ids = [row[0] for row in cur.fetchall()]

    cur.execute(
        "SELECT id_tipo, nome, auto_remediavel, runbook FROM tipos_incidente"
    )
    tipos = cur.fetchall()

    agora = datetime.now()
    n_incidentes_recentes = random.randint(4, 7)

    for _ in range(n_incidentes_recentes):
        id_servidor = random.choice(servidores_ids)
        id_tipo, nome_tipo, auto_remediavel, runbook = random.choice(tipos)

        minutos_atras = random.uniform(1, 90)
        detectado_em = agora - timedelta(minutes=minutos_atras)

        # metade ainda nem teve uma primeira tentativa (Aberto), metade já
        # teve ao menos uma tentativa automática em andamento (Em remediação)
        teve_tentativa = bool(auto_remediavel) and random.random() < 0.5
        status = "Em remediação" if teve_tentativa else "Aberto"

        cur.execute(
            """
            INSERT INTO incidentes (
                id_servidor, id_tipo, detectado_em, resolvido_em, resolvido_por,
                tentativas_automacao, tempo_resolucao_minutos, status
            ) VALUES (?, ?, ?, NULL, NULL, ?, NULL, ?)
            """,
            (
                id_servidor,
                id_tipo,
                detectado_em.strftime("%Y-%m-%d %H:%M:%S"),
                1 if teve_tentativa else 0,
                status,
            ),
        )
        id_incidente = cur.lastrowid

        if teve_tentativa:
            acao_instante = detectado_em + timedelta(minutes=random.uniform(0.5, 2.0))
            cur.execute(
                """
                INSERT INTO acoes_remediacao (id_incidente, executado_em, runbook, sucesso)
                VALUES (?, ?, ?, 0)
                """,
                (id_incidente, acao_instante.strftime("%Y-%m-%d %H:%M:%S"), runbook),
            )

    conn.commit()


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # mesmo padrão de escrita atômica + lock usado no outro projeto: gera
    # num arquivo temporário e só troca pelo definitivo no final, evitando
    # corromper o banco se duas execuções rodarem ao mesmo tempo (comum em
    # plataformas de deploy que podem reiniciar o app mais de uma vez)
    tmp_path = DB_PATH.with_suffix(".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(tmp_path)
    try:
        criar_schema(conn)
        popular_dimensoes(conn)
        gerar_incidentes(conn)
        gerar_incidentes_recentes_em_andamento(conn)
        total = conn.execute("SELECT COUNT(*) FROM incidentes").fetchone()[0]
    finally:
        conn.close()

    os.replace(tmp_path, DB_PATH)
    print(f"Banco gerado em {DB_PATH} com {total} incidentes.")


if __name__ == "__main__":
    main()
