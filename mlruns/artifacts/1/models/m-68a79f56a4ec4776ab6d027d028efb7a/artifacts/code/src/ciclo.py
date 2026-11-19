"""Contexto do ciclo MLOps.

Cada execução do fluxo único recebe um ``cycle_id`` (criado aqui) e um
``data_version`` (calculado na ingestão). Ambos ficam em
``evidencias/ciclo_atual.json`` e são lidos por TODOS os notebooks, de modo
que votação, treinamentos e decisão final compartilham os mesmos
identificadores. Cada notebook registra a conclusão da sua etapa; o notebook
seguinte exige que as anteriores estejam concluídas (falha = fluxo interrompido).

Uso pela linha de comando (workflow do GitHub Actions)::

    python -m src.ciclo novo --gatilho schedule
    python -m src.ciclo falhou
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

from src.config import RAIZ, agora_utc, caminho, configurar_saida_utf8, ler_json, salvar_json

ARQUIVO_CONTEXTO = RAIZ / "evidencias" / "ciclo_atual.json"
DIR_EVIDENCIAS = RAIZ / "evidencias"
ETAPAS = ["01_etl", "02_votacao", "03_treino", "04_promocao", "05_previsoes"]
_PADRAO_CICLO = re.compile(r"^c(\d{4})-")


class CicloInvalido(RuntimeError):
    """Etapas fora de ordem, ciclo falho ou identificadores inconsistentes."""


def _git_commit() -> str | None:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _proximo_sequencial() -> int:
    maiores = [0]
    if DIR_EVIDENCIAS.exists():
        for d in DIR_EVIDENCIAS.iterdir():
            m = _PADRAO_CICLO.match(d.name)
            if d.is_dir() and m:
                maiores.append(int(m.group(1)))
    return max(maiores) + 1


def _info_github() -> dict | None:
    if not os.environ.get("GITHUB_RUN_ID"):
        return None
    servidor = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ["GITHUB_RUN_ID"]
    return {
        "evento": os.environ.get("GITHUB_EVENT_NAME"),
        "run_id": run_id,
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "run_url": f"{servidor}/{repo}/actions/runs/{run_id}",
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "ref": os.environ.get("GITHUB_REF"),
        "sha": os.environ.get("GITHUB_SHA"),
        "agendamento_cron": os.environ.get("N3_CRON"),
    }


def novo_ciclo(gatilho: str | None = None) -> dict:
    """Cria um novo cycle_id e grava o contexto do ciclo."""
    from datetime import datetime, timezone

    gatilho = gatilho or os.environ.get("GITHUB_EVENT_NAME") or "local"
    seq = _proximo_sequencial()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cycle_id = f"c{seq:04d}-{ts}"
    dir_ev = DIR_EVIDENCIAS / cycle_id
    dir_ev.mkdir(parents=True, exist_ok=True)
    ctx = {
        "cycle_id": cycle_id,
        "sequencial": seq,
        "iniciado_em": agora_utc(),
        "gatilho": gatilho,
        "github": _info_github(),
        "git_commit": _git_commit(),
        "data_version": None,
        "mlflow_run_pai": None,
        "status": "em_execucao",
        "dir_evidencias": f"evidencias/{cycle_id}",
        "etapas": {},
    }
    salvar_ciclo(ctx)
    return ctx


def salvar_ciclo(ctx: dict) -> None:
    salvar_json(ctx, ARQUIVO_CONTEXTO)
    salvar_json(ctx, caminho(ctx["dir_evidencias"]) / "ciclo.json")


def carregar_ciclo(exigir: list[str] | tuple[str, ...] = ()) -> dict:
    """Carrega o contexto e garante que as etapas exigidas foram concluídas."""
    ctx = ler_json(ARQUIVO_CONTEXTO)
    if ctx is None:
        raise CicloInvalido("Nenhum ciclo ativo. Execute o notebook 01 (ou `python -m src.ciclo novo`).")
    if ctx.get("status") == "falhou":
        raise CicloInvalido(f"O ciclo {ctx['cycle_id']} falhou; inicie um novo ciclo.")
    faltando = [e for e in exigir if e not in ctx.get("etapas", {})]
    if faltando:
        raise CicloInvalido(
            f"Ciclo {ctx['cycle_id']}: etapas obrigatórias não concluídas: {faltando}. "
            "O fluxo deve ser executado em sequência (01 -> 02 -> 03 -> 04 -> 05)."
        )
    for etapa in exigir:
        info = ctx["etapas"][etapa]
        if info.get("cycle_id") != ctx["cycle_id"] or info.get("data_version") != ctx["data_version"]:
            raise CicloInvalido(f"Identificadores inconsistentes na etapa {etapa}.")
    return ctx


def obter_ou_criar_para_etl() -> dict:
    """Notebook 01: reaproveita o ciclo criado pelo workflow (ainda sem ETL) ou
    cria um novo ciclo (execução manual dos notebooks)."""
    ctx = ler_json(ARQUIVO_CONTEXTO)
    if ctx and ctx.get("status") == "em_execucao" and not ctx.get("etapas"):
        return ctx
    return novo_ciclo(gatilho=os.environ.get("GITHUB_EVENT_NAME") or "notebook_manual")


def registrar_etapa(ctx: dict, etapa: str, **info) -> dict:
    if etapa not in ETAPAS:
        raise ValueError(f"Etapa desconhecida: {etapa}")
    ctx.setdefault("etapas", {})[etapa] = {
        "concluida_em": agora_utc(),
        "cycle_id": ctx["cycle_id"],
        "data_version": ctx["data_version"],
        **info,
    }
    if etapa == ETAPAS[-1]:
        ctx["status"] = "concluido"
        ctx["concluido_em"] = agora_utc()
    salvar_ciclo(ctx)
    return ctx


def dir_evidencias(ctx: dict) -> Path:
    d = caminho(ctx["dir_evidencias"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def marcar_falha(motivo: str = "falha em uma etapa do workflow") -> dict | None:
    ctx = ler_json(ARQUIVO_CONTEXTO)
    if not ctx or ctx.get("status") != "em_execucao":
        return ctx
    ctx["status"] = "falhou"
    ctx["motivo_falha"] = motivo
    ctx["falhou_em"] = agora_utc()
    salvar_ciclo(ctx)
    if ctx.get("mlflow_run_pai"):
        try:
            from src import rastreamento

            rastreamento.encerrar_run_pai(ctx, status="FAILED")
        except Exception as exc:  # o registro da falha não pode mascarar a falha original
            print(f"Aviso: não foi possível marcar o run pai como FAILED: {exc}")
    return ctx


def _exportar_github_env(ctx: dict) -> None:
    destino = os.environ.get("GITHUB_ENV")
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write(f"CYCLE_ID={ctx['cycle_id']}\n")
            f.write(f"EVID_DIR={ctx['dir_evidencias']}\n")


def main(argv: list[str] | None = None) -> None:
    configurar_saida_utf8()
    parser = argparse.ArgumentParser(description="Contexto do ciclo MLOps")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_novo = sub.add_parser("novo", help="cria um novo ciclo")
    p_novo.add_argument("--gatilho", default=None)
    p_falha = sub.add_parser("falhou", help="marca o ciclo atual como falho")
    p_falha.add_argument("--motivo", default="falha em uma etapa do workflow")
    sub.add_parser("info", help="mostra o ciclo atual")
    args = parser.parse_args(argv)

    if args.cmd == "novo":
        ctx = novo_ciclo(args.gatilho)
        _exportar_github_env(ctx)
        print(f"Novo ciclo: {ctx['cycle_id']} (gatilho={ctx['gatilho']})")
    elif args.cmd == "falhou":
        ctx = marcar_falha(args.motivo)
        print(f"Ciclo marcado como falho: {ctx and ctx['cycle_id']}")
    else:
        import json

        print(json.dumps(ler_json(ARQUIVO_CONTEXTO), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
