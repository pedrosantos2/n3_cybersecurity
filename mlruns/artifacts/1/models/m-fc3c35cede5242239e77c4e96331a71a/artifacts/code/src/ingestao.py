"""Etapa 2 do fluxo: entrada e versionamento de dados novos.

Modelo de chegada de dados (definido antes do treinamento, ver config.yaml):

* ``data/raw/`` contém os lotes recebidos (arquivos CSV imutáveis, versionados
  no Git). O lote inicial (``lote_0001.csv``) já acompanha o repositório.
* ``data/registro_lotes.json`` registra cada lote com hash SHA-256, origem,
  ciclo de recebimento/incorporação e status (recebido, incorporado, rejeitado).
* A cada ciclo, arquivos novos colocados em ``data/raw/`` são detectados e
  registrados. Se não houver nenhum lote pendente, a chegada é simulada: o
  próximo bloco da fonte pública (embaralhada com semente fixa) é materializado
  como um novo lote.
* O ``data_version`` é derivado dos hashes dos lotes incorporados, na ordem de
  incorporação. Mesmos dados => mesmo data_version, em qualquer máquina.
"""
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import agora_utc, caminho, ler_json, relativo, salvar_json, sha256_arquivo

_PADRAO_LOTE = re.compile(r"^lote_(\d{4})\.csv$")


class FonteIndisponivel(RuntimeError):
    """A fonte pública não pôde ser obtida (sem rede, Kaggle fora do ar...)."""


class LoteAdulterado(RuntimeError):
    """Um lote já registrado foi alterado ou removido (dados devem ser imutáveis)."""


# ---------------------------------------------------------------------------
# Fonte pública
# ---------------------------------------------------------------------------
def obter_fonte(cfg: dict) -> Path:
    """Garante uma cópia local da fonte pública (Kaggle) e devolve o caminho.

    O download usa ``kagglehub`` (funciona anonimamente para datasets públicos;
    se as variáveis KAGGLE_USERNAME/KAGGLE_KEY existirem, são usadas)."""
    fonte = cfg["dados"]["fonte"]
    destino = caminho(fonte["cache"])
    if destino.exists():
        return destino
    try:
        import kagglehub

        pasta = Path(kagglehub.dataset_download(fonte["kaggle_dataset"]))
    except Exception as exc:  # rede, autenticação, Kaggle indisponível
        raise FonteIndisponivel(
            f"Não foi possível baixar {fonte['kaggle_dataset']} do Kaggle: {exc}. "
            f"Baixe manualmente {fonte['url']} e salve '{fonte['arquivo']}' em {fonte['cache']}."
        ) from exc
    candidatos = list(pasta.rglob(fonte["arquivo"]))
    if not candidatos:
        raise FonteIndisponivel(f"Arquivo {fonte['arquivo']} não encontrado em {pasta}.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(candidatos[0], destino)
    return destino


# ---------------------------------------------------------------------------
# Registro de lotes
# ---------------------------------------------------------------------------
def carregar_registro(cfg: dict) -> dict:
    return ler_json(
        cfg["dados"]["registro_lotes"],
        {"versao_formato": 1, "fonte_proxima_posicao": 0, "lotes": []},
    )


def salvar_registro(cfg: dict, registro: dict) -> None:
    salvar_json(registro, cfg["dados"]["registro_lotes"])


def lotes_por_status(registro: dict, status: str) -> list[dict]:
    return [l for l in registro["lotes"] if l["status"] == status]


def verificar_integridade(registro: dict) -> None:
    """Lotes já registrados não podem mudar: o hash do arquivo deve conferir."""
    for lote in registro["lotes"]:
        p = caminho(lote["arquivo"])
        if not p.exists():
            raise LoteAdulterado(f"Lote registrado ausente: {lote['arquivo']}")
        if sha256_arquivo(p) != lote["sha256"]:
            raise LoteAdulterado(f"Lote alterado após o registro: {lote['arquivo']}")


def _proximo_numero_lote(dir_raw: Path) -> int:
    numeros = [int(m.group(1)) for p in dir_raw.glob("lote_*.csv") if (m := _PADRAO_LOTE.match(p.name))]
    return max(numeros, default=0) + 1


def _novo_registro_lote(p: Path, ctx: dict | None, origem: str, posicao=None) -> dict:
    linhas = len(pd.read_csv(p, dtype=str, keep_default_na=False))
    return {
        "arquivo": relativo(p),
        "sha256": sha256_arquivo(p),
        "linhas": int(linhas),
        "origem": origem,
        "posicao_fonte": posicao,
        "recebido_em": agora_utc(),
        "recebido_no_ciclo": ctx["cycle_id"] if ctx else None,
        "status": "recebido",
    }


def materializar_proximos_lotes(cfg: dict, registro: dict, n_lotes: int, ctx: dict | None = None) -> list[dict]:
    """Simula a chegada de ``n_lotes`` novos lotes a partir da fonte pública."""
    chegada = cfg["dados"]["chegada"]
    col_url, col_alvo = cfg["dados"]["coluna_url"], cfg["dados"]["coluna_alvo"]
    fonte = pd.read_csv(obter_fonte(cfg), dtype=str, keep_default_na=False)[[col_url, col_alvo]]
    perm = np.random.default_rng(chegada["semente"]).permutation(len(fonte))
    dir_raw = caminho(cfg["dados"]["dir_raw"])
    dir_raw.mkdir(parents=True, exist_ok=True)

    novos = []
    pos = int(registro.get("fonte_proxima_posicao", 0))
    for _ in range(n_lotes):
        if pos >= len(fonte):
            break
        tamanho = chegada["tamanho_lote_inicial"] if pos == 0 else chegada["tamanho_lote_novo"]
        idx = perm[pos : pos + tamanho]
        destino = dir_raw / f"lote_{_proximo_numero_lote(dir_raw):04d}.csv"
        fonte.iloc[idx].to_csv(destino, index=False, lineterminator="\n", encoding="utf-8")
        entrada = _novo_registro_lote(destino, ctx, "simulacao_fonte_publica", [pos, pos + len(idx)])
        registro["lotes"].append(entrada)
        novos.append(entrada)
        pos += len(idx)
    registro["fonte_proxima_posicao"] = pos
    return novos


def receber_lotes(cfg: dict, ctx: dict | None = None) -> tuple[dict, list[dict], list[str]]:
    """Detecta/recebe lotes novos. Devolve (registro, lotes pendentes, avisos).

    1. verifica a integridade dos lotes já registrados;
    2. registra arquivos novos colocados manualmente em data/raw/;
    3. se não houver lote pendente, simula a chegada do próximo lote da fonte.
    """
    registro = carregar_registro(cfg)
    verificar_integridade(registro)
    avisos: list[str] = []
    dir_raw = caminho(cfg["dados"]["dir_raw"])
    registrados = {l["arquivo"] for l in registro["lotes"]}
    for p in sorted(dir_raw.glob("*.csv")):
        if relativo(p) not in registrados:
            registro["lotes"].append(_novo_registro_lote(p, ctx, "arquivo_em_data_raw"))

    pendentes = lotes_por_status(registro, "recebido")
    chegada = cfg["dados"]["chegada"]
    if not pendentes and chegada.get("simular_chegada", False):
        try:
            materializar_proximos_lotes(cfg, registro, chegada.get("lotes_por_ciclo", 1), ctx)
        except FonteIndisponivel as exc:
            avisos.append(f"Sem lote novo neste ciclo: {exc}")
        pendentes = lotes_por_status(registro, "recebido")
        if not pendentes:
            avisos.append("Fonte esgotada ou indisponível: ciclo executado com os mesmos dados.")
    salvar_registro(cfg, registro)
    return registro, pendentes, avisos


def ler_lote(cfg: dict, entrada: dict) -> pd.DataFrame:
    col_url, col_alvo = cfg["dados"]["coluna_url"], cfg["dados"]["coluna_alvo"]
    df = pd.read_csv(caminho(entrada["arquivo"]), dtype=str, keep_default_na=False, na_values=[""])
    for col in (col_url, col_alvo):
        if col not in df.columns:
            df[col] = pd.NA
    df = df[[col_url, col_alvo]].copy()
    df["lote"] = Path(entrada["arquivo"]).stem
    return df


def calcular_data_version(registro: dict) -> str:
    incorporados = lotes_por_status(registro, "incorporado")
    if not incorporados:
        return "dv000-vazio"
    h = hashlib.sha256("".join(l["sha256"] for l in incorporados).encode()).hexdigest()
    return f"dv{len(incorporados):03d}-{h[:8]}"


def finalizar_incorporacao(cfg: dict, registro: dict, ctx: dict, aceitos: list[dict], rejeitados: dict[str, str]) -> str:
    """Marca os lotes pendentes como incorporados/rejeitados e devolve o novo data_version."""
    agora = agora_utc()
    for lote in registro["lotes"]:
        if lote["status"] != "recebido":
            continue
        if lote["arquivo"] in rejeitados:
            lote.update(status="rejeitado", motivo_rejeicao=rejeitados[lote["arquivo"]], avaliado_no_ciclo=ctx["cycle_id"])
        elif any(a["arquivo"] == lote["arquivo"] for a in aceitos):
            lote.update(status="incorporado", incorporado_no_ciclo=ctx["cycle_id"], incorporado_em=agora)
    data_version = calcular_data_version(registro)
    registro["data_version_atual"] = data_version
    salvar_registro(cfg, registro)
    return data_version


def carregar_lotes_incorporados(cfg: dict, registro: dict) -> pd.DataFrame:
    """Concatena todos os lotes incorporados, na ordem de incorporação."""
    partes = [ler_lote(cfg, l) for l in lotes_por_status(registro, "incorporado")]
    if not partes:
        raise RuntimeError("Nenhum lote incorporado: não há dados para treinar.")
    return pd.concat(partes, ignore_index=True)
