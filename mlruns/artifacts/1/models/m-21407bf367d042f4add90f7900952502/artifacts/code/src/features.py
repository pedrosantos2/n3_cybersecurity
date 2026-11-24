"""Etapas 4 e 5 do fluxo: três métodos de seleção de atributos e votação.

Métodos (todos ajustados SOMENTE com dados de treino já pré-processados):

1. ``selectkbest`` - SelectKBest com informação mútua (``mutual_info_classif``):
   estatística não paramétrica, capta relações não lineares e serve para
   alvo multiclasse e atributos contínuos/binários.
2. ``random_forest`` - importância por redução média de impureza (MDI) de uma
   Random Forest com classes balanceadas: capta interações entre atributos.
3. ``rfe`` - Recursive Feature Elimination com Regressão Logística
   multinomial (dados padronizados): perspectiva linear e multivariada.

Regra de votação (fixada em config.yaml antes da comparação): cada método
elege seu top-k; a feature é eleita se tiver ``votos_minimos`` votos (2 de 3).
Se forem eleitas menos que ``min_features``, completa-se pelo menor rank médio;
se mais que ``max_features``, corta-se pelo maior rank médio. Empates no rank
médio são resolvidos pela ordem alfabética (determinístico).
"""
from __future__ import annotations

import time
import warnings
from functools import partial
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_selection import RFE, SelectKBest, mutual_info_classif
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from src.preprocessamento import construir_preprocessador

METODOS = ("selectkbest", "random_forest", "rfe")


def _amostra_estratificada(X: pd.DataFrame, y: np.ndarray, n_max: int, semente: int):
    if n_max is None or len(X) <= n_max:
        return X, y
    Xs, _, ys, _ = train_test_split(X, y, train_size=n_max, stratify=y, random_state=semente)
    return Xs, ys


def _ranking(features, importancia, selecionadas=None, k=None) -> pd.DataFrame:
    df = pd.DataFrame({"feature": list(features), "importancia": np.asarray(importancia, dtype=float)})
    df = df.sort_values(["importancia", "feature"], ascending=[False, True]).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    if selecionadas is None:
        df["selecionada"] = df["rank"] <= k
    else:
        df["selecionada"] = df["feature"].isin(selecionadas)
    return df


def metodo_selectkbest(X: pd.DataFrame, y, k: int, semente: int, params: dict) -> pd.DataFrame:
    seletor = SelectKBest(partial(mutual_info_classif, random_state=semente), k=k).fit(X, y)
    return _ranking(X.columns, seletor.scores_, X.columns[seletor.get_support()])


def metodo_random_forest(X: pd.DataFrame, y, k: int, semente: int, params: dict) -> pd.DataFrame:
    rf = RandomForestClassifier(
        n_estimators=params.get("n_estimators", 150),
        max_depth=params.get("max_depth", 12),
        class_weight="balanced_subsample",
        random_state=semente,
        n_jobs=-1,
    ).fit(X, y)
    return _ranking(X.columns, rf.feature_importances_, k=k)


def metodo_rfe(X: pd.DataFrame, y, k: int, semente: int, params: dict) -> pd.DataFrame:
    estimador = LogisticRegression(max_iter=3000, class_weight="balanced", random_state=semente)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        rfe = RFE(estimador, n_features_to_select=k, step=params.get("step", 1)).fit(X, y)
    # Ranking completo: selecionadas ordenadas por |coef| médio; depois as eliminadas
    # na ordem inversa de eliminação (eliminada por último = melhor).
    coef = np.abs(rfe.estimator_.coef_).mean(axis=0)
    importancia = np.zeros(X.shape[1])
    importancia[rfe.support_] = coef
    base = pd.DataFrame({"feature": X.columns, "ranking_rfe": rfe.ranking_, "importancia": importancia})
    base = base.sort_values(["ranking_rfe", "importancia", "feature"], ascending=[True, False, True]).reset_index(drop=True)
    base["rank"] = np.arange(1, len(base) + 1)
    base["selecionada"] = base["ranking_rfe"] == 1
    return base[["feature", "importancia", "rank", "selecionada", "ranking_rfe"]]


_FUNCOES = {"selectkbest": metodo_selectkbest, "random_forest": metodo_random_forest, "rfe": metodo_rfe}


def votar(rankings: dict[str, pd.DataFrame], regra: dict) -> tuple[pd.DataFrame, list[str]]:
    """Aplica a regra de votação e devolve (tabela de votos, features eleitas)."""
    tabela = None
    for metodo, df in rankings.items():
        parte = df.set_index("feature")[["selecionada", "rank", "importancia"]].rename(
            columns={"selecionada": f"voto_{metodo}", "rank": f"rank_{metodo}", "importancia": f"importancia_{metodo}"}
        )
        tabela = parte if tabela is None else tabela.join(parte, how="outer")
    tabela = tabela.reset_index().rename(columns={"index": "feature"})
    votos_cols = [f"voto_{m}" for m in rankings]
    rank_cols = [f"rank_{m}" for m in rankings]
    tabela[votos_cols] = tabela[votos_cols].fillna(False).astype(int)
    tabela["votos"] = tabela[votos_cols].sum(axis=1)
    tabela["rank_medio"] = tabela[rank_cols].mean(axis=1)
    tabela = tabela.sort_values(["votos", "rank_medio", "feature"], ascending=[False, True, True]).reset_index(drop=True)

    vmin, fmin, fmax = regra["votos_minimos"], regra["min_features"], regra["max_features"]
    tabela["eleita"] = False
    tabela["motivo"] = "votos insuficientes"
    maioria = tabela.index[tabela["votos"] >= vmin].tolist()
    tabela.loc[maioria, "motivo"] = f"maioria ({vmin}+ votos)"
    eleitas_idx = list(maioria)
    if len(eleitas_idx) < fmin:
        complemento = [i for i in tabela.index if i not in eleitas_idx][: fmin - len(eleitas_idx)]
        tabela.loc[complemento, "motivo"] = "completada pela quantidade mínima (desempate: rank médio)"
        eleitas_idx += complemento
    if len(eleitas_idx) > fmax:
        cortadas = eleitas_idx[fmax:]
        tabela.loc[cortadas, "motivo"] = "cortada pela quantidade máxima (pior rank médio)"
        eleitas_idx = eleitas_idx[:fmax]
    tabela.loc[eleitas_idx, "eleita"] = True
    colunas = ["feature", "votos", "eleita", "motivo", "rank_medio"] + votos_cols + rank_cols + [
        f"importancia_{m}" for m in rankings
    ]
    tabela = tabela[colunas]
    eleitas = tabela.loc[tabela["eleita"], "feature"].tolist()
    return tabela, eleitas


def executar_votacao(X: pd.DataFrame, y, cfg: dict, semente: int) -> dict:
    """Roda os três métodos sobre (X, y) de treino pré-processados e vota."""
    regra = cfg["votacao"]
    k = min(regra["top_k"], X.shape[1])
    Xs, ys = _amostra_estratificada(X, np.asarray(y), regra.get("amostra_maxima"), semente)
    rankings, tempos = {}, {}
    for metodo in METODOS:
        inicio = time.perf_counter()
        dados = (X, np.asarray(y)) if metodo == "random_forest" else (Xs, ys)
        rankings[metodo] = _FUNCOES[metodo](dados[0], dados[1], k, semente, regra["metodos"].get(metodo, {}))
        tempos[metodo] = round(time.perf_counter() - inicio, 2)
    tabela, eleitas = votar(rankings, regra)
    return {"rankings": rankings, "tabela": tabela, "eleitas": eleitas, "tempos_s": tempos, "k": k}


def jaccard(a, b) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a or b) else 1.0


def votacao_por_fold(X_feat: pd.DataFrame, y, folds: np.ndarray, cfg: dict, semente: int) -> dict:
    """Refaz pré-processamento + três métodos + votação DENTRO de cada fold.

    Garante que a validação cruzada da etapa 03 não vaze informação: em cada
    fold, imputação/winsorização/padronização/one-hot e a escolha de features
    usam apenas a parte de treino daquele fold."""
    y = np.asarray(y)
    resultado = {}
    for f in sorted(np.unique(folds)):
        treino = folds != f
        prep = construir_preprocessador(cfg).fit(X_feat[treino])
        Xt = prep.transform(X_feat[treino])
        votacao = executar_votacao(Xt, y[treino], cfg, semente)
        resultado[int(f)] = {"eleitas": votacao["eleitas"], "tabela": votacao["tabela"]}
    return resultado


def estabilidade(conjuntos: dict[int, list[str]], referencia: list[str]) -> dict:
    """Frequência de eleição por feature e similaridade (Jaccard) entre folds."""
    pares = [jaccard(a, b) for a, b in combinations(conjuntos.values(), 2)]
    freq: dict[str, int] = {}
    for eleitas in conjuntos.values():
        for f in eleitas:
            freq[f] = freq.get(f, 0) + 1
    return {
        "jaccard_medio_entre_folds": float(np.mean(pares)) if pares else 1.0,
        "jaccard_medio_vs_ciclo": float(np.mean([jaccard(c, referencia) for c in conjuntos.values()])),
        "frequencia_eleicao": dict(sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))),
    }
