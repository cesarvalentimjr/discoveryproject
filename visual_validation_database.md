# Validação visual — modo inteligência

Em 09/08/2026, o `app.py` foi iniciado no Streamlit local com `SPORTS_DB_PATH=/tmp/matchbook_test.db`.

A tela inicial carregou corretamente e apresentou: ID da liga, temporada, estratégia de ingestão, botão **Ingerir dados e rodar hipóteses**, localização do banco, métricas de histórico/candidatos/sinais, estado vazio do banco e seções de partidas persistidas e descobertas da inteligência.

A mensagem central confirma o novo fluxo: o sistema acumula partidas no banco, reprocessa o histórico e publica sinais sustentados pelas hipóteses. Não houve erro de aplicação no carregamento.
