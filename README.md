# 🔒 Detector de URLs Maliciosas

Sistema de detecção de URLs maliciosas usando Machine Learning (XGBoost) com FastAPI e Streamlit.

## 📋 Estrutura do Projeto

```
n3_ciencia/
├── app.py                          # API FastAPI
├── frontend.py                     # Frontend Streamlit
├── requirements.txt                # Dependências
├── xgb_url_multiclass_v2.joblib   # Modelo treinado
├── label_encoder_v2.joblib        # Encoder de labels
└── train/
    ├── features.py                 # Extração de features
    ├── training_xg.py              # Script de treinamento
    └── malicious_phish.csv         # Dataset
```

## 📥 Download do Dataset (Obrigatório)

Para treinar o modelo ou recriar o pipeline de ML, é necessário baixar o dataset de URLs maliciosas:

- Dataset: **Malicious URLs Dataset**
- Link: https://www.kaggle.com/datasets/sid321axn/malicious-urls-dataset/data

### Passos:

1. Acesse o link do dataset no Kaggle.
2. Faça login (ou crie uma conta).
3. Baixe o arquivo `.csv` (ex.: `malicious_phish.csv`).
4. Extraia / mova o arquivo `.csv` para dentro da pasta `train` do projeto:

   ```bash
   n3_ciencia/
   └── train/
       └── malicious_phish.csv
   
Certifique-se de que o nome do arquivo no diretório train seja o mesmo esperado pelos scripts (por padrão, malicious_phish.csv).

## 🚀 Como Usar

### 1. Criar e Ativar Ambiente Virtual (venv)

**Criar o ambiente virtual:**

```bash
python3 -m venv venv
```

**Ativar o ambiente virtual:**

- **macOS/Linux:**
```bash
source venv/bin/activate
```

- **Windows:**
```bash
venv\Scripts\activate
```

Você saberá que está ativo quando ver `(venv)` no início do prompt do terminal.

### 2. Instalar Dependências

Com o ambiente virtual ativado:

```bash
pip install -r requirements.txt
```

### 3. Iniciar a API (Backend)

**Com o ambiente virtual ativado**, em um terminal:

```bash
uvicorn app:app --reload
```

A API estará disponível em: `http://localhost:8000`
- Documentação automática: `http://localhost:8000/docs`

### 4. Iniciar o Frontend (Streamlit)

**Com o ambiente virtual ativado**, em outro terminal:

```bash
# Ative o venv novamente neste terminal:
source venv/bin/activate  # macOS/Linux
# ou venv\Scripts\activate  # Windows

# Execute o Streamlit:
streamlit run frontend.py
```

O frontend abrirá automaticamente no navegador em: `http://localhost:8501`

## 🎯 Funcionalidades

### API (FastAPI)
- **POST /predict**: Classifica uma URL
- **GET /health**: Verifica status da API

### Frontend (Streamlit)
- ✅ Interface amigável para análise de URLs
- 📊 Visualização de probabilidades com gráficos
- 🎨 Cards coloridos por tipo de ameaça
- 💡 Recomendações de segurança
- 📋 URLs de exemplo para teste
- 🔌 Monitoramento do status da API

## 🔍 Classificações

O modelo classifica URLs em 4 categorias:

| Categoria | Descrição | Cor |
|-----------|-----------|-----|
| 🟢 **Benign** | URL segura | Verde |
| 🟡 **Phishing** | Tentativa de roubo de dados | Laranja |
| 🔴 **Malware** | Distribuição de malware | Vermelho |
| 🟣 **Defacement** | Site comprometido | Roxo |

## 🧪 Exemplos de Teste

### Via Frontend (Streamlit)
1. Acesse `http://localhost:8501`
2. Digite uma URL ou use os exemplos
3. Clique em "Analisar"

### Via API (curl)

```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.google.com"}'
```

### Via Python

```python
import requests

response = requests.post(
    "http://localhost:8000/predict",
    json={"url": "https://www.google.com"}
)

print(response.json())
```

## 📊 Features Extraídas

O modelo analisa mais de 20 features:
- Comprimento da URL, domínio, path
- Número de pontos, barras, hífens
- Presença de HTTPS
- Detecção de IP no domínio
- TLD suspeita (.ru, .tk, etc)
- Proporção de dígitos/letras/caracteres especiais
- E mais...

## 🛠️ Tecnologias

- **Backend**: FastAPI, XGBoost, Scikit-learn, Pandas
- **Frontend**: Streamlit, Plotly
- **ML**: XGBoost Multiclass Classifier

## 📝 Notas

- Certifique-se de que ambos os arquivos `.joblib` (modelo e encoder) estejam na raiz do projeto
- A API deve estar rodando antes de iniciar o frontend
- Use Python 3.8+ para compatibilidade

## 🔧 Troubleshooting

**Ambiente virtual não ativa:**
```bash
# Certifique-se de estar no diretório correto:
cd /caminho/para/n3_ciencia

# Recrie o ambiente virtual:
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
```

**API não conecta:**
```bash
# Verifique se o venv está ativo (deve ver "(venv)" no prompt)
# Verifique se está rodando:
curl http://localhost:8000/health
```

**Erro de importação:**
```bash
# Certifique-se de que o venv está ativo, depois:
pip install -r requirements.txt --force-reinstall
```

**Frontend não abre:**
```bash
# Com o venv ativo, execute explicitamente:
python -m streamlit run frontend.py
```

**Desativar ambiente virtual:**
```bash
deactivate
```

---

