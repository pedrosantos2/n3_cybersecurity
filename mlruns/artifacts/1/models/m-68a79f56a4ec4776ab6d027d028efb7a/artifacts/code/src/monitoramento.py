"""Critério 10 - Recurso adicional: monitoramento de drift com alerta.

Problema: URLs maliciosas mudam rapidamente (novos TLDs, encurtadores,
campanhas de phishing). O pipeline re-treina a cada ciclo, mas sem
monitoramento ninguém fica sabendo QUANDO os dados que chegam deixaram de se
parecer com os dados do modelo vigente, nem se o vigente já está errando mais
no lote novo - informação necessária para interpretar (e auditar) a decisão de
promoção/manutenção.

Solução integrada ao fluxo:

* ao promover um modelo, guardamos no bundle um *perfil de referência* das
  features do seu conjunto de treino (bins por quantis / frequência de TLD);
* no notebook 01, cada lote novo é comparado ao perfil do vigente com o PSI
  (Population Stability Index) por feature, e o vigente é avaliado no lote
  novo (rotulado) para medir queda de desempenho ANTES do re-treino;
* níveis: estável (< psi_atencao), atenção, alerta (>= psi_alerta ou queda de
  F1 >= queda_f1_alerta);
* no GitHub Actions, ``python -m src.monitoramento alertar`` publica anotações
  (::warning::), escreve o painel no resumo do job e, em caso de alerta, abre
  uma issue no repositório (notificação).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess

import numpy as np
import pandas as pd

from src.config import caminho, carregar_config, configurar_saida_utf8, ler_json
from src.preprocessamento import COLUNAS_CATEGORICAS, COLUNAS_NUMERICAS

EPS = 1e-4


def perfil_referencia(X_feat: pd.DataFrame, bins: int = 10) -> dict:
    """Perfil das features de treino: bordas de quantis e proporções por bin."""
    perfil = {"n": int(len(X_feat)), "numericas": {}, "categoricas": {}}
    for col in COLUNAS_NUMERICAS:
        v = X_feat[col].astype(float).to_numpy()
        bordas = np.unique(np.quantile(v, np.linspace(0, 1, bins + 1)[1:-1]))
        props = _proporcoes_numericas(v, bordas)
        perfil["numericas"][col] = {"bordas": bordas.tolist(), "proporcoes": props.tolist()}
    for col in COLUNAS_CATEGORICAS:
        freq = X_feat[col].astype(str).value_counts(normalize=True)
        principais = freq.head(20)
        perfil["categoricas"][col] = {
            "categorias": principais.index.tolist(),
            "proporcoes": principais.tolist() + [float(max(0.0, 1 - principais.sum()))],
        }
    return perfil


def _proporcoes_numericas(v: np.ndarray, bordas: np.ndarray) -> np.ndarray:
    # side="left": bin i = (borda[i-1], borda[i]]; preserva atributos binários/discretos
    idx = np.searchsorted(bordas, v, side="left")
    contagem = np.bincount(idx, minlength=len(bordas) + 1)
    return contagem / max(len(v), 1)


def psi(esperado, observado) -> float:
    e = np.clip(np.asarray(esperado, dtype=float), EPS, None)
    o = np.clip(np.asarray(observado, dtype=float), EPS, None)
    return float(np.sum((o - e) * np.log(o / e)))


def nivel(valor_psi: float, cfg: dict) -> str:
    m = cfg["monitoramento"]
    if valor_psi >= m["psi_alerta"]:
        return "alerta"
    if valor_psi >= m["psi_atencao"]:
        return "atencao"
    return "estavel"


def calcular_drift(perfil: dict, X_novo: pd.DataFrame, cfg: dict) -> dict:
    por_feature = {}
    for col, ref in perfil["numericas"].items():
        obs = _proporcoes_numericas(X_novo[col].astype(float).to_numpy(), np.asarray(ref["bordas"]))
        por_feature[col] = psi(ref["proporcoes"], obs)
    for col, ref in perfil["categoricas"].items():
        serie = X_novo[col].astype(str)
        obs = [float((serie == c).mean()) for c in ref["categorias"]]
        obs.append(max(0.0, 1 - sum(obs)))
        por_feature[col] = psi(ref["proporcoes"], obs)
    ordenado = dict(sorted(por_feature.items(), key=lambda kv: -kv[1]))
    psi_max_feature, psi_max = next(iter(ordenado.items()))
    return {
        "n_observado": int(len(X_novo)),
        "psi_por_feature": {k: round(v, 5) for k, v in ordenado.items()},
        "psi_max": round(psi_max, 5),
        "feature_psi_max": psi_max_feature,
        "psi_medio": round(float(np.mean(list(ordenado.values()))), 5),
        "features_em_atencao": [k for k, v in ordenado.items() if nivel(v, cfg) != "estavel"],
        "nivel_drift": nivel(psi_max, cfg),
    }


def consolidar_nivel(drift: dict | None, queda_f1: float | None, cfg: dict) -> tuple[str, list[str]]:
    motivos = []
    niveis = ["estavel"]
    if drift:
        niveis.append(drift["nivel_drift"])
        if drift["nivel_drift"] != "estavel":
            motivos.append(f"PSI máximo {drift['psi_max']:.3f} em '{drift['feature_psi_max']}' ({drift['nivel_drift']})")
    if queda_f1 is not None and queda_f1 >= cfg["monitoramento"]["queda_f1_alerta"]:
        niveis.append("alerta")
        motivos.append(f"F1 macro do vigente caiu {queda_f1:.3f} no lote novo")
    ordem = {"estavel": 0, "atencao": 1, "alerta": 2}
    return max(niveis, key=ordem.get), motivos


# ---------------------------------------------------------------------------
# Integração com o GitHub Actions (anotações, resumo do job e issue)
# ---------------------------------------------------------------------------
def _resumo_markdown(mon: dict, ctx: dict) -> str:
    icone = {"estavel": "🟢", "atencao": "🟡", "alerta": "🔴", "sem_referencia": "⚪"}.get(mon["nivel"], "⚪")
    linhas = [
        f"### {icone} Monitoramento de drift - ciclo `{ctx['cycle_id']}`",
        "",
        f"- Nível consolidado: **{mon['nivel']}**",
        f"- Lote(s) analisado(s): {', '.join(mon.get('lotes', [])) or '-'} ({mon.get('n_registros_novos', 0)} registros novos)",
    ]
    if mon.get("drift"):
        d = mon["drift"]
        linhas.append(f"- PSI máximo: **{d['psi_max']:.3f}** (`{d['feature_psi_max']}`); PSI médio: {d['psi_medio']:.3f}")
    if mon.get("desempenho_vigente_no_lote"):
        p = mon["desempenho_vigente_no_lote"]
        linhas.append(
            f"- F1 macro do vigente ({p['versao']}) no lote novo: {p['f1_macro_lote']:.4f} "
            f"(referência {p['f1_macro_referencia']:.4f}; queda {p['queda_f1']:+.4f})"
        )
    for m in mon.get("motivos", []):
        linhas.append(f"- ⚠️ {m}")
    return "\n".join(linhas) + "\n"


def _abrir_issue(titulo: str, corpo: str) -> None:
    if not shutil.which("gh") or not os.environ.get("GH_TOKEN"):
        print("gh CLI/GH_TOKEN indisponível: issue não aberta.")
        return
    subprocess.run(["gh", "issue", "create", "--title", titulo, "--body", corpo], check=False)


def alertar() -> None:
    """Lê o resultado do monitoramento do ciclo atual e publica as notificações."""
    cfg = carregar_config()
    ctx = ler_json("evidencias/ciclo_atual.json")
    mon = ler_json(caminho(ctx["dir_evidencias"]) / "monitoramento_drift.json")
    if not mon:
        print("Sem resultado de monitoramento neste ciclo.")
        return
    texto = _resumo_markdown(mon, ctx)
    print(texto)
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as f:
            f.write(texto + "\n")
    if mon["nivel"] == "alerta":
        print(f"::warning title=Drift/degradação detectado ({ctx['cycle_id']})::{'; '.join(mon.get('motivos', []))}")
        if cfg["monitoramento"].get("abrir_issue_em_alerta") and os.environ.get("GITHUB_ACTIONS"):
            run_url = (ctx.get("github") or {}).get("run_url", "")
            _abrir_issue(f"[MLOps] Alerta de drift no ciclo {ctx['cycle_id']}", texto + f"\nExecução: {run_url}\n")
    elif mon["nivel"] == "atencao":
        print(f"::notice title=Drift moderado ({ctx['cycle_id']})::{'; '.join(mon.get('motivos', []))}")


def main(argv: list[str] | None = None) -> None:
    configurar_saida_utf8()
    parser = argparse.ArgumentParser(description="Monitoramento de drift (critério 10)")
    parser.add_argument("cmd", choices=["alertar"])
    parser.parse_args(argv)
    alertar()


if __name__ == "__main__":
    main()
