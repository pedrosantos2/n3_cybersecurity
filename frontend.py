import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configuração da página
st.set_page_config(
    page_title="Detector de URLs Maliciosas",
    page_icon="🔒",
    layout="wide"
)

# URL da API
API_URL = "http://localhost:8000"

# Título e descrição
st.title("🔒 Detector de URLs Maliciosas")
st.markdown("""
Este aplicativo usa o **modelo vigente** do pipeline MLOps (eleito e promovido automaticamente a cada ciclo) para classificar URLs em:
- **Benign**: URLs seguras
- **Phishing**: Tentativas de roubo de informações
- **Malware**: URLs que distribuem software malicioso
- **Defacement**: URLs comprometidas/alteradas
""")

if "url_input" not in st.session_state:
    st.session_state["url_input"] = ""

# Sidebar com informações
with st.sidebar:
    st.header("ℹ️ Modelo vigente")
    try:
        info = requests.get(f"{API_URL}/modelo", timeout=3).json()
        v = info["vigente"]
        st.info(
            f"**Versão:** {v['versao']} ({v['algoritmo']})\n\n"
            f"**Promovido no ciclo:** `{v['cycle_id']}`\n\n"
            f"**data_version:** `{v['data_version']}`\n\n"
            f"**{v['metrica_principal']} (validação):** {v['valor_metrica_validacao']:.4f}\n\n"
            f"**Features eleitas:** {len(v['features'])}"
        )
        dec = info.get("ultima_decisao") or {}
        if dec:
            st.caption(f"Última decisão ({dec.get('cycle_id')}): **{dec.get('decisao')}** — {dec.get('motivo')}")
    except Exception:
        st.warning("Informações do modelo indisponíveis.")

    # Status da API
    st.header("🔌 Status da API")
    try:
        response = requests.get(f"{API_URL}/health", timeout=2)
        if response.status_code == 200:
            st.success("✅ API Online")
        else:
            st.error("❌ API com problemas")
    except:
        st.error("❌ API Offline")
        st.warning("Execute: `uvicorn app:app --reload`")

# Divisor
st.divider()

# Seção principal - Input
st.header("🔍 Analisar URL")

col1, col2 = st.columns([3, 1])

def _usar_exemplo(url: str) -> None:
    st.session_state["url_input"] = url


with col1:
    url_input = st.text_input(
        "Digite a URL para análise:",
        placeholder="https://exemplo.com",
        help="Cole aqui a URL que deseja verificar",
        key="url_input",
    )

with col2:
    st.write("")
    st.write("")
    analyze_button = st.button("🚀 Analisar", type="primary", use_container_width=True)

# Exemplos reais do conjunto de teste do dataset (preenchem o campo via session_state)
with st.expander("📋 URLs de Exemplo (do conjunto de teste)"):
    col1, col2, col3, col4 = st.columns(4)
    col1.button("🟢 Benign", use_container_width=True, on_click=_usar_exemplo, args=("youtube.com/watch?v=lDnPb7njHUQ",))
    col2.button("🔴 Phishing", use_container_width=True, on_click=_usar_exemplo, args=("http://drive-google-com.fanalav.com/5e858109c170e2415e660a1e0421acdc/",))
    col3.button("🔴 Malware", use_container_width=True, on_click=_usar_exemplo, args=("http://167.114.129.9/bins/dark.arm6",))
    col4.button("🔴 Defacement", use_container_width=True, on_click=_usar_exemplo, args=("http://www.ekino-neureut.de/index.php?option=com_xmap&sitemap=1&Itemid=28",))
    st.caption("O modelo usa apenas o texto da URL. Domínios curtos sem caminho (ex.: google.com) são ambíguos nesta base e podem ser classificados de forma errada.")

# Processamento da análise
if analyze_button and url_input:
    with st.spinner("🔄 Analisando URL..."):
        try:
            # Chamada para a API
            response = requests.post(
                f"{API_URL}/predict",
                json={"url": url_input},
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Resultados
                st.divider()
                st.header("📊 Resultado da Análise")
                
                # Classe predita com destaque
                predicted_class = result["predicted_class"]
                
                # Cores por classe
                color_map = {
                    "benign": "green",
                    "phishing": "orange",
                    "malware": "red",
                    "defacement": "purple"
                }
                
                # Emojis por classe
                emoji_map = {
                    "benign": "✅",
                    "phishing": "⚠️",
                    "malware": "🚨",
                    "defacement": "🔓"
                }
                
                color = color_map.get(predicted_class.lower(), "gray")
                emoji = emoji_map.get(predicted_class.lower(), "❓")
                
                # Card de resultado
                st.markdown(f"""
                <div style="
                    padding: 20px;
                    border-radius: 10px;
                    border: 3px solid {color};
                    background-color: rgba(255,255,255,0.05);
                    text-align: center;
                    margin: 20px 0;
                ">
                    <h1 style="margin: 0; color: {color};">{emoji} {predicted_class.upper()}</h1>
                    <p style="margin: 10px 0 0 0; font-size: 18px;">URL classificada como: <strong>{predicted_class}</strong></p>
                </div>
                """, unsafe_allow_html=True)
                
                # Probabilidades
                st.subheader("📈 Probabilidades por Classe")
                
                probs = result["class_probabilities"]
                
                # Criar dataframe para visualização
                df_probs = pd.DataFrame({
                    "Classe": list(probs.keys()),
                    "Probabilidade": [p * 100 for p in probs.values()]
                })
                df_probs = df_probs.sort_values("Probabilidade", ascending=False)
                
                # Gráfico de barras horizontal
                fig = px.bar(
                    df_probs,
                    x="Probabilidade",
                    y="Classe",
                    orientation="h",
                    text=df_probs["Probabilidade"].apply(lambda x: f"{x:.1f}%"),
                    color="Classe",
                    color_discrete_map={
                        "benign": "#28a745",
                        "phishing": "#ffc107",
                        "malware": "#dc3545",
                        "defacement": "#6f42c1"
                    }
                )
                
                fig.update_layout(
                    showlegend=False,
                    height=300,
                    xaxis_title="Probabilidade (%)",
                    yaxis_title="",
                    xaxis_range=[0, 100]
                )
                
                fig.update_traces(textposition="outside")
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Tabela de probabilidades
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📋 Detalhes")
                    st.markdown(f"""
                    - **URL analisada:** `{result['url']}`
                    - **Classificação:** **{predicted_class.upper()}**
                    - **Confiança:** {max(probs.values()) * 100:.2f}%
                    """)
                
                with col2:
                    st.subheader("💯 Probabilidades")
                    for classe, prob in sorted(probs.items(), key=lambda x: x[1], reverse=True):
                        st.metric(
                            label=classe.upper(),
                            value=f"{prob * 100:.2f}%"
                        )
                
                # Recomendações
                st.divider()
                st.subheader("💡 Recomendações")
                
                if predicted_class.lower() == "benign":
                    st.success("✅ Esta URL parece segura! Mas sempre mantenha cuidado ao navegar.")
                elif predicted_class.lower() == "phishing":
                    st.warning("⚠️ **ATENÇÃO!** Esta URL pode ser uma tentativa de phishing. Não forneça dados pessoais!")
                elif predicted_class.lower() == "malware":
                    st.error("🚨 **PERIGO!** Esta URL pode conter malware. Não acesse este link!")
                elif predicted_class.lower() == "defacement":
                    st.warning("🔓 Esta URL pode estar comprometida. Evite acessá-la.")
                
            else:
                st.error(f"❌ Erro na API: {response.status_code}")
                st.code(response.text)
                
        except requests.exceptions.ConnectionError:
            st.error("❌ Não foi possível conectar à API. Certifique-se de que está rodando!")
            st.code("Execute no terminal: uvicorn app:app --reload")
        except Exception as e:
            st.error(f"❌ Erro ao analisar: {str(e)}")

elif analyze_button and not url_input:
    st.warning("⚠️ Por favor, digite uma URL para analisar.")

# Footer
st.divider()
st.markdown("""
<div style="text-align: center; color: gray; padding: 20px;">
    <p>Desenvolvido com ❤️ usando Streamlit + FastAPI + pipeline MLOps (scikit-learn, XGBoost, MLflow)</p>
    <p>Para mais informações, consulte a documentação da API em <code>http://localhost:8000/docs</code></p>
</div>
""", unsafe_allow_html=True)
