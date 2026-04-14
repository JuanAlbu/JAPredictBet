"""Painel de operacao simplificado para o JAPredictBet.

Este menu abstrai os comandos tecnicos do projeto e oferece um cockpit
enxuto para o utilizador focado na operacao diaria de analise.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta


def limpar_ecra() -> None:
    """Limpa o terminal atual."""
    os.system("cls" if os.name == "nt" else "clear")


def escolher_dia() -> tuple[str, str, str]:
    """Pergunta se a operacao sera para hoje ou amanha.

    Returns:
        Tuple com:
        - rotulo amigavel para UI
        - argumento para o scraper
        - argumento para o shadow_observe
    """
    dias_pt = [
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
        nome_dia = dias_pt[amanha.weekday()]
        data_iso = amanha.strftime("%Y-%m-%d")
        return (f"AMANHA / {nome_dia.upper()}", nome_dia, data_iso)

    return ("HOJE", "hoje", "hoje")


def escolher_mercados() -> tuple[str, bool]:
    """Pergunta se a coleta deve ficar em Resultado Final ou buscar outros mercados."""
    print("\nQual profundidade de mercados deseja?")
    print("[1] Apenas Resultado Final")
    print("[2] Buscar outros mercados tambem")
    opcao = input("Selecione (padrao: Buscar outros mercados): ").strip()

    if opcao == "1":
        return ("APENAS RESULTADO FINAL", True)

    return ("OUTROS MERCADOS TAMBEM", False)


def _mostrar_saida(resultado: subprocess.CompletedProcess[str]) -> None:
    """Exibe a saida do subprocesso de forma amigavel."""
    if resultado.stdout:
        print(resultado.stdout.strip())


def _mostrar_erro(resultado: subprocess.CompletedProcess[str], descricao: str) -> None:
    """Exibe uma mensagem de erro resumida sem despejar traceback bruto."""
    print(f"\n[ERRO] Falha durante a execucao de: {descricao}")
    if resultado.stderr:
        stderr_lines = [line for line in resultado.stderr.strip().splitlines() if line.strip()]
        if stderr_lines:
            print("\nResumo do erro:")
            for line in stderr_lines[-12:]:
                print(line)


def executar_comando(comando: list[str], descricao: str) -> None:
    """Executa um comando externo com tratamento amigavel de erros."""
    print(f"\n[INICIANDO] {descricao}...")
    print("-" * 50)
    try:
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
        input("Pressione ENTER para voltar ao menu...")
        return

    if resultado.returncode == 0:
        _mostrar_saida(resultado)
        print(f"\n[OK] {descricao} concluido com sucesso.")
    else:
        _mostrar_saida(resultado)
        _mostrar_erro(resultado, descricao)

    print("-" * 50)
    input("Pressione ENTER para voltar ao menu...")


def executar_manutencao() -> None:
    """Executa a manutencao semanal em duas etapas."""
    print("\n[INICIANDO] Manutencao do sistema (Feature Store + Treino)...")
    print("-" * 50)

    etapas = [
        ([sys.executable, "scripts/refresh_features.py"], "Atualizacao do Feature Store"),
        ([sys.executable, "run.py"], "Treino dos modelos"),
    ]

    try:
        for comando, descricao in etapas:
            print(f"\nExecutando: {descricao}")
            resultado = subprocess.run(
                comando,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if resultado.returncode != 0:
                _mostrar_saida(resultado)
                _mostrar_erro(resultado, descricao)
                print("-" * 50)
                input("Pressione ENTER para voltar ao menu...")
                return
            _mostrar_saida(resultado)
    except KeyboardInterrupt:
        print("\n[AVISO] Operacao cancelada pelo utilizador.")
        print("-" * 50)
        input("Pressione ENTER para voltar ao menu...")
        return

    print("\n[OK] Manutencao concluida com sucesso.")
    print("-" * 50)
    input("Pressione ENTER para voltar ao menu...")


def executar_fluxo_pre_match(
    rotulo_dia: str,
    dia_scraper: str,
    dia_shadow: str,
    quick_mode: bool,
    dry_run: bool = False,
) -> None:
    """Atualiza o snapshot pre-match e executa a analise do dia."""
    sufixo = " + Dry-Run" if dry_run else ""
    print(f"\n[INICIANDO] Preparacao e analise ({rotulo_dia}{sufixo})...")
    print("-" * 50)

    shadow_cmd = [
        sys.executable,
        "scripts/shadow_observe.py",
        "--pre-match",
        dia_shadow,
    ]
    if dry_run:
        shadow_cmd.append("--dry-run")

    scraper_cmd = [sys.executable, "scripts/superbet_scraper.py", dia_scraper]
    if quick_mode:
        scraper_cmd.append("--quick")
    else:
        scraper_cmd.extend(["--stream-seconds", "90"])

    comandos = [
        (
            scraper_cmd,
            f"Extracao de Odds ({rotulo_dia})",
        ),
        (
            shadow_cmd,
            f"{'Dry-Run' if dry_run else 'Shadow Mode'} ({rotulo_dia})",
        ),
    ]

    try:
        for comando, descricao in comandos:
            print(f"\nExecutando: {descricao}")
            resultado = subprocess.run(
                comando,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if resultado.returncode != 0:
                _mostrar_saida(resultado)
                _mostrar_erro(resultado, descricao)
                print("-" * 50)
                input("Pressione ENTER para voltar ao menu...")
                return
            _mostrar_saida(resultado)
    except KeyboardInterrupt:
        print("\n[AVISO] Operacao cancelada pelo utilizador.")
        print("-" * 50)
        input("Pressione ENTER para voltar ao menu...")
        return

    print(f"\n[OK] Fluxo concluido com sucesso ({rotulo_dia}{sufixo}).")
    print("-" * 50)
    input("Pressione ENTER para voltar ao menu...")


def menu_principal() -> None:
    """Exibe o menu principal do cockpit operacional."""
    while True:
        limpar_ecra()
        print("===========================================")
        print("    JAPREDICTBET - PAINEL DE OPERACAO      ")
        print("===========================================")
        print("[1] Preparar o Dia (Extrair Odds)")
        print("    Varre a Superbet e prepara o terreno para a analise.")
        print("[2] Gerar Entradas do Dia (Shadow Mode)")
        print("    Orquestra ML + LLM e produz a Lista do Dia.")
        print("[3] Simulacao Segura (Dry-Run)")
        print("    Roda as analises na tela sem depender do fluxo oficial.")
        print("[4] Auditar Performance (Resultados)")
        print("    Avalia o lucro/prejuizo das decisoes passadas do sistema.")
        print("[5] Manutencao do Sistema (Semanal)")
        print("    Atualiza a inteligencia do sistema e retreina os modelos.")
        print("[0] Sair")
        print("===========================================")

        escolha = input("Escolha uma opcao: ").strip()

        if escolha == "1":
            rotulo_dia, dia_scraper, _ = escolher_dia()
            rotulo_mercados, quick_mode = escolher_mercados()
            executar_comando(
                (
                    [sys.executable, "scripts/superbet_scraper.py", dia_scraper, "--quick"]
                    if quick_mode
                    else [
                        sys.executable,
                        "scripts/superbet_scraper.py",
                        dia_scraper,
                        "--stream-seconds",
                        "90",
                    ]
                ),
                f"Extracao de Odds ({rotulo_dia} | {rotulo_mercados})",
            )
        elif escolha == "2":
            rotulo_dia, dia_scraper, dia_shadow = escolher_dia()
            _, quick_mode = escolher_mercados()
            executar_fluxo_pre_match(
                rotulo_dia=rotulo_dia,
                dia_scraper=dia_scraper,
                dia_shadow=dia_shadow,
                quick_mode=quick_mode,
                dry_run=False,
            )
        elif escolha == "3":
            rotulo_dia, dia_scraper, dia_shadow = escolher_dia()
            _, quick_mode = escolher_mercados()
            executar_fluxo_pre_match(
                rotulo_dia=rotulo_dia,
                dia_scraper=dia_scraper,
                dia_shadow=dia_shadow,
                quick_mode=quick_mode,
                dry_run=True,
            )
        elif escolha == "4":
            executar_comando(
                [sys.executable, "scripts/consensus_accuracy_report.py"],
                "Relatorio de Performance",
            )
        elif escolha == "5":
            executar_manutencao()
        elif escolha == "0":
            print("\nA encerrar JAPredictBet. Boa sorte!")
            break
        else:
            print("\n[AVISO] Opcao invalida.")
            time.sleep(1)


if __name__ == "__main__":
    menu_principal()
