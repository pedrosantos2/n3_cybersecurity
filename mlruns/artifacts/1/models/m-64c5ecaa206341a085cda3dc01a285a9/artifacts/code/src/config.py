"""Configuração do projeto e utilitários de caminho/serialização."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
os.environ.setdefault("PYTHONUTF8", "1")

RAIZ = Path(__file__).resolve().parents[1]
CAMINHO_CONFIG_PADRAO = RAIZ / "config" / "config.yaml"


def carregar_config(caminho: str | Path | None = None) -> dict:
    """Lê ``config/config.yaml`` (ou o arquivo indicado em ``N3_CONFIG``)."""
    caminho = Path(caminho or os.environ.get("N3_CONFIG") or CAMINHO_CONFIG_PADRAO)
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


def caminho(relativo: str | Path) -> Path:
    """Converte um caminho relativo à raiz do projeto em absoluto."""
    p = Path(relativo)
    return p if p.is_absolute() else RAIZ / p


def relativo(p: str | Path) -> str:
    """Caminho relativo à raiz, sempre com barras '/' (portável entre SOs)."""
    try:
        return Path(p).resolve().relative_to(RAIZ).as_posix()
    except ValueError:
        return Path(p).as_posix()


def agora_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_arquivo(p: str | Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _json_default(o: Any):
    import numpy as np

    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, Path):
        return o.as_posix()
    return str(o)


def salvar_json(dados: Any, p: str | Path) -> Path:
    p = caminho(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2, default=_json_default)
        f.write("\n")
    return p


def ler_json(p: str | Path, padrao: Any = None) -> Any:
    p = caminho(p)
    if not p.exists():
        return padrao
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def configurar_saida_utf8() -> None:
    """Evita UnicodeEncodeError no console do Windows (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def preparar_notebook() -> dict:
    """Chamado na primeira célula de cada notebook: fixa o diretório de trabalho
    na raiz do projeto (caminhos consistentes local x GitHub Actions) e
    devolve a configuração."""
    os.chdir(RAIZ)
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))
    os.environ.setdefault("PYTHONUTF8", "1")
    import warnings

    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=UserWarning, module="mlflow")
    warnings.filterwarnings("ignore", message="IProgress not found")
    import logging

    logging.getLogger("mlflow").setLevel(logging.ERROR)
    return carregar_config()
