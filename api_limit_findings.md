Fonte oficial consultada: https://www.thesportsdb.com/docs_api_guide

Achados:

- A chave gratuita atual da V1 é `123`.
- A API V2 é exclusiva para assinantes Premium.
- A documentação informa limite global de 30 requisições por minuto para usuários free.
- O endpoint V1 `eventsseason.php` mostra `Free Limit: 15` e `Premium Limit: 3000`.
- Portanto, a consulta do dashboard retornar 15 partidas é o comportamento esperado da versão free, não um truncamento causado pelo Streamlit ou pelo código Python.

Consequência técnica: para carregar uma temporada completa, a aplicação precisa de uma fonte Premium ou de uma fonte alternativa que permita paginação/extração completa. Fazer várias chamadas artificiais ao mesmo endpoint não garante paginação, pode duplicar partidas e pode atingir o limite de 30 requisições por minuto.
