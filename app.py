from fastapi.middleware.cors import CORSMiddleware
from train.training_xg import extract_features
from pydantic import BaseModel
from fastapi import FastAPI
import pandas as pd
import joblib
import re

model = joblib.load("xgb_url_multiclass_v2.joblib")
le = joblib.load("label_encoder_v2.joblib")

app = FastAPI(
    title="URL Maliciosa - XGBoost API",
    version="1.0.0",
    description="API para classificar URLs como benign/phishing/malware/defacement usando XGBoost."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class URLItem(BaseModel):
    url: str


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/predict")
def predict_url(item: URLItem):
    
    features = extract_features(item.url)
    X = pd.DataFrame([features])
    
    pred_proba = model.predict_proba(X)[0]
    pred_class_idx = pred_proba.argmax()
    pred_label = le.inverse_transform([pred_class_idx])[0]
    
    class_probs = {
        str(label): float(p)
        for label, p in zip(le.classes_, pred_proba)
    }

    return {
        "url": item.url,
        "predicted_class": pred_label,
        "class_probabilities": class_probs
    }



