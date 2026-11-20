"""Etapa 8/9 do fluxo: eleição do vencedor do ciclo e promoção controlada.

1. ``eleger_vencedor``: compara automaticamente os dois candidatos pela média
   da métrica principal na validação cruzada (mesmos folds e features).
2. ``decidir_promocao``: confronta o vencedor do ciclo com o modelo vigente no
   holdout de validação (mesmos registros para os dois = protocolo compatível)
   e aplica a regra pré-definida (limiar de melhoria + pisos de qualidade).
3. ``registrar_decisao``: grava ``models/modelo_vigente.json`` (manifesto),
   preserva todas as versões em ``models/versoes/`` e acrescenta a decisão ao
   histórico ``models/historico_decisoes.csv``.
"""
from __future__ import annotations

import csv
import math
import re

import joblib
import numpy as np
import pandas as pd

from src.config import RAIZ, agora_utc, caminho, ler_json, relativo, salvar_json, sha256_arquivo

ARQUIVO_MANIFESTO = RAIZ / "models" / "modelo_vigente.json"
DIR_VERSOES = RAIZ / "models" / "versoes"
ARQUIVO_HISTORICO = RAIZ / "models" / "historico_decisoes.csv"
DIR_CANDIDATOS = RAIZ / "data" / "processed" / "candidatos"

COLUNAS_HISTORICO = [
    "cycle_id", "data_version", "gatilho", "decidido_em", "vencedor_ciclo", "algoritmo_vencedor",
    "cv_vencedor", "cv_perdedor", "metrica_desafiante_validacao", "metrica_vigente_validacao",
    "delta", "limiar", "decisao", "versao_vigente_apos", "run_id_desafiante", "motivo",
]


class PromocaoBloqueada(RuntimeError):
    """Inconsistência detectada: nenhuma promoção pode acontecer."""


def melhor(a: float, b: float, direcao: str) -> bool:
    return a > b if direcao == "maximizar" else a < b


def resumir_cv(cv: pd.DataFrame, metrica: str) -> pd.DataFrame:
    return (
        cv.groupby(["papel", "algoritmo"])[metrica]
        .agg(media="mean", desvio="std", minimo="min", maximo="max")
        .reset_index()
    )


def eleger_vencedor(resumo: pd.DataFrame, cfg: dict) -> dict:
    direcao = cfg["avaliacao"]["direcao"]
    tol = cfg["eleicao"]["tolerancia_empate"]
    a, b = resumo.iloc[0], resumo.iloc[1]
    delta = float(a["media"] - b["media"])
    if abs(delta) < tol:
        vencedor, perdedor = (a, b) if a["desvio"] <= b["desvio"] else (b, a)
        motivo = f"empate técnico (|Δ|={abs(delta):.5f} < {tol}); vence o menor desvio-padrão entre folds"
    else:
        vencedor, perdedor = (a, b) if melhor(a["media"], b["media"], direcao) else (b, a)
        motivo = f"maior média de {cfg['avaliacao']['metrica_principal']} na validação cruzada (Δ={abs(delta):.4f})"
    return {
        "vencedor": vencedor["papel"],
        "algoritmo_vencedor": vencedor["algoritmo"],
        "perdedor": perdedor["papel"],
        "algoritmo_perdedor": perdedor["algoritmo"],
        "media_vencedor": float(vencedor["media"]),
        "media_perdedor": float(perdedor["media"]),
        "desvio_vencedor": float(vencedor["desvio"]),
        "motivo": motivo,
    }


# ---------------------------------------------------------------------------
# Modelo vigente (persistente entre ciclos: lido do repositório, não do runner)
# ---------------------------------------------------------------------------
def carregar_manifesto() -> dict | None:
    return ler_json(ARQUIVO_MANIFESTO)


def carregar_modelo(arquivo: str, sha256: str | None = None):
    p = caminho(arquivo)
    if not p.exists():
        raise FileNotFoundError(f"Modelo não encontrado: {arquivo}")
    if sha256 and sha256_arquivo(p) != sha256:
        raise PromocaoBloqueada(f"Hash do modelo {arquivo} não confere com o manifesto (arquivo adulterado?).")
    return joblib.load(p)


def carregar_vigente():
    """Devolve (manifesto, modelo) do vigente, ou (None, None) se ainda não existe."""
    manifesto = carregar_manifesto()
    if not manifesto or not manifesto.get("vigente"):
        return manifesto, None
    v = manifesto["vigente"]
    return manifesto, carregar_modelo(v["arquivo_modelo"], v["sha256"])


def decidir_promocao(desafiante: dict, vigente: dict | None, cfg: dict, checagens_integridade: list[dict]) -> dict:
    """Aplica a regra de promoção definida a priori no config.yaml."""
    regra = cfg["promocao"]
    metrica = cfg["avaliacao"]["metrica_principal"]
    direcao = cfg["avaliacao"]["direcao"]
    classes = cfg["dados"]["classes"]
    v_des = desafiante[metrica]
    checagens = list(checagens_integridade)
    checagens.append({
        "regra": "metrica_finita",
        "ok": bool(np.isfinite(v_des)),
        "detalhe": f"{metrica} do desafiante = {v_des}",
    })
    piso = regra["metrica_minima"]
    checagens.append({
        "regra": "piso_metrica_principal",
        "ok": bool(v_des >= piso) if direcao == "maximizar" else bool(v_des <= piso),
        "detalhe": f"{metrica}={v_des:.4f} vs piso {piso}",
    })
    pior_recall = min(desafiante[f"recall_{c}"] for c in classes)
    checagens.append({
        "regra": "recall_minimo_por_classe",
        "ok": bool(pior_recall >= regra["recall_minimo_por_classe"]),
        "detalhe": f"menor recall por classe={pior_recall:.4f} vs mínimo {regra['recall_minimo_por_classe']}",
    })
    if vigente is None:
        delta = None
        checagens.append({"regra": "supera_vigente", "ok": True, "detalhe": "não há modelo vigente (primeiro ciclo)"})
    else:
        v_vig = vigente[metrica]
        delta = (v_des - v_vig) if direcao == "maximizar" else (v_vig - v_des)
        checagens.append({
            "regra": "supera_vigente",
            "ok": bool(delta >= regra["limiar_melhoria"]),
            "detalhe": f"Δ={delta:+.4f} (desafiante {v_des:.4f} x vigente {v_vig:.4f}); limiar {regra['limiar_melhoria']}",
        })
    falhas = [c for c in checagens if not c["ok"]]
    if any(c["regra"].startswith("integridade") for c in falhas):
        decisao = "bloqueado"
    elif falhas:
        decisao = "manter" if vigente is not None else "sem_modelo_aprovado"
    else:
        decisao = "promover"
    motivo = (
        "todas as regras de promoção foram satisfeitas"
        if decisao == "promover"
        else "; ".join(f"{c['regra']}: {c['detalhe']}" for c in falhas)
    )
    return {
        "decisao": decisao,
        "motivo": motivo,
        "metrica": metrica,
        "direcao": direcao,
        "valor_desafiante": float(v_des),
        "valor_vigente": None if vigente is None else float(vigente[metrica]),
        "delta": None if delta is None else float(delta),
        "limiar": regra["limiar_melhoria"],
        "checagens": checagens,
    }


def proxima_versao() -> str:
    numeros = [int(m.group(1)) for d in DIR_VERSOES.glob("v*") if (m := re.match(r"^v(\d{4})$", d.name))]
    return f"v{max(numeros, default=0) + 1:04d}"


def salvar_versao(modelo, versao: str) -> tuple[str, str]:
    destino = DIR_VERSOES / versao / "modelo.joblib"
    destino.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, destino, compress=3)
    return relativo(destino), sha256_arquivo(destino)


def registrar_decisao(ctx: dict, cfg: dict, decisao: dict, eleicao: dict, candidato: dict, modelo_desafiante) -> dict:
    """Atualiza manifesto + histórico. Versões anteriores nunca são apagadas."""
    manifesto = carregar_manifesto() or {"vigente": None, "versoes_anteriores": []}
    if decisao["decisao"] == "promover":
        versao = proxima_versao()
        modelo_desafiante.metadados["versao"] = versao
        arquivo, sha = salvar_versao(modelo_desafiante, versao)
        if manifesto.get("vigente"):
            manifesto.setdefault("versoes_anteriores", []).append(
                {k: manifesto["vigente"][k] for k in ("versao", "cycle_id", "data_version", "algoritmo", "arquivo_modelo", "sha256", "run_id")}
                | {"substituida_em": agora_utc(), "substituida_no_ciclo": ctx["cycle_id"]}
            )
        manifesto["vigente"] = {
            "versao": versao,
            "cycle_id": ctx["cycle_id"],
            "data_version": ctx["data_version"],
            "algoritmo": candidato["algoritmo"],
            "papel_no_ciclo": eleicao["vencedor"],
            "features": candidato["features"],
            "n_features": len(candidato["features"]),
            "metrica_principal": decisao["metrica"],
            "valor_metrica_validacao": decisao["valor_desafiante"],
            "metricas_validacao": candidato["metricas_validacao"],
            "metrica_cv_media": eleicao["media_vencedor"],
            "metrica_cv_desvio": eleicao["desvio_vencedor"],
            "run_id": candidato["run_id"],
            "model_uri_mlflow": candidato.get("model_uri"),
            "modelo_registrado": candidato.get("modelo_registrado"),
            "arquivo_modelo": arquivo,
            "sha256": sha,
            "promovido_em": agora_utc(),
        }
    manifesto["ultima_decisao"] = {
        "cycle_id": ctx["cycle_id"],
        "data_version": ctx["data_version"],
        "gatilho": ctx["gatilho"],
        "decidido_em": agora_utc(),
        "decisao": decisao["decisao"],
        "motivo": decisao["motivo"],
        "vencedor_ciclo": eleicao["vencedor"],
        "algoritmo_vencedor": eleicao["algoritmo_vencedor"],
        "metrica": decisao["metrica"],
        "valor_desafiante": decisao["valor_desafiante"],
        "valor_vigente": decisao["valor_vigente"],
        "delta": decisao["delta"],
        "run_id_desafiante": candidato["run_id"],
        "run_id_promocao": decisao.get("run_id_promocao"),
        "features_desafiante": candidato["features"],
        "versao_vigente_apos": (manifesto.get("vigente") or {}).get("versao"),
    }
    manifesto["regra_promocao"] = cfg["promocao"]
    manifesto["historico"] = relativo(ARQUIVO_HISTORICO)
    salvar_json(manifesto, ARQUIVO_MANIFESTO)

    ARQUIVO_HISTORICO.parent.mkdir(parents=True, exist_ok=True)
    novo = not ARQUIVO_HISTORICO.exists()
    with open(ARQUIVO_HISTORICO, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS_HISTORICO, lineterminator="\n")
        if novo:
            w.writeheader()
        fmt = lambda x: "" if x is None or (isinstance(x, float) and math.isnan(x)) else (round(x, 6) if isinstance(x, float) else x)
        w.writerow({
            "cycle_id": ctx["cycle_id"],
            "data_version": ctx["data_version"],
            "gatilho": ctx["gatilho"],
            "decidido_em": manifesto["ultima_decisao"]["decidido_em"],
            "vencedor_ciclo": eleicao["vencedor"],
            "algoritmo_vencedor": eleicao["algoritmo_vencedor"],
            "cv_vencedor": fmt(eleicao["media_vencedor"]),
            "cv_perdedor": fmt(eleicao["media_perdedor"]),
            "metrica_desafiante_validacao": fmt(decisao["valor_desafiante"]),
            "metrica_vigente_validacao": fmt(decisao["valor_vigente"]),
            "delta": fmt(decisao["delta"]),
            "limiar": decisao["limiar"],
            "decisao": decisao["decisao"],
            "versao_vigente_apos": manifesto["ultima_decisao"]["versao_vigente_apos"] or "",
            "run_id_desafiante": candidato["run_id"],
            "motivo": decisao["motivo"],
        })
    return manifesto


def ler_historico() -> pd.DataFrame:
    if not ARQUIVO_HISTORICO.exists():
        return pd.DataFrame(columns=COLUNAS_HISTORICO)
    return pd.read_csv(ARQUIVO_HISTORICO)
