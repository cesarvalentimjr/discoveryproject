# Sports Data Layer — TheSportsDB Free

Pipeline Python que consulta a versão gratuita V1 do [TheSportsDB](https://www.thesportsdb.com/docs_api_examples), normaliza partidas e executa hipóteses estatísticas conservadoras.

## O que foi concluído

O projeto agora possui um pacote executável chamado `sports_data_layer`, com modelos normalizados (`Match`, `StandingRow` e `TeamRef`), registro de provedores com cache TTL, seleção de fallback, adaptador JSON genérico e ingestão compatível com o formato `events` usado pelo TheSportsDB.

Também foram restauradas as quatro hipóteses previstas no README original: D006, desempenho em casa versus fora; D010, sequência quente/fria; D022, impacto dos dias de descanso; e D101, desempenho por faixa de tabela. O lote aplica a correção de Benjamini–Hochberg e publica somente descobertas ajustadas como significativas.

## Instalação e execução

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m sports_data_layer.example_usage
```

Para executar apenas o bootstrap do provedor:

```bash
python -m sports_data_layer.tools.bootstrap
```

A consulta padrão usa o endpoint gratuito:

```text
https://www.thesportsdb.com/api/v1/json/123/eventsseason.php?id=4351&s=2025
```

O identificador `123` é o código público usado nos exemplos V1 da documentação. Para outra liga ou temporada, altere `id` e `s` em `sports_data_layer/example_usage.py` e em `sports_data_layer/tools/bootstrap.py`.

## Resultado normalizado

```python
from datetime import date
from sports_data_layer.tools.bootstrap import ProviderSpec, bootstrap_registry

registry = bootstrap_registry([
    ProviderSpec(
        provider="thesportsdb",
        url="https://www.thesportsdb.com/api/v1/json/123/eventsseason.php?id=4351&s=2025",
        competition="brasileirao_a",
    )
])

matches = registry.get_matches("brasileirao_a", date(2025, 1, 1), date(2025, 12, 31))
```

## Limitações da versão gratuita

A documentação fornecida mostra a V1 gratuita para consultas como `searchteams.php` e `lookupevent.php`; os exemplos V2, incluindo livescores, exigem chave de API Premium [1]. O projeto, portanto, declara automaticamente apenas `BASIC_RESULTS` ao consumir `eventsseason.php`. Sem uma fonte confiável de classificação, D101 é pulada e não é fabricada uma tabela.

A resposta pode conter partidas sem placar, adiadas ou futuras. Essas partidas continuam disponíveis no resultado normalizado, mas o motor estatístico só usa partidas finalizadas. **A API free limita `eventsseason.php` a 15 eventos por consulta**, enquanto a documentação indica até 3.000 para Premium [2]. Portanto, quando o dashboard mostra 15 partidas, isso é um limite da fonte e não significa que a temporada tenha apenas 15 jogos. Fazer várias chamadas idênticas não cria paginação confiável e pode retornar duplicatas ou atingir o limite global de 30 requisições por minuto para usuários free [2].

## Inteligência analítica sem banco de dados

O caminho principal pode funcionar sem banco: a aplicação percorre a temporada rodada a rodada usando `eventsround.php`, consolida os eventos em memória pelo `idEvent` e executa as hipóteses sobre o conjunto completo obtido naquela execução. Isso resolve a limitação de 15 eventos do endpoint de temporada sem exigir infraestrutura adicional. Os resultados permanecem na sessão atual e são recalculados quando uma nova coleta é iniciada.

O banco SQLite continua disponível como módulo opcional para quem quiser persistir histórico, mas não é necessário para rodar a análise rodada a rodada.

Para executar o pipeline sem frontend:

```bash
python run_round_intelligence.py --league-id 4351 --season 2025 --start-round 1 --end-round 38
```

O sistema faz uma requisição por rodada, remove duplicidades pelo ID do evento e, ao final, imprime o total consolidado e os sinais significativos. A API Free permite aproximadamente 30 requisições por minuto; por isso o adaptador espera cerca de 2,1 segundos entre rodadas e trata respostas HTTP 429 com espera adicional. Uma temporada de 38 rodadas pode levar cerca de 1–2 minutos.

### Banco opcional


O núcleo do projeto é o pipeline analítico, não o dashboard. O banco SQLite `sports_intelligence.db` mantém partidas por `event_id`, registra cada execução de ingestão e armazena os candidatos e sinais produzidos pelas hipóteses. Em execução local, esse arquivo é persistente. No Streamlit Community Cloud, o filesystem da aplicação pode ser recriado em reinícios ou novos deploys; para persistência operacional permanente, o próximo passo é apontar a mesma camada para um PostgreSQL/Supabase ou outro banco externo usando um segredo de conexão. Cada nova coleta faz upsert das partidas, recalcula as hipóteses sobre todo o histórico da competição e aplica Benjamini–Hochberg ao lote de candidatos.

Para usar o banco opcional e acumular uma janela fracionada:

```bash
python run_intelligence.py --league-id 4351 --season 2025 --db sports_intelligence.db
```

Para acumular uma janela fracionada:

```bash
python run_intelligence.py --league-id 4351 --season 2025 --start 2025-03-01 --end 2025-03-28 --db sports_intelligence.db
```

O comando pode ser executado novamente com outra janela. As partidas já existentes não são duplicadas, porque o banco usa o ID do evento como chave primária. Para consultar o histórico pelo Python:

```python
from sports_data_layer.storage import SportsDatabase

db = SportsDatabase("sports_intelligence.db")
print(db.summary("competition"))
print(db.get_discoveries(significant_only=True))
```

## Dashboard visual

O projeto agora inclui `app.py`, um frontend enxuto em Streamlit. Para executar localmente:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Depois, abra `http://localhost:8501`. O Streamlit busca as rodadas, mostra o progresso, consolida os eventos em memória e executa as hipóteses. O frontend não depende de banco para o fluxo principal.

Para buscar uma quantidade maior de partidas na API Free, selecione **Fracionada · por dia** no campo **Modo de coleta**. Informe uma janela de até 28 dias; o aplicativo fará uma requisição por data, consolidará os resultados e removerá duplicidades pelo ID do evento. Como o limite global é de 30 requisições por minuto, a janela foi limitada a 28 dias por segurança. Para carregar uma temporada inteira, repita a coleta em blocos de datas diferentes ou use uma fonte Premium.


## Publicação no GitHub e Streamlit Cloud

Crie um repositório no GitHub e, dentro da pasta do projeto, execute:

```bash
git init
git add .
git commit -m "Adicionar dashboard Streamlit de inteligência esportiva"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

No [Streamlit Community Cloud](https://share.streamlit.io/), escolha **New app**, selecione o repositório, a branch `main` e informe `app.py` como arquivo principal. O serviço instalará automaticamente as dependências de `requirements.txt`.

## Verificação

```bash
python -m compileall -q sports_data_layer app.py
python -m sports_data_layer.example_usage
streamlit run app.py
```

A execução foi validada com a resposta real do TheSportsDB: o provedor foi inicializado, 15 partidas foram normalizadas e o motor concluiu sem exceção.

## Estrutura principal

| Caminho | Responsabilidade |
|---|---|
| `sports_data_layer/models.py` | Modelos normalizados de times, partidas e tabela |
| `sports_data_layer/adapters/generic_mapping_adapter.py` | Conversão da resposta JSON em modelos |
| `sports_data_layer/tools/autonomous_pipeline.py` | Validação inicial e declaração de capacidades |
| `sports_data_layer/registry.py` | Cache, seleção de provedor e fallback |
| `sports_data_layer/hypotheses/` | Hipóteses e correção estatística |
| `sports_data_layer/example_usage.py` | Exemplo completo de execução |

## Referências

[1]: https://www.thesportsdb.com/docs_api_examples "TheSportsDB — API Tutorial and Examples"
[2]: https://www.thesportsdb.com/docs_api_guide "TheSportsDB — Free Sports API Documentation"
