"""Integração com o MLflow (Etapa 6 - rastreabilidade).

Armazenamento: servidor de tracking local com backend SQLite
(``mlruns/mlflow.db``) e artefatos servidos via proxy
(``--artifacts-destination mlruns/artifacts``). Com o proxy, o MLflow grava
URIs relativas (``mlflow-artifacts:/...``) em vez de caminhos absolutos da
máquina, então o histórico gerado no runner do GitHub Actions continua
consultável - com artefatos - em qualquer outra máquina que clone o repositório.

Estrutura no MLflow, por ciclo::

    ciclo-<cycle_id>                (run pai: tags cycle_id, data_version, gatilho)
      ├── <cycle_id>/01_etl
      ├── <cycle_id>/02_votacao_features
      ├── <cycle_id>/03_modelo_a_<algoritmo>
      ├── <cycle_id>/03_modelo_b_<algoritmo>
      ├── <cycle_id>/04_promocao
      └── <cycle_id>/05_previsoes

Consulta local: ``python -m src.rastreamento ui`` (abre http://127.0.0.1:5000).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient

from src.config import RAIZ, carregar_config, configurar_saida_utf8


def uri_servidor(cfg: dict) -> str:
    return f"http://{cfg['mlflow']['host']}:{cfg['mlflow']['porta']}"


def servidor_ativo(uri: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"{uri}/health", timeout=timeout) as resp:
            return resp.status == 200
    except OSError:
        return False


def comando_servidor(cfg: dict) -> list[str]:
    m = cfg["mlflow"]
    return [
        sys.executable, "-m", "mlflow", "server",
        "--backend-store-uri", m["backend_store_uri"],
        "--artifacts-destination", m["artifacts_destination"],
        "--host", m["host"],
        "--port", str(m["porta"]),
        "--workers", "1",
    ]


def iniciar_servidor(cfg: dict, aguardar_s: int = 120, desacoplado: bool = True):
    """Sobe o servidor MLflow a partir da raiz do projeto (caminhos relativos)."""
    (RAIZ / "mlruns").mkdir(exist_ok=True)
    log = open(RAIZ / "mlruns" / "servidor.log", "a", encoding="utf-8")
    kwargs = {}
    if desacoplado:
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        else:
            kwargs["start_new_session"] = True
    env = {**os.environ, "PYTHONUTF8": "1"}
    proc = subprocess.Popen(comando_servidor(cfg), cwd=RAIZ, stdout=log, stderr=subprocess.STDOUT, env=env, **kwargs)
    uri = uri_servidor(cfg)
    limite = time.time() + aguardar_s
    while time.time() < limite:
        if servidor_ativo(uri):
            return proc
        if proc.poll() is not None:
            break
        time.sleep(1)
    raise RuntimeError(f"Servidor MLflow não respondeu em {uri}. Veja mlruns/servidor.log.")


def configurar_mlflow(cfg: dict) -> str:
    """Aponta o cliente para o servidor (subindo-o se necessário) e devolve o experiment_id."""
    uri = os.environ.get("MLFLOW_TRACKING_URI") or uri_servidor(cfg)
    if uri.startswith("http") and not servidor_ativo(uri):
        if uri != uri_servidor(cfg):
            raise RuntimeError(f"MLFLOW_TRACKING_URI={uri} não está respondendo.")
        iniciar_servidor(cfg)
    mlflow.set_tracking_uri(uri)
    exp = mlflow.set_experiment(cfg["mlflow"]["experimento"])
    return exp.experiment_id


def _tags_ciclo(ctx: dict) -> dict:
    tags = {
        "cycle_id": ctx["cycle_id"],
        "data_version": ctx["data_version"],
        "gatilho": ctx["gatilho"],
    }
    if ctx.get("github"):
        tags["github_run_url"] = ctx["github"]["run_url"]
        tags["github_run_id"] = ctx["github"]["run_id"]
    if ctx.get("git_commit"):
        tags["git_commit"] = ctx["git_commit"]
    return tags


def criar_run_pai(ctx: dict, cfg: dict) -> str:
    exp_id = configurar_mlflow(cfg)
    client = MlflowClient()
    descricao = (
        f"Ciclo {ctx['cycle_id']} | data_version {ctx['data_version']} | gatilho {ctx['gatilho']}"
    )
    run = client.create_run(
        exp_id,
        run_name=f"ciclo-{ctx['cycle_id']}",
        tags={**_tags_ciclo(ctx), "tipo": "ciclo", "mlflow.note.content": descricao},
    )
    client.log_param(run.info.run_id, "cycle_id", ctx["cycle_id"])
    client.log_param(run.info.run_id, "data_version", ctx["data_version"])
    return run.info.run_id


@contextmanager
def run_etapa(ctx: dict, cfg: dict, nome: str, etapa: str, tags: dict | None = None):
    """Run filho do ciclo (todas as etapas compartilham cycle_id e data_version)."""
    configurar_mlflow(cfg)
    todas = {
        "mlflow.parentRunId": ctx["mlflow_run_pai"],
        **_tags_ciclo(ctx),
        "tipo": "etapa",
        "etapa": etapa,
        **(tags or {}),
    }
    with mlflow.start_run(run_name=f"{ctx['cycle_id']}/{nome}", tags=todas) as run:
        mlflow.log_params({"cycle_id": ctx["cycle_id"], "data_version": ctx["data_version"]})
        yield run


def atualizar_run_pai(ctx: dict, tags: dict | None = None, metricas: dict | None = None) -> None:
    client = MlflowClient()
    for k, v in (tags or {}).items():
        client.set_tag(ctx["mlflow_run_pai"], k, str(v))
    for k, v in (metricas or {}).items():
        client.log_metric(ctx["mlflow_run_pai"], k, float(v))


def encerrar_run_pai(ctx: dict, status: str = "FINISHED") -> None:
    cfg = carregar_config()
    configurar_mlflow(cfg)
    MlflowClient().set_terminated(ctx["mlflow_run_pai"], status)


def runs_do_ciclo(cfg: dict, cycle_id: str) -> pd.DataFrame:
    configurar_mlflow(cfg)
    return mlflow.search_runs(
        experiment_names=[cfg["mlflow"]["experimento"]],
        filter_string=f"tags.cycle_id = '{cycle_id}'",
        order_by=["attributes.start_time ASC"],
    )


def historico_ciclos(cfg: dict) -> pd.DataFrame:
    configurar_mlflow(cfg)
    return mlflow.search_runs(
        experiment_names=[cfg["mlflow"]["experimento"]],
        filter_string="tags.tipo = 'ciclo'",
        order_by=["attributes.start_time ASC"],
    )


def main(argv: list[str] | None = None) -> None:
    configurar_saida_utf8()
    parser = argparse.ArgumentParser(description="Servidor MLflow do projeto")
    parser.add_argument("cmd", choices=["ui", "servidor", "status"], help="ui/servidor: sobe o servidor em primeiro plano")
    args = parser.parse_args(argv)
    cfg = carregar_config()
    uri = uri_servidor(cfg)
    if args.cmd == "status":
        print(f"{uri}: {'ativo' if servidor_ativo(uri) else 'inativo'}")
        return
    if servidor_ativo(uri):
        print(f"Servidor MLflow já está ativo em {uri}")
        return
    print(f"Iniciando MLflow em {uri} (Ctrl+C para parar)...")
    os.chdir(RAIZ)
    (RAIZ / "mlruns").mkdir(exist_ok=True)
    subprocess.run(comando_servidor(cfg), cwd=RAIZ, env={**os.environ, "PYTHONUTF8": "1"})


if __name__ == "__main__":
    main()
