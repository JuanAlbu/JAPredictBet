"""Painel de operacao — JAPredictBet (v2.0 — Revisao 08-MAI-2026).

Cockpit enxuto com 6 opcoes que respeitam a arquitetura real do sistema:
- O Shadow Mode usa APENAS o Gatekeeper LLM (Prompt Mestre V26).
- O ML Ensemble (30 modelos) e exclusivo do Mode 1 (Backtest).
- Nenhum agente executa apostas reais — 100% observacional.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ── Helpers ────────────────────────────────────────────────────────────


def _root() -> Path:
    """Raiz do projeto (um nivel acima de scripts/)."""
    return Path(__file__).resolve().parent.parent


def limpar_ecra() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _pausa() -> None:
    input("\nPressione ENTER para voltar ao menu...")


# ── Selecao de dia ─────────────────────────────────────────────────────


def escolher_dia() -> tuple[str, str, str]:
    """Pergunta se a operacao sera para hoje ou amanha.

    Returns:
        (rotulo_ui, arg_scraper, arg_shadow)
          - rotulo_ui:       "HOJE" | "AMANHA / SEXTA"
          - arg_scraper:     "hoje" | "sexta" | YYYY-MM-DD
          - arg_shadow:      "hoje" | "amanha" | YYYY-MM-DD
    """
    _dias_pt = [
        "segunda",
        "terca",
        "quarta",
        "quinta",
        "sexta",
        "sabado",
        "domingo",
    ]

    print("\nQual o dia da operacao?")
    print("[1] Hoje")
    print("[2] Amanha")
    opcao = input("Selecione (padrao: Hoje): ").strip()

    if opcao == "2":
        amanha = datetime.now() + timedelta(days=1)
        nome_dia = _dias_pt[amanha.weekday()]
        data_iso = amanha.strftime("%Y-%m-%d")
        return (f"AMANHA / {nome_dia.upper()}", nome_dia, data_iso)

    return ("HOJE", "hoje", "hoje")


# ── Selecao de escopo do scraper ───────────────────────────────────────


def escolher_escopo() -> tuple[str, bool]:
    """Pergunta o escopo de mercados para o scraper.

    Returns:
        (rotulo, apenas_resultado_final)
    """
    print("\nEscopo de mercados para o scraper:")
    print("[1] Todos os mercados (completo — ~90s de streaming)")
    print("[2] Apenas Resultado Final (rapido)")
    opcao = input("Selecione (padrao: Todos os mercados): ").strip()

    if opcao == "2":
        return ("APENAS RESULTADO FINAL", True)
    return ("TODOS OS MERCADOS", False)


# ── Execucao de comandos ───────────────────────────────────────────────


def _mostrar_saida(resultado: subprocess.CompletedProcess[str]) -> None:
    if resultado.stdout:
        print(resultado.stdout.strip())


def _mostrar_erro(
    resultado: subprocess.CompletedProcess[str],
    descricao: str,
) -> None:
    print(f"\n[ERRO] Falha durante: {descricao}")
    if resultado.stderr:
        linhas = [ln for ln in resultado.stderr.strip().splitlines() if ln.strip()]
        if linhas:
            print("\nResumo do erro:")
            for line in linhas[-12:]:
                print(line)


def _executar(
    comando: list[str],
    descricao: str,
    *,  # <-- Forca keyword-only nos parametros seguintes
    verbose: bool = False,
) -> int:
    """Executa um comando externo. Retorna o codigo de saida."""
    print(f"\n[INICIANDO] {descricao}...")
    print("-" * 50)

    try:
        if verbose:
            # Em modo verbose, deixa stdout/stderr fluir para o terminal
            resultado = subprocess.run(
                comando,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
        else:
            resultado = subprocess.run(
                comando,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
    except KeyboardInterrupt:
        print("\n[AVISO] Operacao cancelada pelo utilizador.")
        print("-" * 50)
        _pausa()
        return 130  # 128 + SIGINT

    if resultado.returncode == 0:
        if not verbose:
            _mostrar_saida(resultado)
        print(f"\n[OK] {descricao} concluido com sucesso.")
    else:
        if not verbose:
            _mostrar_saida(resultado)
        _mostrar_erro(resultado, descricao)

    print("-" * 50)
    return resultado.returncode


def _executar_encadeado(
    etapas: list[tuple[list[str], str]],
    verbose: bool = False,
) -> bool:
    """Executa comandos em sequencia. Para no primeiro erro. Retorna True se tudo ok."""
    try:
        for comando, descricao in etapas:
            print(f"\nExecutando: {descricao}")
            if verbose:
                resultado = subprocess.run(
                    comando,
                    check=False,
                    encoding="utf-8",
                    errors="replace",
                )
            else:
                resultado = subprocess.run(
                    comando,
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            if resultado.returncode != 0:
                if not verbose:
                    _mostrar_saida(resultado)
                _mostrar_erro(resultado, descricao)
                print("-" * 50)
                _pausa()
                return False
            if not verbose:
                _mostrar_saida(resultado)
    except KeyboardInterrupt:
        print("\n[AVISO] Operacao cancelada pelo utilizador.")
        print("-" * 50)
        _pausa()
        return False
    return True


# ── Opcoes do menu ─────────────────────────────────────────────────────


def opcao_1_coletar_odds() -> None:
    """[1] Coletar Odds — apenas o scraper, sem analise."""
    rotulo_dia, dia_scraper, _ = escolher_dia()
    rotulo_escopo, apenas_rf = escolher_escopo()

    cmd = [sys.executable, "scripts/superbet_scraper.py", dia_scraper]
    if apenas_rf:
        cmd.append("--quick")
    else:
        cmd.extend(["--stream-seconds", "90"])

    _executar(cmd, f"Coleta de Odds ({rotulo_dia} | {rotulo_escopo})")
    _pausa()


def opcao_2_analisar() -> None:
    """[2] Analisar Jogos — apenas Shadow Mode (Gatekeeper LLM), sem re-scrapear."""
    _, _, dia_shadow = escolher_dia()

    cmd = [
        sys.executable,
        "scripts/shadow_observe.py",
        "--pre-match",
        dia_shadow,
    ]
    _executar(cmd, f"Analise — Gatekeeper LLM (pre-match: {dia_shadow})")
    _pausa()


def opcao_3_fluxo_completo() -> None:
    """[3] Coletar + Analisar — scraper seguido de Shadow Mode."""
    rotulo_dia, dia_scraper, dia_shadow = escolher_dia()
    rotulo_escopo, apenas_rf = escolher_escopo()

    scraper_cmd: list[str] = [
        sys.executable,
        "scripts/superbet_scraper.py",
        dia_scraper,
    ]
    if apenas_rf:
        scraper_cmd.append("--quick")
    else:
        scraper_cmd.extend(["--stream-seconds", "90"])

    shadow_cmd: list[str] = [
        sys.executable,
        "scripts/shadow_observe.py",
        "--pre-match",
        dia_shadow,
    ]

    etapas = [
        (scraper_cmd, f"Coleta de Odds ({rotulo_dia} | {rotulo_escopo})"),
        (shadow_cmd, f"Analise — Gatekeeper LLM ({rotulo_dia})"),
    ]

    ok = _executar_encadeado(etapas)
    if ok:
        print(f"\n[OK] Fluxo completo concluido ({rotulo_dia}).")
        print("-" * 50)
    _pausa()


def opcao_4_dry_run() -> None:
    """[4] Simulacao Segura — Dry-Run do Shadow Mode (sem LLM)."""
    _, _, dia_shadow = escolher_dia()

    cmd = [
        sys.executable,
        "scripts/shadow_observe.py",
        "--pre-match",
        dia_shadow,
        "--dry-run",
    ]
    _executar(
        cmd,
        f"Dry-Run — coleta de contexto sem chamadas LLM (pre-match: {dia_shadow})",
    )
    _pausa()


def opcao_5_backtest() -> None:
    """[5] Relatorio do Ensemble — Backtest Mode 1 (30 modelos)."""
    _executar(
        [sys.executable, "scripts/consensus_accuracy_report.py"],
        "Relatorio do Ensemble — Backtest (Mode 1, 30 modelos)",
    )
    _pausa()


def opcao_6_manutencao() -> None:
    """[6] Manutencao Semanal — atualiza Feature Store."""
    print("\n[INICIANDO] Manutencao do sistema (Feature Store)...")
    print("-" * 50)
    print(
        "\nNota: O treino dos 30 modelos do ensemble (Mode 1) e feito "
        "separadamente via 'python run.py' ou 'scripts/update_pipeline.py'.\n"
        "Esta opcao apenas atualiza as features dos jogos recentes."
    )

    ok = _executar_encadeado(
        [
            (
                [sys.executable, "scripts/refresh_features.py"],
                "Atualizacao do Feature Store",
            ),
        ]
    )
    if ok:
        print("\n[OK] Manutencao concluida.")
        print("-" * 50)
    _pausa()


# ── Menu principal ─────────────────────────────────────────────────────


def menu_principal() -> None:
    """Exibe o menu principal do cockpit operacional."""
    verbose = False  # toggle com tecla 'v'

    while True:
        limpar_ecra()
        print("=" * 55)
        print("   JAPREDICTBET — PAINEL DE OPERACAO (v2.0)")
        print("=" * 55)
        print()
        print("[1] Coletar Odds")
        print("    Varre a Superbet e gera snapshot pre-match.")
        print()
        print("[2] Analisar Jogos")
        print("    Executa o Gatekeeper LLM sobre snapshot ja coletado.")
        print("    (Necessario ter rodado [1] primeiro)")
        print()
        print("[3] Coletar + Analisar (Fluxo Completo)")
        print("    Scraper → Gatekeeper LLM. Tudo em sequencia.")
        print()
        print("[4] Simulacao Segura (Dry-Run)")
        print("    Coleta contexto mas NAO chama o LLM (sem custo).")
        print()
        print("[5] Relatorio do Ensemble (Backtest)")
        print("    Avalia os 30 modelos no Mode 1 (historico).")
        print()
        print("[6] Manutencao Semanal")
        print("    Atualiza o Feature Store com jogos recentes.")
        print()
        print("-" * 55)
        modo = "VERBOSE" if verbose else "NORMAL"
        print(f"  [V] Alternar modo de saida (atual: {modo})")
        print("  [0] Sair")
        print("=" * 55)

        escolha = input("Escolha uma opcao: ").strip().lower()

        if escolha == "1":
            opcao_1_coletar_odds()
        elif escolha == "2":
            opcao_2_analisar()
        elif escolha == "3":
            opcao_3_fluxo_completo()
        elif escolha == "4":
            opcao_4_dry_run()
        elif escolha == "5":
            opcao_5_backtest()
        elif escolha == "6":
            opcao_6_manutencao()
        elif escolha == "v":
            verbose = not verbose
        elif escolha == "0":
            print("\nA encerrar JAPredictBet. Boa sorte!")
            break
        else:
            print("\n[AVISO] Opcao invalida.")
            time.sleep(1)


if __name__ == "__main__":
    menu_principal()
