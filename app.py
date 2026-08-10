from __future__ import annotations

from dataclasses import replace
from datetime import date

import pandas as pd
import streamlit as st

from sports_data_layer.analysis_service import run_temporal_hypotheses
from sports_data_layer.adapters.generic_mapping_adapter import GenericMappingAdapter
from sports_data_layer.capabilities import Capability, CapabilityMatrix
from sports_data_layer.registry import ProviderConfig, SportsDataRegistry

st.set_page_config(page_title="Matchbook · Sports Intelligence", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    :root { --ink:#0d1117; --paper:#f5f4ef; --muted:#6b7280; --line:#deded7; --accent:#c9f25d; }
    .stApp { background:var(--paper); color:var(--ink); font-family:'DM Sans',sans-serif; }
    [data-testid="stSidebar"] { background:#11151b; border-right:1px solid #272d35; }
    [data-testid="stSidebar"] * { color:#e8eee2 !important; }
    h1,h2,h3,h4 { font-family:'Space Grotesk',sans-serif !important; letter-spacing:-.04em; color:var(--ink); }
    [data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 { color:#f5f7f2 !important; }
    .hero { padding:2rem 0 1.2rem; border-bottom:1px solid var(--line); margin-bottom:1.4rem; }
    .eyebrow { text-transform:uppercase; letter-spacing:.16em; font-size:.7rem; font-weight:700; color:#74820d; }
    .hero h1 { font-size:clamp(2.4rem,5vw,4.8rem); line-height:.96; margin:.4rem 0 .8rem; }
    .hero p { color:var(--muted); max-width:700px; font-size:1.05rem; }
    .metric { background:#fff; border:1px solid var(--line); border-radius:16px; padding:1rem 1.1rem; min-height:105px; }
    .metric-label { color:var(--muted); font-size:.76rem; text-transform:uppercase; letter-spacing:.1em; font-weight:700; }
    .metric-value { font-family:'Space Grotesk'; font-size:2rem; font-weight:700; margin-top:.35rem; }
    .section { margin:2rem 0 .7rem; display:flex; align-items:baseline; justify-content:space-between; border-bottom:1px solid var(--line); padding-bottom:.45rem; }
    .section h2 { margin:0; font-size:1.35rem; }
    .tag { display:inline-block; background:var(--accent); padding:.25rem .55rem; border-radius:99px; font-size:.7rem; font-weight:700; }
    .discovery { background:#fff; border:1px solid var(--line); border-left:4px solid #95b920; padding:1rem 1.1rem; border-radius:12px; margin:.65rem 0; }
    .muted { color:var(--muted); font-size:.9rem; }
    footer { visibility:hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


def metric(label: str, value: str) -> None:
    st.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>', unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def get_registry(league_id: int):
    matrix = CapabilityMatrix()
    matrix.set("thesportsdb", {Capability.BASIC_RESULTS})
    adapter = GenericMappingAdapter(
        "thesportsdb",
        "https://www.thesportsdb.com/api/v1/json/123/eventsround.php",
        matrix,
        mapping={"list_path": "events", "competition": "competition", "league_id": str(league_id)},
    )
    return SportsDataRegistry({"thesportsdb": adapter}, ProviderConfig({"competition": "thesportsdb"}, {}))


st.sidebar.markdown("# ◈ Matchbook")
st.sidebar.caption("Inteligência de análise esportiva.")
st.sidebar.markdown("---")
league_id = st.sidebar.number_input("ID da liga", min_value=1, value=4351, step=1, help="Ex.: 4351 para a Brazilian Serie A.")
season_start, season_end = st.sidebar.slider("Intervalo de temporadas", min_value=2010, max_value=2026, value=(2021, 2026), step=1, help="Todas as temporadas entre o início e o fim serão coletadas e consolidadas.")
selected_seasons = [str(year) for year in range(season_start, season_end + 1)]
st.sidebar.caption(f"Serão analisadas {len(selected_seasons)} temporadas: {selected_seasons[0]}–{selected_seasons[-1]}.")
start_round = st.sidebar.number_input("Rodada inicial", min_value=1, max_value=100, value=1, step=1)
end_round = st.sidebar.number_input("Rodada final", min_value=1, max_value=100, value=38, step=1)
st.sidebar.markdown("---")
st.sidebar.caption("Fonte")
st.sidebar.markdown("**TheSportsDB · eventsround.php · V1 Free**")
st.sidebar.caption("Cada rodada é consultada separadamente e deduplicada em memória.")

st.markdown('<div class="hero"><div class="eyebrow">Sports intelligence / 03</div><h1>O jogo,<br>bem lido.</h1><p>Uma inteligência de análise que percorre várias temporadas rodada a rodada, consolida os jogos e executa as hipóteses sobre a série temporal completa — sem banco de dados.</p></div>', unsafe_allow_html=True)

if st.sidebar.button("Buscar temporada e rodar hipóteses", type="primary", use_container_width=True):
    if not selected_seasons:
        st.sidebar.error("Selecione pelo menos uma temporada.")
    elif end_round < start_round:
        st.sidebar.error("A rodada final precisa ser maior ou igual à inicial.")
    else:
        try:
            registry = get_registry(int(league_id))
            rounds = list(range(int(start_round), int(end_round) + 1))
            total_requests = len(selected_seasons) * len(rounds)
            progress = st.progress(0, text="Preparando coleta rodada a rodada…")
            unique_matches = {}
            completed = 0
            collected_rounds = 0
            for season in selected_seasons:
                empty_streak = 0
                for round_number in rounds:
                    round_matches = registry.get_matches_by_rounds("competition", [round_number], season)
                    if round_matches:
                        empty_streak = 0
                        for match in round_matches:
                            normalized = replace(match, season=season, competition="competition")
                            unique_matches[normalized.id] = normalized
                        collected_rounds += 1
                    else:
                        empty_streak += 1
                    completed += 1
                    progress.progress(completed / total_requests, text=f"{season} · rodada {round_number}/{rounds[-1]} · {len(unique_matches)} partidas únicas")
                    if empty_streak >= 2 and round_number >= 10:
                        break
            matches = sorted(unique_matches.values(), key=lambda match: (match.date, match.id))
            progress.empty()
            evidence, snapshots = run_temporal_hypotheses(matches, [], discovery_fraction=0.65)
            st.session_state["matches"] = matches
            st.session_state["evidence"] = evidence
            st.session_state["snapshots"] = snapshots
            st.session_state["seasons"] = selected_seasons
            st.session_state["rounds_collected"] = collected_rounds
            st.sidebar.success(f"{len(selected_seasons)} temporadas ({selected_seasons[0]}–{selected_seasons[-1]}) · {len(matches)} partidas; {len(evidence)} evidências avaliadas.")
        except Exception as exc:
            st.sidebar.error("A coleta ou análise falhou.")
            st.sidebar.caption(str(exc))

matches = st.session_state.get("matches", [])
evidence = st.session_state.get("evidence", [])
validated = [item for item in evidence if item.final_status == "validated"]
candidates = [item for item in evidence if item.final_status in {"candidate", "exploratory"}]
finished = [m for m in matches if m.is_finished]
upcoming = [m for m in matches if not m.is_finished]
home_wins = sum(m.home_score > m.away_score for m in finished)
draws = sum(m.home_score == m.away_score for m in finished)
away_wins = len(finished) - home_wins - draws

cols = st.columns(4)
with cols[0]: metric("Partidas", f"{len(matches):,}")
with cols[1]: metric("Finalizadas", f"{len(finished):,}")
with cols[2]: metric("Candidatos", f"{len(candidates):,}")
with cols[3]: metric("Validados", f"{len(validated):,}")

st.markdown('<div class="section"><h2>Leitura da temporada</h2><span class="tag">RODADA A RODADA</span></div>', unsafe_allow_html=True)
if not matches:
    st.info("Nenhuma temporada foi carregada. Use a ação lateral para buscar as rodadas e executar as hipóteses.")
else:
    left, right = st.columns([1.35, 1])
    with left:
        results_df = pd.DataFrame({"Resultado": ["Casa", "Empate", "Fora"], "Partidas": [home_wins, draws, away_wins]})
        st.bar_chart(results_df.set_index("Resultado"), color="#91ad25", height=220)
    with right:
        st.markdown("#### Balanço da amostra consolidada")
        if finished:
            total_goals = sum(m.home_score + m.away_score for m in finished)
            st.markdown(f"**{total_goals / len(finished):.2f}** gols por partida")
            st.markdown(f"**{100 * home_wins / len(finished):.0f}%** de vitórias mandantes")
            st.markdown(f"**{100 * draws / len(finished):.0f}%** de empates")
        st.caption(f"{len(upcoming)} partidas sem placar · {st.session_state.get('rounds_collected', 0)} rodadas com dados · temporadas: {', '.join(st.session_state.get('seasons', []))}.")

st.markdown('<div class="section"><h2>Partidas consolidadas</h2><span class="muted">Deduplicadas pelo ID do evento</span></div>', unsafe_allow_html=True)
if matches:
    match_df = pd.DataFrame([{"Data": m.date.strftime("%d/%m/%Y"), "Mandante": m.home_team.name, "Placar": f"{m.home_score if m.home_score is not None else '—'} × {m.away_score if m.away_score is not None else '—'}", "Visitante": m.away_team.name, "Status": "Finalizada" if m.is_finished else "Agendada"} for m in sorted(matches, key=lambda item: item.date, reverse=True)])
    st.dataframe(match_df, width="stretch", hide_index=True)
else:
    st.info("A tabela aparecerá depois da coleta.")

st.markdown('<div class="section"><h2>Descobertas da inteligência</h2><span class="muted">Descoberta → validação futura</span></div>', unsafe_allow_html=True)
if evidence:
    for item in validated:
        st.markdown(f'<div class="discovery"><strong>[VALIDADO] {item.title}</strong><br><span class="muted">{item.subject} · descoberta n={item.n_discovery} · validação n={item.n_validation} · q={item.q_value if item.q_value is not None else "—"} · {item.reason}</span></div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame([{"Status": item.final_status, "Código": item.code, "Hipótese": item.title, "Entidade": item.subject, "N descoberta": item.n_discovery, "N validação": item.n_validation, "p": round(item.p_value, 4), "q": round(item.q_value, 4) if item.q_value is not None else None, "Motivo": item.reason} for item in evidence]), hide_index=True, width="stretch")
else:
    st.info("As descobertas aparecerão após a coleta da temporada.")

st.markdown('<div class="section"><h2>Como interpretar</h2></div>', unsafe_allow_html=True)
st.markdown('<p class="muted">A temporada é dividida cronologicamente: 65% para descoberta e 35% para validação futura. As variáveis temporais são calculadas apenas com partidas anteriores. Um candidato não é tratado como achado robusto até reaparecer na janela posterior com o mesmo código e entidade.</p>', unsafe_allow_html=True)
