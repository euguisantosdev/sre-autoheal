"""
dashboard.py

Painel do SRE Auto-Heal: mostra o estado atual da frota simulada, o feed
de incidentes recentes, e as métricas que contam a história do projeto —
quantos incidentes a automação resolve sozinha, quão mais rápido isso é
do que um analista, e quanto tempo isso representa economizado.
"""

import os
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

DB_PATH = BASE_DIR / "data" / "autoheal.db"
LOCK_PATH = BASE_DIR / "data" / ".gerando.lock"

COR_PRIMARIA = "#7C4DFF"
COR_RESOLUCAO = {"automacao": "#2ECC71", "analista": "#F39C12"}
COR_STATUS = {
    "Resolvido": "#2ECC71",
    "Em remediação": "#F39C12",
    "Aberto": "#E74C3C",
    "Escalado": "#E74C3C",
}
SEQUENCIA_CATEGORICA = px.colors.qualitative.Set2

pio.templates.default = "plotly_dark"

st.set_page_config(
    page_title="SRE Auto-Heal",
    page_icon="🩹",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    div[data-testid="stMetric"] {
        background-color: rgba(124, 77, 255, 0.08);
        border: 1px solid rgba(124, 77, 255, 0.25);
        border-radius: 10px;
        padding: 14px 16px 10px 16px;
    }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; }
    .status-pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _ensure_db() -> None:
    """Gera o banco na primeira execução, com segurança contra corrida
    entre processos (ex: Streamlit Cloud reiniciando o app mais de uma
    vez na inicialização) — mesmo padrão usado no Service Desk Dashboard."""
    if DB_PATH.exists():
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        lock_fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        esperado = 0
        while not DB_PATH.exists() and esperado < 60:
            time.sleep(1)
            esperado += 1
        if not DB_PATH.exists():
            raise RuntimeError(
                "Outro processo está gerando o banco, mas não terminou a tempo."
            )
        return

    try:
        from data import gerar_historico

        gerar_historico.main()
    finally:
        os.close(lock_fd)
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()


@st.cache_data(ttl=300)
def carregar_dados():
    conn = sqlite3.connect(DB_PATH)
    try:
        incidentes = pd.read_sql_query(
            """
            SELECT i.*, s.nome AS servidor, s.camada, s.criticidade,
                   ti.nome AS tipo_incidente, ti.auto_remediavel, ti.mttr_manual_minutos
            FROM incidentes i
            JOIN servidores s ON s.id_servidor = i.id_servidor
            JOIN tipos_incidente ti ON ti.id_tipo = i.id_tipo
            """,
            conn,
            parse_dates=["detectado_em", "resolvido_em"],
        )
        acoes = pd.read_sql_query(
            "SELECT * FROM acoes_remediacao", conn, parse_dates=["executado_em"]
        )
        servidores = pd.read_sql_query("SELECT * FROM servidores", conn)
    finally:
        conn.close()
    return incidentes, acoes, servidores


def status_mais_recente_por_servidor(incidentes: pd.DataFrame, servidores: pd.DataFrame) -> pd.DataFrame:
    if incidentes.empty:
        base = servidores.copy()
        base["status"] = "Saudável"
        return base

    idx = incidentes.sort_values("detectado_em").groupby("id_servidor").tail(1)
    status_map = idx.set_index("id_servidor")["status"]

    base = servidores.copy()
    base["status"] = base["id_servidor"].map(status_map).fillna("Saudável")
    # um incidente "Resolvido" não significa que o servidor está mal agora
    base.loc[base["status"] == "Resolvido", "status"] = "Saudável"
    return base


def main() -> None:
    try:
        _ensure_db()
    except Exception as erro:
        st.error(
            "Não consegui preparar os dados do painel. Tente recarregar a página "
            "em alguns segundos."
        )
        with st.expander("Detalhes técnicos do erro"):
            st.code(f"{type(erro).__name__}: {erro}")
        st.stop()

    st.title("🩹 SRE Auto-Heal")
    st.caption(
        "Simulação de uma frota de servidores com auto-remediação de incidentes — "
        "o que a automação resolve sozinha vs. o que precisa de um analista."
    )

    try:
        incidentes, acoes, servidores = carregar_dados()
    except sqlite3.DatabaseError as erro:
        st.error(
            "O banco de dados local parece corrompido. Apague o arquivo "
            "`data/autoheal.db` e rode o app de novo para gerá-lo do zero."
        )
        with st.expander("Detalhes técnicos do erro"):
            st.code(f"{type(erro).__name__}: {erro}")
        st.stop()

    with st.sidebar:
        st.header("Filtros")
        camadas = ["Todas"] + sorted(servidores["camada"].unique().tolist())
        camada_sel = st.selectbox("Camada", camadas)
        dias = st.slider("Últimos N dias", min_value=3, max_value=30, value=30)

    corte = pd.Timestamp.now() - pd.Timedelta(days=dias)
    df = incidentes[incidentes["detectado_em"] >= corte].copy()
    if camada_sel != "Todas":
        df = df[df["camada"] == camada_sel]

    resolvidos = df[df["status"] == "Resolvido"]

    # ---------- KPIs ----------
    col1, col2, col3, col4 = st.columns(4)

    total = len(df)
    taxa_auto = (
        100 * (resolvidos["resolvido_por"] == "automacao").mean() if len(resolvidos) else 0
    )
    mttr_auto = resolvidos.loc[resolvidos["resolvido_por"] == "automacao", "tempo_resolucao_minutos"].mean()
    mttr_analista = resolvidos.loc[resolvidos["resolvido_por"] == "analista", "tempo_resolucao_minutos"].mean()

    automatizados = resolvidos[resolvidos["resolvido_por"] == "automacao"]
    horas_economizadas = (
        (automatizados["mttr_manual_minutos"] - automatizados["tempo_resolucao_minutos"]).sum() / 60
        if len(automatizados)
        else 0
    )

    col1.metric("Incidentes no período", f"{total}")
    col2.metric("Resolvidos pela automação", f"{taxa_auto:.0f}%")
    col3.metric(
        "MTTR automação vs. manual",
        f"{mttr_auto:.1f} min" if pd.notna(mttr_auto) else "—",
        delta=f"-{(mttr_analista - mttr_auto):.0f} min vs. manual" if pd.notna(mttr_auto) and pd.notna(mttr_analista) else None,
        delta_color="inverse",
    )
    col4.metric("Horas economizadas (estimado)", f"{horas_economizadas:.0f} h")

    st.divider()

    # ---------- Status da frota ----------
    st.subheader("Status da frota agora")
    frota = status_mais_recente_por_servidor(incidentes, servidores)

    cols = st.columns(len(frota))
    for col, (_, row) in zip(cols, frota.iterrows()):
        cor = COR_STATUS.get(row["status"], "#2ECC71")
        col.markdown(
            f"""
            <div style="border:1px solid {cor}55; border-radius:10px; padding:10px; text-align:center;">
                <div style="font-weight:600; font-size:0.85rem;">{row['nome']}</div>
                <div style="color:{cor}; font-size:0.78rem; margin-top:4px;">● {row['status']}</div>
                <div style="color:#999; font-size:0.7rem; margin-top:2px;">{row['camada']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # ---------- Gráficos ----------
    g1, g2 = st.columns(2)

    with g1:
        st.subheader("Volume de incidentes por dia")
        por_dia = df.groupby(df["detectado_em"].dt.date).size().reset_index(name="total")
        fig = px.line(por_dia, x="detectado_em", y="total", markers=True)
        fig.update_traces(line_color=COR_PRIMARIA)
        fig.update_layout(xaxis_title="", yaxis_title="Incidentes")
        st.plotly_chart(fig, use_container_width=True)

    with g2:
        st.subheader("MTTR: automação vs. analista")
        mttr_df = (
            resolvidos.groupby("resolvido_por")["tempo_resolucao_minutos"]
            .mean()
            .reset_index()
        )
        fig = px.bar(
            mttr_df,
            x="resolvido_por",
            y="tempo_resolucao_minutos",
            color="resolvido_por",
            color_discrete_map=COR_RESOLUCAO,
            text_auto=".1f",
        )
        fig.update_layout(xaxis_title="", yaxis_title="Minutos", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    g3, g4 = st.columns(2)

    with g3:
        st.subheader("Taxa de auto-resolução por tipo de incidente")
        por_tipo = (
            resolvidos.groupby("tipo_incidente")["resolvido_por"]
            .apply(lambda s: 100 * (s == "automacao").mean())
            .reset_index(name="pct_automacao")
            .sort_values("pct_automacao")
        )
        fig = px.bar(
            por_tipo,
            x="pct_automacao",
            y="tipo_incidente",
            orientation="h",
            color_discrete_sequence=[COR_PRIMARIA],
            text_auto=".0f",
        )
        fig.update_layout(xaxis_title="% resolvido por automação", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with g4:
        st.subheader("Taxa de sucesso por runbook")
        acoes_runbook = acoes[acoes["runbook"] != "diagnostico_automatico"]
        if not acoes_runbook.empty:
            por_runbook = (
                acoes_runbook.groupby("runbook")["sucesso"]
                .mean()
                .mul(100)
                .reset_index(name="pct_sucesso")
                .sort_values("pct_sucesso")
            )
            fig = px.bar(
                por_runbook,
                x="pct_sucesso",
                y="runbook",
                orientation="h",
                color_discrete_sequence=SEQUENCIA_CATEGORICA,
                text_auto=".0f",
            )
            fig.update_layout(xaxis_title="% de execuções bem-sucedidas", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem execuções de runbook no período selecionado.")

    st.divider()

    # ---------- Feed de incidentes recentes ----------
    st.subheader("Incidentes recentes")
    feed = df.sort_values("detectado_em", ascending=False).head(25)[
        ["detectado_em", "servidor", "tipo_incidente", "status", "resolvido_por", "tempo_resolucao_minutos"]
    ].rename(
        columns={
            "detectado_em": "Detectado em",
            "servidor": "Servidor",
            "tipo_incidente": "Tipo",
            "status": "Status",
            "resolvido_por": "Resolvido por",
            "tempo_resolucao_minutos": "Tempo (min)",
        }
    )
    st.dataframe(feed, use_container_width=True, hide_index=True)

    with st.expander("Log de auditoria das ações de remediação automática"):
        log = acoes.sort_values("executado_em", ascending=False).head(50).rename(
            columns={
                "executado_em": "Executado em",
                "runbook": "Runbook",
                "sucesso": "Sucesso",
            }
        )
        log["Sucesso"] = log["Sucesso"].map({1: "✅", 0: "❌"})
        st.dataframe(log[["Executado em", "Runbook", "Sucesso"]], use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
