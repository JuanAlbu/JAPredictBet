# JA PREDICT BET - Fluxo de Execucao Diaria

Atualizado: 12-APR-2026

## Rotina Diaria (2 comandos)

1. `python scripts/superbet_scraper.py hoje` -> coleta odds
2. `python scripts/shadow_observe.py --pre-match hoje` -> avalia jogos

Variacoes do scraper:

```bash
python scripts/superbet_scraper.py amanha
python scripts/superbet_scraper.py 2026-04-13
python scripts/superbet_scraper.py hoje --quick
python scripts/superbet_scraper.py hoje --all-markets --json
```

Variacoes do shadow:

```bash
python scripts/shadow_observe.py --pre-match hoje --dry-run
python scripts/shadow_observe.py --pre-match hoje --verbose
python scripts/shadow_observe.py
```

Observacoes:

- `--dry-run`: roda sem API key
- sem `--pre-match`: modo live T-60

## Fluxo Completo - Passo a Passo

### Step 1 - Coleta de Odds (Scraper)

- Conecta ao SSE Superbet (30s de stream)
- Captura eventos de futebol com mercados: corners, 1x2, BTTS
- Output: `data/odds/pre_match/YYYY-MM-DD.json`
- Conteudo por evento: `event_id`, times, kickoff, odds por mercado

### Step 2 - Conversao para MatchContext

- JSON bruto -> objetos tipados (`MatchContext`)
- Odds organizadas por mercado (`corners`, `1x2`, `BTTS`)
- Pre-match: apenas odds disponiveis
- Live T-60: odds + escalacoes + lesoes + standings (`API-Football`)

### Step 3 - Consensus Engine (corners only, por jogo)

- Feature Store -> 106+ stats por time (`rolling mean`, `STD`, `EMA`, `H2H`, `ELO`)
- 30 modelos preveem lambda (esperado de escanteios por time)
- Ensemble:
  - 11 XGBoost
  - 10 LightGBM
  - 5 Ridge
  - 4 ElasticNet
- Objetivo Poisson, arquitetura `two-model` (`home` + `away`)

Para cada modelo:

- `lambda_total = lambda_home + lambda_away`
- Poisson CDF -> probabilidade de over/under a linha
- `edge = p_modelo - p_implied (1/odds)`
- Voto: `edge >= 0.05` -> vota `SIM`

Agregacao dos 30 votos:

- `consensus_pct = votos_sim / 30`
- Dynamic margin rule:
  - margem `< 0.5` -> threshold apertado (`50%`)
  - margem `>= 0.5` -> threshold base (`45%`)
- Decisao: `consensus_pct >= threshold` -> `BET`

Output:

- `consensus_pct`
- `edge_mean`
- lambda medio
- `bet=true/false`

### Step 4 - Gatekeeper Agent (LLM, corners + consensus)

Mercado: Escanteios Over/Under

- Pre-filtro Python: `best_odd < 1.60` -> `FILTERED` (sem chamada LLM)
- LLM: `gpt-4o-mini`, `temp=0.3`

Entrada do LLM:

- `MatchContext` completo (times, odds, contexto)
- Output do ensemble (lambda, `consensus_pct`, edge, votos)
- Prompt: `PROMPT_MESTRE V25`

Saida do LLM:

- `status`: `APPROVED` ou `NO BET`
- `stake`: `0.5`, `1.0` ou `2.0`
- `market`: ex. `Escanteios Over 9.5`
- `edge`: Alto / Medio / Baixo
- `justification`: razao textual
- `red_flags`: riscos identificados

### Step 5 - Analyst Agent (LLM, mercados complementares)

Mercados: `1x2`, `BTTS`, `Over/Under Goals`

- Nao usa ensemble (analise puramente qualitativa via LLM)
- Pre-filtro Python: nenhuma odd `> min_odd` -> `FILTERED`
- LLM: `gpt-4o-mini`

Entrada do LLM:

- `MatchContext` sem consensus
- Prompt: `PROMPT_ANALYST V1`

Saida do LLM:

- lista de `MarketEvaluation` (`status`, `stake`, `odd`, `edge`, justificativa)
- `best_pick`: melhor oportunidade identificada

### Step 6 - Capping + Log + Summary

- Max 5 entradas `APPROVED` por dia (excedentes -> `CAPPED`)
- Shadow log gravado em `logs/shadow_bets.log` (`JSONL`, append)
- Resumo visual no console com status por jogo

## Dois Modos Operacionais - Quando Usar Cada

| Item | Pre-match | Live T-60 |
| --- | --- | --- |
| Quando | Horas antes dos jogos | 60min antes do kickoff |
| Comando | `--pre-match hoje` | sem flag `--pre-match` |
| Odds | JSON do scraper (REST) | SSE stream real-time |
| Contexto | Apenas odds | + escalacoes, lesoes, standings (`API-Football`) |
| Uso tipico | Rotina diaria padrao | Refinamento com dados ao vivo |
| API keys | `OPENAI_API_KEY` | `OPENAI_API_KEY` + `API_FOOTBALL_KEY` |

## Dois Agentes LLM - O Que Cada Um Faz

| Item | Gatekeeper | Analyst |
| --- | --- | --- |
| Mercado | Escanteios (Over/Under) | `1x2`, `BTTS`, `O/U Goals` |
| Usa ensemble? | Sim (30 modelos Poisson) | Nao (qualitativo) |
| Decisao | Estatistica + LLM | LLM puro |
| Output | 1 resultado por jogo | Lista de mercados + best pick |
| Prompt | `PROMPT_MESTRE V25` | `PROMPT_ANALYST V1` |
| Modelo LLM | `gpt-4o-mini (temp=0.3)` | `gpt-4o-mini` |

## Tipos de Resposta por Jogo

- `APPROVED`: aposta recomendada (`stake 0.5 / 1.0 / 2.0`)
- `NO BET`: LLM avaliou e rejeitou (sem value suficiente)
- `FILTERED`: pre-filtro Python descartou (odd abaixo do minimo)
- `CAPPED`: passou nos criterios, mas limite diario (5) foi atingido
- `DRY_RUN`: teste local sem LLM (`--dry-run`)
- `ERROR`: falha na chamada LLM ou no parsing da resposta

## Exemplo de Output no Console

```text
============================================================
SHADOW OBSERVATION SUMMARY
============================================================
  Mode:              pre-match
  Run at:            2026-04-13T15:45:22+00:00
  Matches collected: 15
  Matches evaluated: 14
  Entries approved:  3
------------------------------------------------------------
  [OK] Arsenal vs Chelsea     | APPROVED | stake=1.0 | consensus=67%
       -> Strong consensus + favorable matchup
  [INFO] Analyst: APPROVED    | 1/3 mercados | Best: 1x2 HOME @ 1.50

  [OK] Man City vs Fulham     | APPROVED | stake=0.5 | consensus=60%
       -> Moderate edge, limited consensus support
  [INFO] Analyst: NO BET      | 0/3 mercados

  [X] Liverpool vs Brighton   | NO BET   | consensus=40%
      -> Consensus threshold not met (40% < 45%)

  [!] Brentford vs Newcastle  | FILTERED | stake=None
      -> Best odd 1.55 < minimum 1.60
------------------------------------------------------------
  Shadow log: logs/shadow_bets.log
```

## Artefatos Gerados

| Arquivo | Conteudo |
| --- | --- |
| `data/odds/pre_match/YYYY-MM-DD.json` | Snapshot de odds do dia (scraper) |
| `logs/shadow_bets.log` | JSONL com todas as avaliacoes (append) |
| `artifacts/feature_store.parquet` | Features pre-computadas (106+ por time) |
| `artifacts/models/*.pkl` | 30 modelos treinados (ensemble) |

## Manutencao Periodica

| Frequencia | Comando | Proposito |
| --- | --- | --- |
| Semanal | `python scripts/refresh_features.py --config config.yml` | Atualizar Feature Store com novos dados |
| Mensal | `python run.py --config config.yml` | Retreinar ensemble com dados recentes |
| Sob demanda | `python scripts/hyperopt_search.py --config config.yml --algorithm all --n-trials 50` | Otimizar hiperparametros |

## Nota de Seguranca

Este sistema e estritamente uma ferramenta de `ANALYTICS`.

- Nenhum modulo executa apostas reais.
- O shadow mode e puramente observacional.
- O objetivo e registrar recomendacoes para posterior validacao de acuracia e calibracao.
