"""Execução local do fluxo único (mesma sequência do workflow agendado).

    python -m src.pipeline                 # um ciclo completo 01 -> 05
    python -m src.pipeline --ciclos 2      # dois ciclos seguidos (inicial + lote adicional)

Cada notebook é executado em sequência; o notebook executado (com saídas) é
salvo em ``evidencias/<cycle_id>/notebooks/``. Qualquer falha interrompe o
fluxo, marca o ciclo como ``falhou`` e impede as etapas seguintes (inclusive a
promoção).
"""
from __future__ import annotations

import argparse
import time

import nbformat
from nbclient import NotebookClient

from src import ciclo, monitoramento, rastreamento, relatorio
from src.config import RAIZ, caminho, carregar_config, configurar_saida_utf8

NOTEBOOKS = [
    "01_etl",
    "02_votacao_features",
    "03_treino_competicao",
    "04_selecao_promocao",
    "05_previsoes",
]


def executar_notebook(nome: str, destino_dir, timeout: int = 3600) -> float:
    origem = RAIZ / "notebooks" / f"{nome}.ipynb"
    nb = nbformat.read(origem, as_version=4)
    cliente = NotebookClient(
        nb, timeout=timeout, kernel_name="python3", resources={"metadata": {"path": str(origem.parent)}}
    )
    inicio = time.perf_counter()
    try:
        cliente.execute()
    finally:
        destino_dir.mkdir(parents=True, exist_ok=True)
        nbformat.write(nb, destino_dir / f"{nome[:2]}_executado.ipynb")
    return time.perf_counter() - inicio


def executar_ciclo(gatilho: str, ate: int = 5) -> dict:
    ctx = ciclo.novo_ciclo(gatilho)
    print(f"\n=== Ciclo {ctx['cycle_id']} (gatilho={gatilho}) ===")
    destino = caminho(ctx["dir_evidencias"]) / "notebooks"
    for nome in NOTEBOOKS[:ate]:
        try:
            dur = executar_notebook(nome, destino)
        except Exception as erro:
            ciclo.marcar_falha(f"falha no notebook {nome}: {type(erro).__name__}")
            print(f"[FALHA] {nome}: fluxo interrompido; nenhuma etapa posterior será executada.")
            raise
        print(f"[ok] {nome} ({dur:.0f}s)")
    if ate >= 5:
        monitoramento.alertar()
        relatorio.publicar_resumo()
    return ciclo.carregar_ciclo()


def main(argv: list[str] | None = None) -> None:
    configurar_saida_utf8()
    parser = argparse.ArgumentParser(description="Executa o fluxo único MLOps localmente")
    parser.add_argument("--ciclos", type=int, default=1)
    parser.add_argument("--gatilho", default="local")
    parser.add_argument("--ate", type=int, default=5, help="executa só os notebooks 01..N")
    args = parser.parse_args(argv)
    rastreamento.configurar_mlflow(carregar_config())  # sobe o servidor MLflow se necessário
    for _ in range(args.ciclos):
        executar_ciclo(args.gatilho, args.ate)


if __name__ == "__main__":
    main()
