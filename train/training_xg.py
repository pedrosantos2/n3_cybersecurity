import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
import joblib
from train.features import extract_features  

df = pd.read_csv("train/malicious_phish.csv") 

df = df[["url", "type"]].dropna()
df["url"] = df["url"].astype(str)


le = LabelEncoder()
y = le.fit_transform(df["type"])

feature_dicts = [extract_features(u) for u in df["url"]]
X = pd.DataFrame(feature_dicts)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

num_classes = len(le.classes_)
model = XGBClassifier(
    n_estimators=400,
    max_depth=7,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="multi:softprob",
    num_class=num_classes,
    eval_metric="mlogloss",
    tree_method="hist"
)

model.fit(X_train, y_train)

print("Train acc:", model.score(X_train, y_train))
print("Test  acc:", model.score(X_test, y_test))


joblib.dump(model, "xgb_url_multiclass_v2.joblib")
joblib.dump(le, "label_encoder_v2.joblib")
