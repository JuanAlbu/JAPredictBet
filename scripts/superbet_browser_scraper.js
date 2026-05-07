// ======================================================================
//  FERRAMENTA AUXILIAR DE DEBUG — NÃO FAZ PARTE DO FLUXO AUTOMATIZADO
// ======================================================================
//
// ⚠️  Este script NÃO é usado pelo pipeline de produção.
//
// O fluxo principal do JAPredictBet é:
//   scripts/superbet_scraper.py  →  Playwright + REST API  →  JSON snapshot
//       └── src/japredictbet/pipeline/gatekeeper_live_pipeline.py  →  LLM + log
//
// Este JS é uma ferramenta de diagnóstico rápido para uso MANUAL no
// console do navegador (F12).  Útil para:
//   • Verificar rapidamente quantos jogos estão na página (sem rodar o scraper Python)
//   • Debug de DOM quando o Playwright não acha eventos que você vê na tela
//   • Descoberta de novos TIDs (tournament IDs) que não estão no mapeamento
//   • Validar se mudanças no site quebraram os seletores do scraper Python
//
// NÃO cole este script esperando que ele alimente o pipeline — ele
// apenas imprime no console.  O pipeline consome os snapshots JSON
// gerados pelo superbet_scraper.py.
// ======================================================================
//
// == Superbet Event Scraper (CORRIGIDO v3) ==
// Cole no console do navegador em: https://superbet.bet.br/apostas/futebol?day=...
//
// Correções aplicadas:
//  1. Duplicação: agora itera sobre TODOS os <a> links de odds (1 link = 1 evento).
//     Deduplica por eventId ao final.
//  2. Times com \n: extrai do slug da URL (liverpool-x-chelsea-12025321) como
//     estratégia primária. Fallback: split do textContent por \n.
//  3. Containers de grupo (3-part: offer-prematch-TID-eid1-eid2): agora captura
//     os links internos via querySelectorAll no container mais próximo.
//  4. Regex corrigido para times com hífen (ex: Newcastle-United, West-Ham).
//     Usa (.+) greedy com backtrack em vez de ([^\-]+).
//  5. Log de diagnóstico: mostra links pulados e o motivo, facilitando debug.

(function () {
  const rows = [];
  const skipped = []; // diagnóstico: links pulados

  // ── Estratégia: encontra TODOS os links de evento ─────────────────
  // Cada <a href="/odds/futebol/slug-x-slug-EVENTID"> representa 1 evento.
  // Funciona tanto em containers 2-part (evento único) quanto 3-part (grupo).
  const links = document.querySelectorAll('a[href*="/odds/futebol/"]');

  links.forEach(function (link) {
    const href = link.getAttribute("href");

    // Extrai eventId e nomes dos times do slug da URL
    // Formato: /odds/futebol/time-casa-x-time-fora-EVENTID
    // Usa (.+) greedy que faz backtrack para capturar times com hífen
    const slugMatch = href.match(
      /\/odds\/futebol\/(.+)-x-(.+)-(\d{5,})(?:\/|\?|#|$)/
    );
    if (!slugMatch) {
      skipped.push({ href: href, reason: "regex_slug_nao_casou" });
      return;
    }

    const eventId = slugMatch[3];
    const mandante = slugMatch[1]
      .split("-")
      .map(function (w) {
        return w.charAt(0).toUpperCase() + w.slice(1);
      })
      .join(" ");
    const visitante = slugMatch[2]
      .split("-")
      .map(function (w) {
        return w.charAt(0).toUpperCase() + w.slice(1);
      })
      .join(" ");

    // ── Extrai TID do container offer-prematch mais próximo ─────────
    // Sobe na árvore DOM até achar [id^="offer-prematch-"]
    let tid = "";
    let el = link;
    while (el) {
      if (el.id && el.id.startsWith("offer-prematch-")) {
        const tidMatch = el.id.match(/^offer-prematch-(\d+)/);
        if (tidMatch) {
          tid = tidMatch[1];
        }
        break;
      }
      el = el.parentElement;
    }

    // ── Extrai horário ──────────────────────────────────────────────
    // Procura .event__time no container do evento (sobe até achar ou
    // busca lateralmente no mesmo nível do link)
    let horario = "";
    const eventRow = link.closest('[class*="event"]');
    if (eventRow) {
      const timeEl =
        eventRow.querySelector(".event__time") ||
        eventRow.querySelector('[class*="time"]');
      if (timeEl) {
        horario = timeEl.textContent.trim();
      }
    }

    // ── Extrai nome da liga ─────────────────────────────────────────
    // Estratégia em 3 níveis: tenta sport-events-list primeiro,
    // depois sobe até qualquer section/div com header, por último
    // busca o accordion/group wrapper
    let liga = "";
    const section = link.closest('[class*="sport-events-list"]');
    if (section) {
      const header = section.querySelector(
        '.sport-events-list__header, [class*="header"], h2, h3'
      );
      if (header) {
        liga = header.textContent.trim();
      }
    }
    // Fallback: busca accordion/group (ex: league-container)
    if (!liga) {
      const accordion = link.closest(
        '[class*="accordion"], [class*="league"], [class*="competition"], [class*="championship"]'
      );
      if (accordion) {
        const accordionHeader = accordion.querySelector(
          '[class*="header"], [class*="title"], [class*="name"], h2, h3, h4, button'
        );
        if (accordionHeader) {
          liga = accordionHeader.textContent.trim();
        }
      }
    }

    rows.push({
      eventId: eventId,
      tid: tid,
      mandante: mandante,
      visitante: visitante,
      horario: horario,
      liga: liga,
    });
  });

  // ── Remove duplicatas por eventId (mantém a primeira ocorrência) ──
  const uniqueRows = [];
  const seen = new Set();
  rows.forEach(function (row) {
    if (!seen.has(row.eventId)) {
      seen.add(row.eventId);
      uniqueRows.push(row);
    }
  });

  // ── Diagnóstico ──────────────────────────────────────────────────
  console.log("═══════════════════════════════════════════");
  console.log("  DIAGNÓSTICO DO SCRAPER");
  console.log("═══════════════════════════════════════════");
  console.log("Total de links <a> com '/odds/futebol/': " + links.length);
  console.log("Eventos capturados com sucesso: " + rows.length);
  console.log("Duplicatas removidas: " + (rows.length - uniqueRows.length));
  console.log(
    "Links pulados (regex não casou): " + skipped.length
  );
  if (skipped.length > 0) {
    console.log("\n── LINKS PULADOS (investigar) ──");
    console.table(skipped);
  }
  console.log("\n── EVENTOS FINAIS ──");
  console.table(uniqueRows);

  // ── Exporta como CSV ─────────────────────────────────────────────
  const csv =
    "eventId;tid;mandante;visitante;horario;liga\n" +
    uniqueRows
      .map(function (r) {
        return [
          r.eventId,
          r.tid,
          r.mandante,
          r.visitante,
          r.horario,
          r.liga,
        ].join(";");
      })
      .join("\n");

  console.log("\n--- CSV ---");
  console.log(csv);

  // Copia para clipboard
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(csv).then(
      function () {
        console.log("CSV copiado para a área de transferência!");
      },
      function () {
        console.log(
          "Não foi possível copiar para clipboard. Copie manualmente acima."
        );
      }
    );
  }

  return uniqueRows;
})();
