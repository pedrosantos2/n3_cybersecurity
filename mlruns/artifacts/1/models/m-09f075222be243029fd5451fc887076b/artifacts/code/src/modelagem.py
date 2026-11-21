"""Etapa 6/7 do fluxo: dois algoritmos, mesmo protocolo de avaliação.

* ``criar_estimador``: fábrica dos algoritmos permitidos no config.yaml.
* ``construir_pipeline``: pré-processamento (ajustado no treino) + seleção das
  features eleitas + estimador. É esse objeto que é serializado, então as
  previsões usam exatamente o mesmo pré-processamento e o mesmo conjunto de
  features do treinamento.
* ``validacao_cruzada``: StratifiedKFold no treino; em cada fold os DOIS
  modelos recebem os mesmos dados e as mesmas features eleitas naquele fold.
* ``ModeloURL``: bundle serializável (pipeline + classes + metadados + perfil
  de referência para o monitoramento de drift).
"""
from __future__ import annotations

import time
import warnings

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.utils.class_weight import compute_sample_weight

from src.preprocessamento import construir_preprocessador, extrair_features_lote

ALGORITMOS = ("random_forest", "xgboost", "logistic_regression", "hist_gradient_boosting")


class SeletorColunas(BaseEstimator, TransformerMixin):
    """Mantém apenas as colunas (features eleitas) informadas."""

    def __init__(self, colunas=None):
        self.colunas = colunas

    def fit(self, X, y=None):
        faltando = [c for c in self.colunas if c not in X.columns]
        if faltando:
            raise ValueError(f"Features eleitas ausentes após o pré-processamento: {faltando}")
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X):
        return X[list(self.colunas)]

    def get_feature_names_out(self, input_features=None):
        return np.asarray(self.colunas, dtype=object)


def criar_estimador(spec: dict, semente: int, balancear: bool):
    algoritmo = spec["algoritmo"]
    params = dict(spec.get("params", {}))
    if algoritmo == "random_forest":
        if balancear:
            params.setdefault("class_weight", "balanced_subsample")
        return RandomForestClassifier(random_state=semente, n_jobs=-1, **params)
    if algoritmo == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(
            objective="multi:softprob",
            eval_metric="mlogloss",
            tree_method="hist",
            random_state=semente,
            n_jobs=-1,
            **params,
        )
    if algoritmo == "logistic_regression":
        if balancear:
            params.setdefault("class_weight", "balanced")
        params.setdefault("max_iter", 3000)
        return LogisticRegression(random_state=semente, **params)
    if algoritmo == "hist_gradient_boosting":
        if balancear:
            params.setdefault("class_weight", "balanced")
        return HistGradientBoostingClassifier(random_state=semente, **params)
    raise ValueError(f"Algoritmo não suportado: {algoritmo}. Use um de {ALGORITMOS}.")


def construir_pipeline(cfg: dict, features: list[str], spec: dict, semente: int) -> Pipeline:
    return Pipeline(
        [
            ("preprocessamento", construir_preprocessador(cfg)),
            ("selecao", SeletorColunas(list(features))),
            ("modelo", criar_estimador(spec, semente, cfg["modelos"].get("balancear_classes", True))),
        ]
    )


def ajustar(pipe: Pipeline, X: pd.DataFrame, y: np.ndarray, spec: dict, cfg: dict) -> Pipeline:
    """Ajusta o pipeline. XGBoost não tem class_weight: usa pesos balanceados por amostra."""
    kwargs = {}
    if cfg["modelos"].get("balancear_classes", True) and spec["algoritmo"] == "xgboost":
        kwargs["modelo__sample_weight"] = compute_sample_weight("balanced", y)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        pipe.fit(X, y, **kwargs)
    return pipe


def codificar_alvo(y: pd.Series, classes: list[str]) -> np.ndarray:
    mapa = {c: i for i, c in enumerate(classes)}
    codificado = y.map(mapa)
    if codificado.isna().any():
        raise ValueError("Rótulos fora das classes configuradas.")
    return codificado.to_numpy(dtype=int)


def calcular_metricas(y_true: np.ndarray, proba: np.ndarray, classes: list[str]) -> dict:
    y_pred = proba.argmax(axis=1)
    rotulos = list(range(len(classes)))
    m = {
        "f1_macro": f1_score(y_true, y_pred, average="macro", labels=rotulos, zero_division=0),
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "precision_macro": precision_score(y_true, y_pred, average="macro", labels=rotulos, zero_division=0),
        "recall_macro": recall_score(y_true, y_pred, average="macro", labels=rotulos, zero_division=0),
        "log_loss": log_loss(y_true, np.clip(proba, 1e-15, 1), labels=rotulos),
    }
    f1s = f1_score(y_true, y_pred, average=None, labels=rotulos, zero_division=0)
    recs = recall_score(y_true, y_pred, average=None, labels=rotulos, zero_division=0)
    for i, c in enumerate(classes):
        m[f"f1_{c}"] = f1s[i]
        m[f"recall_{c}"] = recs[i]
    return {k: float(v) for k, v in m.items()}


def matriz_confusao(y_true, proba, classes) -> pd.DataFrame:
    cm = confusion_matrix(y_true, proba.argmax(axis=1), labels=list(range(len(classes))))
    return pd.DataFrame(cm, index=[f"real_{c}" for c in classes], columns=[f"prev_{c}" for c in classes])


def validacao_cruzada(
    X_feat: pd.DataFrame,
    y: np.ndarray,
    folds: np.ndarray,
    features_por_fold: dict[int, list[str]],
    especificacoes: dict[str, dict],
    cfg: dict,
) -> pd.DataFrame:
    """Avalia TODOS os modelos com os mesmos folds e as mesmas features por fold."""
    classes = cfg["dados"]["classes"]
    semente = cfg["avaliacao"]["semente"]
    linhas = []
    for f in sorted(np.unique(folds)):
        treino, teste = folds != f, folds == f
        for papel, spec in especificacoes.items():
            pipe = construir_pipeline(cfg, features_por_fold[int(f)], spec, semente)
            inicio = time.perf_counter()
            ajustar(pipe, X_feat[treino], y[treino], spec, cfg)
            tempo = time.perf_counter() - inicio
            proba = pipe.predict_proba(X_feat[teste])
            linhas.append(
                {
                    "papel": papel,
                    "algoritmo": spec["algoritmo"],
                    "fold": int(f),
                    "n_treino": int(treino.sum()),
                    "n_validacao": int(teste.sum()),
                    "n_features": len(features_por_fold[int(f)]),
                    "tempo_treino_s": round(tempo, 2),
                    **calcular_metricas(y[teste], proba, classes),
                }
            )
    return pd.DataFrame(linhas)


class ModeloURL:
    """Bundle do modelo: recebe URLs cruas e devolve classes/probabilidades."""

    def __init__(self, pipeline: Pipeline, classes: list[str], features: list[str], metadados: dict, perfil_referencia=None):
        self.pipeline = pipeline
        self.classes = list(classes)
        self.features = list(features)
        self.metadados = dict(metadados)
        self.perfil_referencia = perfil_referencia

    def prever_proba_features(self, X_feat: pd.DataFrame) -> np.ndarray:
        return self.pipeline.predict_proba(X_feat)

    def prever_proba(self, urls) -> pd.DataFrame:
        X = extrair_features_lote(pd.Series(list(urls)))
        return pd.DataFrame(self.prever_proba_features(X), columns=self.classes)

    def prever(self, urls) -> list[str]:
        proba = self.prever_proba(urls)
        return [self.classes[i] for i in proba.to_numpy().argmax(axis=1)]

    def __repr__(self) -> str:
        m = self.metadados
        return f"ModeloURL({m.get('algoritmo')}, versao={m.get('versao')}, cycle_id={m.get('cycle_id')}, features={len(self.features)})"
