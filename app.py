"""API de classificação de URLs servindo SEMPRE o modelo vigente do pipeline.

O modelo não é mais um arquivo fixo: a API lê ``models/modelo_vigente.json``
(manifesto mantido pelo notebook 04), carrega o bundle versionado indicado
(pré-processamento + features eleitas + estimador, com hash SHA-256 conferido)
e recarrega automaticamente quando o manifesto muda (nova promoção).

    uvicorn app:app --reload        # http://localhost:8000/docs
"""
from __future__ import annotations

import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.promocao import ARQUIVO_MANIFESTO, carregar_vigente


class _ModeloVigente:
    """Cache do vigente, invalidado quando o manifesto é alterado."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mtime = None
        self.manifesto = None
        self.modelo = None

    def obter(self):
        mtime = ARQUIVO_MANIFESTO.stat().st_mtime if ARQUIVO_MANIFESTO.exists() else None
        with self._lock:
            if mtime != self._mtime:
                self.manifesto, self.modelo = carregar_vigente()
                self._mtime = mtime
        if self.modelo is None:
            raise HTTPException(
                status_code=503,
                detail="Nenhum modelo vigente. Execute o pipeline: python -m src.pipeline",
            )
        return self.manifesto, self.modelo


VIGENTE = _ModeloVigente()

app = FastAPI(
    title="URL Maliciosa - API do modelo vigente",
    version="2.0.0",
    description="Classifica URLs como benign/defacement/phishing/malware com o modelo promovido pelo pipeline MLOps.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class URLItem(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048, examples=["https://www.google.com"])


def _info_modelo(manifesto: dict) -> dict:
    v = manifesto["vigente"]
    return {k: v.get(k) for k in ("versao", "algoritmo", "cycle_id", "data_version", "valor_metrica_validacao", "promovido_em", "run_id")}


@app.get("/health")
def health_check():
    try:
        manifesto, _ = VIGENTE.obter()
        return {"status": "ok", "modelo_vigente": manifesto["vigente"]["versao"]}
    except HTTPException:
        return {"status": "sem_modelo", "modelo_vigente": None}


@app.get("/modelo")
def modelo_vigente():
    manifesto, modelo = VIGENTE.obter()
    return {
        "vigente": {**_info_modelo(manifesto), "features": modelo.features, "metrica_principal": manifesto["vigente"]["metrica_principal"]},
        "ultima_decisao": manifesto.get("ultima_decisao"),
    }


@app.post("/predict")
def predict_url(item: URLItem):
    manifesto, modelo = VIGENTE.obter()
    proba = modelo.prever_proba([item.url]).iloc[0]
    return {
        "url": item.url,
        "predicted_class": str(proba.idxmax()),
        "class_probabilities": {str(c): float(p) for c, p in proba.items()},
        "modelo": _info_modelo(manifesto),
    }
