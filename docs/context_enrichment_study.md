# Estudo de Viabilidade — Enriquecimento de Contexto para o Gatekeeper

**Data:** 04 de Maio, 2026
**Status:** Em análise
**Onda:** 7 — Bloco 7A (ENR.1)
**Autor:** JAPredictBet

---

## 1. Resumo Executivo

Este documento avalia sistematicamente as opções técnicas para enriquecer o contexto injetado no Gatekeeper LLM (Prompt Mestre V26). O diagnóstico de 04-MAI-2026 revelou que o `MatchContext` atual cobre odds + escalações + lesões + tabela, mas tem **4 gaps críticos**:

| Gap | Impacto | Item Roadmap |
|-----|---------|-------------|
| Árbitro (`RefereeInfo`) nunca populado | Pilar 3 da validação (Arbitragem) fica cego | ENR.3 |
| H2H recente ausente no Shadow Mode | Análise 1x2 e Over/Under sem histórico de confronto | ENR.4 |
| **Standings com fallback 2024 (dados velhos)** | **Gatekeeper recebe tabela defasada 2 anos → decisões incorretas** | **→ Correção Imediata** |
| Zero contexto externo (notícias) | Desfalques de última hora, clima, motivação extra-campo ignorados | ENR.5 |
| Sem memória de longo prazo | Gatekeeper repete erros, não aprende com veredictos passados | ENR.2 |

**⚠️ Alerta de Qualidade — Standings com Fallback 2024:** O [`context_collector.py`](src/japredictbet/data/context_collector.py:528) aplica fallback para temporada 2024 quando a temporada atual não retorna dados da API-Football. Isso significa que o Gatekeeper pode estar recebendo **dados de tabela com 2 anos de defasagem** (ex: analisar um jogo de 2026 com standings de 2024). Dados desatualizados são **piores que ausência de dados** — podem induzir o LLM a conclusões incorretas sobre o momento da equipe.

**Causa raiz:** O plano free da API-Football v3 tem cobertura limitada de temporadas. Para acesso à temporada atual (2025/2026), é necessário o plano PRO ($40/mês, 750 req/dia) ou superior.

**Recomendação:** Remover o fallback 2024 e substituir por `None` (ausência explícita) quando a temporada atual não está disponível. O prompt do Gatekeeper deve tratar `home_standing: null` como "dados de tabela indisponíveis" em vez de receber silenciosamente dados velhos. Alternativa: upgrade para API-Football PRO.

---

## 2. Diagnóstico do Fluxo Atual

### 2.1 Fluxo Pre-Match (Shadow Mode primário)

```
superbet_scraper.py (hoje)
  → data/odds/pre_match/YYYY-MM-DD.json
    → pre_match_odds.py::load_pre_match_contexts()
      → List[MatchContext] com odds populados (SEM lineup, standings, referee, H2H)
        → ContextCollector.enrich_pre_match_contexts()
          → API-Football: fixtures/{date} → fuzzy match → lineups, injuries, standings
          → ❌ referee NÃO populado
          → ❌ H2H NÃO populado
        → GatekeeperLivePipeline._evaluate_single_match()
          → match_ctx.to_llm_context() → JSON compacto injetado no prompt
          → GatekeeperAgent.evaluate_match() → LLM call
```

### 2.2 Fluxo Live T-60 (fallback, menos usado)

```
ContextCollector.collect_upcoming(minutes_before=60)
  → SuperbetCollector.fetch_today_odds() → SSE feed
  → ApiFootballClient.get_fixtures_today() → fixtures na janela T-60
    → get_lineups(fixture_id) → ✅
    → get_injuries(fixture_id) → ✅
    → get_standings(league_id, season) → ✅
    → ❌ get_referee(fixture_id) → método NÃO EXISTE
    → ❌ get_h2h(fixture_id) → método NÃO EXISTE
```

### 2.3 O que o `MatchContext.to_llm_context()` serializa HOJE

```json
{
  "home_team": "...",
  "away_team": "...",
  "kickoff_utc": "...",
  "league": "...",
  "odds": { "corner_line": 9.5, "corner_over_odds": 1.85, ... },
  "home_lineup": { "formation": "4-3-3", "missing_players": [...] },
  "away_lineup": { ... },
  "home_standing": { "rank": 3, "points": 42, "form": "WWDLW" },
  "away_standing": { ... }
  // ❌ "referee": ausente (código existe na linha 171-172 de context_collector.py)
  // ❌ "h2h": ausente (não há campo no MatchContext nem no to_llm_context)
  // ❌ "external_research": ausente (não implementado)
  // ❌ "knowledge_store": ausente (não implementado)
}
```

### 2.4 Onde o Prompt Mestre V26 referencia esses dados

| Seção do Prompt | Depende de | Status |
|-----------------|-----------|--------|
| Pilar 1 — Comportamento | Dados históricos (FeatureStore) | ✅ Parcial (não injetado no Shadow) |
| Pilar 2 — Desfalques | `home_lineup.missing_players` | ✅ |
| Pilar 3 — Arbitragem | `referee` | ❌ NUNCA populado |
| Pilar 4 — Coerência com o jogo | Análise qualitativa do LLM | ⚠️ Sem H2H, sem notícias |
| Pilar 5 — Contexto competitivo | `standings` | ✅ |
| Análise 1x2 | H2H últimas 3 partidas (linha 192 do prompt) | ❌ Prompt pede, dado não existe |
| Análise Over/Under Gols | Histórico de unders em H2H | ❌ Prompt referencia, dado ausente |

---

## 3. Fontes de Dados Avaliadas

### 3.1 API-Football v3 (api-sports.io) — JÁ INTEGRADA

**Plano:** Free tier — 100 req/dia
**Endpoints já usados:** `fixtures`, `fixtures/lineups`, `injuries`, `standings`
**Endpoints disponíveis e NÃO usados:**

| Endpoint | Dados | Req/dia estimado | Custo |
|----------|-------|------------------|-------|
| `fixtures/{id}` | `referee` (nome do árbitro) | +1 por partida (já incluso na chamada `fixtures`) | $0 |
| `fixtures/headtohead/{h2h}` | Últimos N confrontos entre dois times | +1 por partida | $0 |
| `fixtures/{id}/events` | Eventos do jogo (gols, cartões) | Pós-jogo apenas | $0 |
| `teams/{id}/statistics` | Estatísticas agregadas do time | +2 por partida | $0 |

**Limite diário:** 100 requisições. Considerando 10 ligas × ~5 jogos/dia = 50 partidas:
- `fixtures` (1 chamada bulk) = 1 req
- `fixtures/lineups` (50×) = 50 req
- `injuries` (50×) = 50 req
- **TOTAL já consumido: 101 req** ⚠️ **Já acima do limite free!**

**Realidade operacional:** O plano free (100 req/dia) é insuficiente para 50 partidas com 2 endpoints por partida. Soluções:
1. **Usar `fixtures` com `include=lineups`** — o endpoint `fixtures` pode retornar lineups inline via parâmetro (reduz de 50 para 0 chamadas extras).
2. **Fazer `get_referee()` inline no loop de `fixtures`** — o campo `referee` JÁ VEM no response de `fixtures` (sem chamada extra) se o plano permitir.
3. **Plano PRO ($40/mês)** — 750 req/dia. Cobre folgadamente 50 partidas com todos os endpoints.

**Verificação:** O response do endpoint `fixtures` da API-Football v3 **já inclui o campo `fixture.referee`** quando disponível. Não é necessária uma chamada extra a `fixtures/{id}`.

```json
// Exemplo de response de fixtures (já recebido hoje)
{
  "fixture": {
    "id": 123456,
    "referee": "Wilton Pereira Sampaio",  // ← JÁ VEM AQUI!
    "date": "2026-05-04T19:00:00+00:00"
  },
  "teams": { "home": {...}, "away": {...} },
  "league": {...}
}
```

**Conclusão:** ENR.3 (Árbitro) é **custo zero em requisições** — o dado já trafega na chamada `fixtures` existente. Basta extrair o campo e popular `RefereeInfo`.

### 3.2 Web Search / Notícias

| Fonte | Custo | Limite | Qualidade | Latência |
|-------|-------|--------|-----------|----------|
| **DuckDuckGo Instant Answers** | $0 | Ilimitado (não oficial) | Média — snippets, sem corpo completo | 1-3s |
| **SerpAPI** (Google Search) | $50/mês (100 searches) | 100/mês no plano básico | Alta — resultados Google completos | 2-4s |
| **Tavily Search API** | $0 (1000 req/mês) | 1000/mês free | Alta — feito para LLM, resume automaticamente | 1-2s |
| **NewsAPI.org** | $0 (500 req/dia) | 500/dia dev; 100/dia production | Média-alta — manchetes + descrições | 1-2s |
| **GNews API** | $0 (100 req/dia) | 100/dia | Média — headlines apenas | 0.5-1s |
| **RSS Feeds** (Globo Esporte, ESPN) | $0 | Ilimitado | Variável — depende do portal | 0.5-2s |
| **Google News RSS** | $0 | Ilimitado | Média — headlines sem corpo | 0.5-1s |

**Recomendação:** Tavily Search API como primeira opção (gratuito, feito para LLM, resume automaticamente). DuckDuckGo como fallback gratuito ilimitado.

**Custo operacional estimado:**
- 50 partidas/dia × 30 dias = 1500 pesquisas/mês → Tavily grátis cobre 1000, excedente ~$0.01/search ≈ $5/mês
- Alternativa: pesquisar apenas jogos na Zona Alvo (1.60-2.20) → ~15 pesquisas/dia = 450/mês → grátis

### 3.3 News APIs Esportivas

| Fonte | Cobertura | Custo |
|-------|-----------|-------|
| **API-Football `fixtures/{id}/events`** | Pós-jogo: gols, cartões, substituições | $0 (já incluso) |
| **API-Football `teams/{id}/statistics`** | Estatísticas agregadas por temporada | $0 (já incluso) |
| **TheSportsDB** | Lineups, eventos, tabelas | Grátis (100 req/dia) |
| **OpenLigaDB** | Dados de ligas europeias | Grátis |

**Conclusão:** Para notícias de desfalques de última hora, melhor usar web search. APIs esportivas cobrem dados estruturados, não notícias.

### 3.4 Web Scraping de Dados Estruturados — Desenvolvimento Futuro (Pós-MVP)

> **Status:** 🧪 OPÇÃO LEVANTADA — NÃO implementar. Registrada para avaliação futura.

Como alternativa à API-Football PRO ($40/mês) para obter standings da temporada atual, o web scraping de portais esportivos públicos foi considerado:

| Fonte | Dados Disponíveis | Complexidade | Risco Legal | Robustez |
|-------|-------------------|-------------|-------------|----------|
| **Soccerway** | Tabelas completas, forma (W/D/L), próximos jogos, H2H | Média — HTML estruturado, sem API pública | Baixo-médio (dados públicos) | Alta — estrutura estável |
| **Flashscore** | Standings, forma recente, H2H, escalações, estatísticas do jogo | Alta — HTML dinâmico, carregamento JS | Baixo-médio (dados públicos) | Média — mudanças ocasionais de layout |
| **SofaScore** | Standings, médias por time (cantos, gols, cartões), H2H | Alta — fortemente dinâmico, anti-bot | Médio — ToS restritivo | Baixa — requer Selenium/Playwright |
| **WhoScored** | Estatísticas avançadas (xG, posses, pressão) | Alta — anti-bot agressivo | Alto — dados licenciados da Opta | Muito baixa |

**Recomendação para o futuro:**
- **Soccerway** como primeira opção de scraping — HTML semântico, estrutura previsível, baixo risco
- **Flashscore** como fallback — mais dados, mas requer parsing mais complexo
- **NÃO scrapear SofaScore ou WhoScored** — risco legal e técnico elevados

**Estimativa de esforço futuro:**
- Soccerway scraper: 3-5 dias (parser HTML + extração de standings + cache)
- Flashscore scraper: 5-8 dias (requer headless browser para JS rendering)
- Manutenção contínua: ~2-4h/mês (ajustes de layout quando os sites mudam)

**Pré-requisitos para considerar esta rota:**
1. Volume de apostas justifique o custo de manutenção (estimado: >20 entradas/mês)
2. API-Football PRO descartada por custo ou limitação de cobertura
3. Jurisdição local permita web scraping de dados públicos esportivos

**Conclusão:** Manter como opção de médio/longo prazo. A correção da FASE 0 (05-MAI-2026) remove o fallback para dados velhos e aceita `standings: null`, o que é suficiente para o MVP atual. O web scraping só se justifica quando o volume de operação exigir standings da temporada corrente como diferencial competitivo.

---

## 4. RAG / Knowledge Store — Tecnologias

### 4.1 Comparação de Backends

| Tecnologia | Custo | Complexidade | Persistência | Embeddings |
|-----------|-------|-------------|-------------|------------|
| **SQLite + numpy** (manual) | $0 | Média — 200-300 linhas | ✅ Arquivo único | Manual (sentence-transformers) |
| **ChromaDB** (open source) | $0 | Baixa — API simples | ✅ Diretório local | Integrado (all-MiniLM-L6-v2) |
| **FAISS** (Meta) | $0 | Média-alta — C++ bindings | ✅ Índice em disco | Externo (sentence-transformers) |
| **LanceDB** | $0 | Baixa — embedded, sem servidor | ✅ Arquivo único | Integrado |
| **Pinecone** (cloud) | ~$70/mês | Baixa — API gerenciada | ✅ Cloud | Integrado |
| **Qdrant** (self-hosted) | $0 (Docker) | Média — precisa de container | ✅ Docker volume | Integrado |
| **Weaviate** (self-hosted) | $0 (Docker) | Alta — schema complexo | ✅ Docker volume | Integrado |

### 4.2 Recomendação

**LanceDB** como primeira escolha:
- Embedded (sem servidor, sem Docker)
- API Python simples, similar a pandas
- Suporte nativo a filtros por metadata (essencial para "buscar veredictos do mesmo time")
- Persiste em arquivo único (como SQLite)
- Embeddings via `sentence-transformers` (all-MiniLM-L6-v2, 80MB, rápido em CPU)

**Fallback:** ChromaDB — mais maduro, comunidade maior, mas requer diretório separado para persistência.

### 4.3 Coleções Propostas

| Coleção | Conteúdo | Embedding de | Metadados |
|---------|----------|-------------|-----------|
| `veredicts` | Veredictos passados do Gatekeeper | `justification` (texto) | status, market, odd, home_team, away_team, resultado_real |
| `referee_profiles` | Perfis de árbitros | `name + resumo estatístico` | avg_fouls, avg_cards, avg_corners |
| `team_profiles` | Comportamentos táticos | `descrição de perfil` | league, season |
| `match_contexts` | Cache de contexto dos últimos 7 dias | `home_team + away_team` | data, fixture_id |

### 4.4 Modelo de Embedding

**`sentence-transformers/all-MiniLM-L6-v2`** (80 MB):
- 384 dimensões
- Rápido em CPU (~100 docs/segundo)
- Suporte multilíngue moderado (inglês melhor que português)
- Alternativa multilíngue: `paraphrase-multilingual-MiniLM-L12-v2` (470 MB, melhor para português)

**Custo:** $0 (modelos open source, execução local)

---

## 5. Análise de Custo/Benefício por Item

### 5.1 ENR.3 — Árbitro no MatchContext ⭐ QUICK WIN

| Critério | Avaliação |
|----------|----------|
| **Esforço estimado** | 2-4 horas |
| **Requisições API extras** | **ZERO** — dado já trafega no `fixtures` response |
| **Impacto no prompt** | +50-80 caracteres por partida (nome do árbitro + stats) |
| **Valor para decisão** | ALTO — Pilar 3 da validação fica funcional |
| **Risco** | Baixíssimo — apenas extrair campo existente |
| **Dependências** | Nenhuma |
| **Custo mensal** | $0 |

**Ação:** Adicionar `referee_info` ao response do `get_fixtures_today()` + popular `MatchContext.referee` no `collect_upcoming()` e `enrich_pre_match_contexts()`.

### 5.2 ENR.4 — H2H Recente no MatchContext

| Critério | Avaliação |
|----------|----------|
| **Esforço estimado** | 4-6 horas |
| **Requisições API extras** | +1 por partida (`fixtures/headtohead`) |
| **Impacto no prompt** | +100-200 caracteres por partida |
| **Valor para decisão** | ALTO — Análise 1x2 e Over/Under dependem disso |
| **Risco** | Médio — pode consumir muitas requisições no plano free |
| **Dependências** | ENR.3 (mesmo loop de fixtures) |
| **Custo mensal** | $0 (free tier) se ≤50 partidas/dia com otimização |

**Otimização:** Para reduzir chamadas, fazer `fixtures/headtohead` apenas para partidas na Zona Alvo (1.60–2.20) + Zona de Composição (1.25–1.59). Ignorar Zona Morta.

### 5.3 ENR.5 — The Scout (Pesquisa Web)

| Critério | Avaliação |
|----------|----------|
| **Esforço estimado** | 8-12 horas |
| **Requisições API extras** | 1 pesquisa web por partida na Zona Alvo |
| **Impacto no prompt** | +300-500 caracteres por partida |
| **Valor para decisão** | MÉDIO-ALTO — desfalques de última hora e notícias |
| **Risco** | Médio — latência extra (1-3s), dados não estruturados |
| **Dependências** | ENR.1 (define tecnologia), ENR.2 (cache para evitar repetir) |
| **Custo mensal** | $0-5 (Tavily free tier ou DuckDuckGo gratuito) |

### 5.4 ENR.2 — Knowledge Store (RAG)

| Critério | Avaliação |
|----------|----------|
| **Esforço estimado** | 12-20 horas |
| **Requisições API extras** | ZERO |
| **Impacto no prompt** | +200-400 caracteres por partida (apenas contexto relevante) |
| **Valor para decisão** | ALTO — aprendizado com erros passados |
| **Risco** | Médio — implementação nova, embeddings locais |
| **Dependências** | Nenhuma (módulo independente) |
| **Custo mensal** | $0 |

---

## 6. Recomendação de Implementação Faseada

### Fase 1 — Quick Wins + Correções (6-10 horas, custo $0)

**⚠️ Item 0 — Correção Imediata (30 min)**
- **Remover fallback 2024 dos standings:** Substituir fallback por `None` em [`context_collector.py`](src/japredictbet/data/context_collector.py:528-540) nos métodos `collect_upcoming()` e `enrich_pre_match_contexts()`. Dados de 2024 são piores que ausência de dados — induzem o LLM a erro.
- **Atualizar `to_llm_context()`:** Confirmar que `home_standing: null` e `away_standing: null` são serializados corretamente (atualmente o método `_slim_standing` retorna `None` e só adiciona ao payload se não for None — ok).
- **Atualizar PROMPT_MESTRE.md:** Adicionar instrução para tratar `standing: null` como "dados de tabela indisponíveis para a temporada atual — não usar tabela como fator de decisão".

**Ordem de execução:**
1. **ENR.3 — Árbitro (2-4h):** Extrair `referee` do response de `fixtures`, popular `RefereeInfo`, injetar no prompt. Custo zero em API.
2. **ENR.4 — H2H (2-4h, após ENR.3):** Adicionar `get_h2h()` no `ApiFootballClient`, novo campo `MatchContext.h2h`, serializar no `to_llm_context()`.

**Resultado esperado:** Dados da temporada atual (ou ausência explícita) + Pilar 3 (Arbitragem) funcional + análise 1x2 com histórico real. Os 3 maiores gaps resolvidos.

### Fase 2 — Knowledge Store (12-20 horas, custo $0)

**Ordem de execução:**
1. **ENR.2 — Knowledge Store:** Implementar `data/knowledge_store.py` com LanceDB + `sentence-transformers`.
2. Integrar ao `GatekeeperAgent` para buscar contexto relevante antes da chamada LLM.
3. Popular com veredictos à medida que o pipeline roda.

**Resultado esperado:** Gatekeeper "lembra" de erros passados, melhora progressivamente.

### Fase 3 — The Scout (8-12 horas, custo $0-5/mês)

**Ordem de execução:**
1. **ENR.5 — The Scout:** Implementar `data/web_scout.py` com Tavily API (ou DuckDuckGo fallback).
2. Integrar ao pipeline: disparar pesquisa apenas para jogos na Zona Alvo.
3. Cache de 6h para evitar pesquisas repetidas do mesmo jogo.

**Resultado esperado:** Contexto externo (desfalques de última hora, clima, notícias) injetado no prompt.

### Fase 4 — Refinamento Contínuo

- A/B test: medir precisão do Gatekeeper com vs sem cada fonte de enriquecimento
- Ajustar peso de cada fonte no prompt baseado em resultados
- Expandir coleções do Knowledge Store (team_profiles, condições climáticas)

---

## 7. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|-------------|---------|-----------|
| **Standings com dados de 2024 (já em produção!)** | **CERTEZA** (código ativo) | **ALTO — Gatekeeper decide com tabela errada** | **Remover fallback 2024 imediatamente**; usar `None` quando temporada atual indisponível |
| **Rate limit API-Football** | ALTA (free tier já no limite) | Pipeline quebra sem enriquecimento | Otimizar chamadas (inline referee, H2H seletivo); plano PRO se necessário |
| **Token bloat no prompt** | MÉDIA | Custo LLM sobe, latency aumenta | Compactar contexto; só injetar o essencial; `to_llm_context()` já faz slim |
| **Alucinação do LLM com dados novos** | BAIXA | Análise incorreta | Dados factuais (árbitro, H2H) não deveriam causar alucinação |
| **Falso positivo em fuzzy match de H2H** | MÉDIA | Dado incorreto no prompt | Usar fixture_id (numérico) em vez de fuzzy match sempre que possível |
| **Pesquisa web irrelevante** | MÉDIA | Prompt poluído com ruído | Filtrar por relevância; template de query específico; max 3 resultados |
| **Embeddings consomem RAM** | BAIXA | Performance | all-MiniLM-L6-v2 usa ~80MB; aceitável |
| **Dados do Knowledge Store desatualizados** | BAIXA | Recomendação baseada em contexto velho | TTL por coleção; invalidar após 30 dias |

---

## 8. Métricas de Sucesso

Após implementação de cada fase, medir:

1. **Cobertura de contexto:** % de partidas com referee, H2H, external_research populados
2. **Precisão do Gatekeeper:** taxa de acerto dos mercados aprovados (requer shadow log com resultados reais)
3. **Redução de NO BET por "informação insuficiente":** quantas partidas deixam de ser rejeitadas por falta de dados
4. **Latência do pipeline:** tempo total de coleta + enriquecimento + avaliação LLM
5. **Custo por partida avaliada:** tokens LLM + chamadas API externas

---

## 9. Conclusão

O enriquecimento de contexto é o **maior multiplicador de qualidade** disponível para o Gatekeeper atualmente. O custo é baixo (majoritariamente $0) e o esforço de implementação é moderado.

**Prioridade máxima:** ENR.3 (Árbitro) — Quick Win de 2-4 horas com custo zero e alto impacto. O dado já está disponível no response da API-Football, apenas não está sendo extraído.

**Próximo passo:** ENR.4 (H2H) — complementa a análise 1x2 que o prompt já solicita mas não recebe.

**Investimento futuro:** ENR.2 (Knowledge Store) — transforma o Gatekeeper de um avaliador stateless para um sistema que aprende continuamente.

---

## Apêndice A — Exemplo de Response da API-Football `fixtures`

```json
{
  "fixture": {
    "id": 123456,
    "referee": "Wilton Pereira Sampaio",
    "timezone": "UTC",
    "date": "2026-05-04T19:00:00+00:00",
    "timestamp": 1746399600,
    "status": { "long": "Not Started", "short": "NS", "elapsed": null }
  },
  "league": {
    "id": 71,
    "name": "Serie A",
    "country": "Brazil",
    "season": 2026
  },
  "teams": {
    "home": { "id": 121, "name": "Flamengo" },
    "away": { "id": 135, "name": "Palmeiras" }
  }
}
```

**Campo `referee` já presente na linha `fixture.referee` — nenhuma chamada extra necessária.**

## Apêndice B — Exemplo de Response da API-Football `fixtures/headtohead`

```json
{
  "response": [
    {
      "fixture": { "id": 111111, "date": "2025-11-15T..." },
      "teams": { "home": { "name": "Flamengo" }, "away": { "name": "Palmeiras" } },
      "goals": { "home": 2, "away": 1 },
      "score": { "halftime": { "home": 1, "away": 0 } }
    },
    ...
  ]
}
```

**Dados extraíveis por partida:** placar, gols 1T, mandante/visitante, data. Para escanteios, seria necessário endpoint adicional (`fixtures/{id}/statistics`).
