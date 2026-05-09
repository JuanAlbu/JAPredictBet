# JA PREDICT BET - Fluxo de Execucao Diaria

Atualizado: 09-MAY-2026

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

### Step 3 - Gatekeeper Agent (LLM unificado, TODOS os mercados)

- Pre-filtro Python (scraper/pipeline): market whitelist (corners, 1x2, BTTS, O/U Gols) + filtro por seleção antes da LLM
- `odd < 1.25`: removida do payload LLM (ZONA MORTA)
- `1.25 <= odd < 1.60`: só entra como `PERNA DE COMPOSIÇÃO`, sem stake e sem elegibilidade para `best_pick`
- `1.60 <= odd <= 2.20`: candidata a aposta simples
- `odd > 2.20`: candidata de variância com stake máxima `0.5u`
- Pós-LLM: guarda determinístico reclassifica qualquer violação restante da matriz de odds
- LLM: Prompt Mestre V26, `temp=0.3`

Entrada do LLM:

- `MatchContext` completo (times, odds, contexto situacional)
- NÃO inclui output de ensemble (30-model ensemble = exclusivo do Mode 1 Backtest)
- Prompt: `PROMPT_MESTRE.md` V26 (multi-mercado)

Saida do LLM:

- `markets[]`: array de `MarketEvaluation` (corners, 1x2, BTTS, O/U Gols, 1º Tempo)
- Cada mercado: `status`, `stake`, `odd`, `edge`, `classification`, `justification`, `red_flags`
- `best_pick`: melhor oportunidade global identificada

### Step 4 - Capping + Log + Summary

- Max 5 entradas `APPROVED` por dia (excedentes -> `CAPPED`)
- Shadow log gravado em `logs/shadow_bets.log` (`JSONL`, append)
- Resumo visual no console com status por jogo e mercados aprovados

## Dois Modos Operacionais - Quando Usar Cada

| Item | Pre-match | Live T-60 |
| --- | --- | --- |
| Quando | Horas antes dos jogos | 60min antes do kickoff |
| Comando | `--pre-match hoje` | sem flag `--pre-match` |
| Odds | JSON do scraper (REST) | SSE stream real-time |
| Contexto | Apenas odds | + escalacoes, lesoes, standings (`API-Football`) |
| Uso tipico | Rotina diaria padrao | Refinamento com dados ao vivo |
| API keys | `OPENAI_API_KEY` | `OPENAI_API_KEY` + `API_FOOTBALL_KEY` |

## Agente LLM Unificado — O Que Faz

| Item | GatekeeperAgent (V26) |
| --- | --- |
| Mercados | TODOS: Escanteios, 1x2, BTTS, Over/Under Gols, 1º Tempo |
| Usa ensemble? | Nao (30-model ensemble = exclusivo do Mode 1 Backtest) |
| Decisao | LLM puro (context-driven, Prompt Mestre V26) |
| Output | Array de `MarketEvaluation` + `best_pick` global |
| Prompt | `PROMPT_MESTRE.md` V26 (multi-mercado) |
| Modelo LLM | `gpt-4o-mini (temp=0.3)` |

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
  Run at:            2026-05-03T15:45:22+00:00
  Matches collected: 15
  Matches evaluated: 14
  Entries approved:  3
------------------------------------------------------------
  [OK] Arsenal vs Chelsea     | APPROVED | 2/5 mercados
       -> Best: Escanteios Over 9.5 | APOSTA SIMPLES | stake=1.0
       -> Tambem: BTTS SIM | PERNA DE COMPOSIÇÃO | stake=None

  [OK] Man City vs Fulham     | APPROVED | 1/5 mercados
       -> Best: 1x2 HOME | APOSTA SIMPLES | stake=0.5

  [X] Liverpool vs Brighton   | NO BET   | 0/5 mercados
      -> Gatekeeper rejeitou: escalação incerta, odds baixas

  [!] Brentford vs Newcastle  | FILTERED | stake=None
      -> Nenhuma seleção elegível após filtro pré-LLM
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
