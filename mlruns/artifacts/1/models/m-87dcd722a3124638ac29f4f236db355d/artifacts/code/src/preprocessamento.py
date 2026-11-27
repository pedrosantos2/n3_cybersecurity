"""Etapa 3 do fluxo: ETL, validação e engenharia de atributos.

* ``diagnosticar`` / ``limpar``: ausentes, duplicações, inconsistências de
  rótulo e outliers, com contagem antes/depois e justificativa de cada ação.
* ``particionar``: partição determinística por hash (treino/validação/teste).
* ``extrair_features``: atributos léxicos da URL (função sem estado, portanto
  sem risco de vazamento - não aprende nada dos dados).
* ``construir_preprocessador``: ColumnTransformer (imputação, winsorização,
  padronização e one-hot) que é SEMPRE ajustado apenas com dados de treino.
"""
from __future__ import annotations

import hashlib
import ipaddress
import math
import re
from collections import Counter
from urllib.parse import urlsplit

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# ---------------------------------------------------------------------------
# Engenharia de atributos
# ---------------------------------------------------------------------------
PALAVRAS_SUSPEITAS = (
    "login", "signin", "verify", "account", "update", "secure", "bank", "confirm",
    "password", "paypal", "ebay", "webscr", "free", "bonus", "lucky", "admin", "wp-",
)
# Grupos de palavras-chave por tipo de ameaça (conhecimento de domínio, fixo:
# não é aprendido dos dados, logo não causa vazamento).
PALAVRAS_CMS = (
    "index.php", "option=com", "itemid", "component", "view=article", "wp-content",
    "wp-includes", "administrator", "mod_", "task=", "catid", "joomla",
)
PALAVRAS_PHISHING = (
    "login", "signin", "verify", "account", "update", "secure", "bank", "confirm", "password",
    "paypal", "ebay", "webscr", "apple", "microsoft", "outlook", "office", "dropbox", "wallet", "auth",
)
PALAVRAS_MALWARE = (".exe", ".bin", ".sh", "mozi", "bins", ".apk", "download", "payload", "x86", "arm7", "mips")
_RE_EXTENSAO = re.compile(r"\.([a-z0-9]{1,5})$")
ENCURTADORES = {
    "bit.ly", "goo.gl", "tinyurl.com", "ow.ly", "t.co", "is.gd", "buff.ly", "adf.ly",
    "bitly.com", "cutt.ly", "shorturl.at", "rb.gy", "tiny.cc", "tr.im", "x.co",
}
EXTENSOES_EXECUTAVEIS = (".exe", ".zip", ".rar", ".apk", ".bin", ".scr", ".msi", ".dll", ".jar", ".sh", ".bat")
TLDS_SUSPEITAS = {"ru", "cn", "tk", "top", "xyz", "ml", "ga", "cf", "gq", "pw", "su", "cc"}
# Prefixo removido antes da extração: esquema (http://, https://...) e "www."
_RE_PREFIXO = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.\-]*://)?(?:www\d?\.)?", re.IGNORECASE)
_RE_TOKENS = re.compile(r"[A-Za-z0-9]+")
_RE_TLD = re.compile(r"^[a-z][a-z0-9\-]{0,23}$")

# Viés de coleta tratado no ETL: no dataset, quase nenhuma URL benigna traz
# esquema/"www." e todas as de defacement trazem "http://"; entre URLs só de
# domínio, 99% das benignas terminam com "/" contra 8% das de phishing.
# Atributos como has_scheme/has_https/has_www/barra final aprenderiam o FORMATO
# da fonte, não o risco da URL (ex.: "https://www.google.com" virava phishing).
# Por isso a URL é normalizada (sem esquema, sem "www." e sem "/" final) antes
# de extrair os atributos.
COLUNAS_NUMERICAS = [
    "url_length", "host_length", "path_length", "query_length",
    "num_dots", "num_slash", "num_hyphen", "num_underscore", "num_at", "num_question",
    "num_equal", "num_ampersand", "num_percent", "num_digits", "num_letters", "num_special",
    "num_subdomains", "path_depth", "num_params", "digits_in_host", "longest_token",
    "has_ip", "has_port", "is_shortener",
    "has_exec_extension", "num_suspicious_words", "tld_suspicious",
    "ratio_digits", "ratio_letters", "ratio_special", "entropy",
    "kw_cms", "kw_phishing", "kw_malware", "ext_php", "ext_html", "has_query",
    "num_path_tokens",
]
COLUNAS_CATEGORICAS = ["tld"]
COLUNAS_FEATURES = COLUNAS_NUMERICAS + COLUNAS_CATEGORICAS


def _eh_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def _entropia(texto: str) -> float:
    if not texto:
        return 0.0
    n = len(texto)
    return -sum((c / n) * math.log2(c / n) for c in Counter(texto).values())


def normalizar_url(url) -> str:
    """Remove espaços nas bordas, o esquema, o prefixo "www." e barras finais
    (diferenças de formato entre as fontes do dataset - viés de coleta)."""
    url = "" if url is None or (isinstance(url, float) and math.isnan(url)) else str(url).strip()
    return _RE_PREFIXO.sub("", url, count=1).rstrip("/")


def extrair_features(url: str) -> dict:
    """Atributos léxicos de uma URL normalizada (sem acesso à rede)."""
    url = normalizar_url(url)
    n = len(url)
    alvo = "http://" + url
    porta = None
    try:
        partes = urlsplit(alvo)
        host = (partes.hostname or "").lower()
        caminho_url, query = partes.path or "", partes.query or ""
        try:
            porta = partes.port
        except ValueError:
            porta = None
    except ValueError:  # p.ex. "Invalid IPv6 URL"
        host, caminho_url, query = "", url, ""

    eh_ip = bool(host) and _eh_ip(host)
    rotulos = [r for r in host.split(".") if r] if host and not eh_ip else []
    if eh_ip:
        tld = "ip"
    elif len(rotulos) >= 2 and _RE_TLD.match(rotulos[-1]):
        tld = rotulos[-1]
    else:
        tld = "sem_tld"

    url_baixa = url.lower()
    num_digitos = sum(c.isdigit() for c in url)
    num_letras = sum(c.isalpha() for c in url)
    num_especiais = sum(not c.isalnum() for c in url)
    tokens = _RE_TOKENS.findall(url)
    m_ext = _RE_EXTENSAO.search(caminho_url.lower())
    extensao = m_ext.group(1) if m_ext else ""

    return {
        "url_length": n,
        "host_length": len(host),
        "path_length": len(caminho_url),
        "query_length": len(query),
        "num_dots": url.count("."),
        "num_slash": url.count("/"),
        "num_hyphen": url.count("-"),
        "num_underscore": url.count("_"),
        "num_at": url.count("@"),
        "num_question": url.count("?"),
        "num_equal": url.count("="),
        "num_ampersand": url.count("&"),
        "num_percent": url.count("%"),
        "num_digits": num_digitos,
        "num_letters": num_letras,
        "num_special": num_especiais,
        "num_subdomains": max(len(rotulos) - 2, 0),
        "path_depth": len([s for s in caminho_url.split("/") if s]),
        "num_params": (query.count("&") + 1) if query else 0,
        "digits_in_host": sum(c.isdigit() for c in host),
        "longest_token": max((len(t) for t in tokens), default=0),
        "has_ip": int(eh_ip),
        "has_port": int(porta is not None),
        "is_shortener": int(host in ENCURTADORES),
        "has_exec_extension": int(caminho_url.lower().endswith(EXTENSOES_EXECUTAVEIS)),
        "num_suspicious_words": sum(url_baixa.count(p) for p in PALAVRAS_SUSPEITAS),
        "tld_suspicious": int(tld in TLDS_SUSPEITAS),
        "ratio_digits": num_digitos / n if n else 0.0,
        "ratio_letters": num_letras / n if n else 0.0,
        "ratio_special": num_especiais / n if n else 0.0,
        "entropy": _entropia(url),
        "kw_cms": sum(url_baixa.count(p) for p in PALAVRAS_CMS),
        "kw_phishing": sum(url_baixa.count(p) for p in PALAVRAS_PHISHING),
        "kw_malware": sum(url_baixa.count(p) for p in PALAVRAS_MALWARE),
        "ext_php": int(extensao == "php"),
        "ext_html": int(extensao in ("html", "htm")),
        "has_query": int(bool(query)),
        "num_path_tokens": len(_RE_TOKENS.findall(caminho_url)),
        "tld": tld,
    }


def extrair_features_lote(urls) -> pd.DataFrame:
    """Aplica ``extrair_features`` a uma coleção de URLs (mantém o índice)."""
    indice = urls.index if isinstance(urls, pd.Series) else None
    linhas = [extrair_features(u) for u in urls]
    return pd.DataFrame(linhas, columns=COLUNAS_FEATURES, index=indice)


# ---------------------------------------------------------------------------
# Diagnóstico e limpeza
# ---------------------------------------------------------------------------
def diagnosticar(df: pd.DataFrame, cfg: dict) -> dict:
    """Indicadores de qualidade de um conjunto bruto (usado antes e depois)."""
    col_url, col_alvo = cfg["dados"]["coluna_url"], cfg["dados"]["coluna_alvo"]
    classes = set(cfg["dados"]["classes"])
    url = df[col_url]
    alvo = df[col_alvo]
    url_txt = url.fillna("").astype(str)
    url_norm = url_txt.str.strip()
    comp = url_norm.str.len()
    validas = url_norm[url_norm != ""]
    rotulos_por_url = df.assign(_u=url_norm).dropna(subset=[col_alvo]).groupby("_u")[col_alvo].nunique()
    q1, q3 = (comp.quantile(0.25), comp.quantile(0.75)) if len(comp) else (0, 0)
    limite_iqr = q3 + 3 * (q3 - q1)
    return {
        "linhas": int(len(df)),
        "url_ausente": int(url.isna().sum()),
        "alvo_ausente": int(alvo.isna().sum()),
        "url_vazia": int(((url_norm == "") & url.notna()).sum()),
        "espacos_nas_bordas": int((url_txt != url_norm).sum()),
        "rotulo_invalido": int((alvo.notna() & ~alvo.astype(str).str.strip().str.lower().isin(classes)).sum()),
        "linhas_duplicadas": int(df.duplicated(subset=[col_url, col_alvo]).sum()),
        "urls_repetidas": int(validas.duplicated().sum()),
        "urls_com_rotulos_conflitantes": int((rotulos_por_url > 1).sum()),
        "comprimento_mediano": float(comp.median()) if len(comp) else 0.0,
        "comprimento_p99": float(comp.quantile(0.99)) if len(comp) else 0.0,
        "comprimento_maximo": int(comp.max()) if len(comp) else 0,
        "outliers_comprimento_iqr3": int((comp > limite_iqr).sum()),
        "acima_comprimento_maximo": int((comp > cfg["dados"]["qualidade"]["comprimento_maximo_url"]).sum()),
        "distribuicao_classes": {str(k): int(v) for k, v in alvo.value_counts(dropna=True).items()},
    }


def limpar(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, list[dict]]:
    """Aplica os tratamentos justificados e devolve (dados limpos, log de ações).

    A ordem de ``df`` importa: em duplicações, a PRIMEIRA ocorrência (lote mais
    antigo) é mantida, então registros repetidos em lotes novos não entram de novo.
    """
    col_url, col_alvo = cfg["dados"]["coluna_url"], cfg["dados"]["coluna_alvo"]
    qual = cfg["dados"]["qualidade"]
    classes = cfg["dados"]["classes"]
    acoes: list[dict] = []

    def registrar(acao, antes, depois, justificativa):
        acoes.append({"acao": acao, "removidos": int(antes - depois), "restantes": int(depois), "justificativa": justificativa})

    d = df.copy()
    n = len(d)
    d = d.dropna(subset=[col_url, col_alvo])
    registrar("remover_ausentes", n, len(d), "Sem URL ou sem rótulo não há como extrair atributos nem supervisionar.")

    n = len(d)
    d[col_url] = d[col_url].astype(str).str.strip()
    d = d[d[col_url] != ""]
    registrar("normalizar_e_remover_vazias", n, len(d), "Espaços nas bordas são ruído de coleta; URL vazia é inválida.")

    n = len(d)
    d[col_alvo] = d[col_alvo].astype(str).str.strip().str.lower()
    d = d[d[col_alvo].isin(classes)]
    registrar("remover_rotulos_invalidos", n, len(d), f"Somente as classes previstas no problema: {classes}.")

    n = len(d)
    d = d[d[col_url].str.len() <= qual["comprimento_maximo_url"]]
    registrar(
        "remover_urls_corrompidas",
        n,
        len(d),
        f"URLs acima de {qual['comprimento_maximo_url']} caracteres excedem limites práticos de navegadores/servidores "
        "e indicam registros concatenados. Demais outliers são mantidos (URLs longas são informativas) e "
        "tratados por winsorização ajustada no treino.",
    )

    if qual.get("remover_conflitos_rotulo", True):
        n = len(d)
        n_rotulos = d.groupby(col_url)[col_alvo].transform("nunique")
        d = d[n_rotulos == 1]
        registrar("remover_conflitos_de_rotulo", n, len(d), "A mesma URL com rótulos diferentes é inconsistente (rótulo não confiável).")

    n = len(d)
    d = d.drop_duplicates(subset=[col_url], keep="first")
    registrar("remover_duplicadas", n, len(d), "Cada URL entra uma única vez; mantém a ocorrência do lote mais antigo.")
    return d.reset_index(drop=True), acoes


# ---------------------------------------------------------------------------
# Particionamento determinístico
# ---------------------------------------------------------------------------
def particionar(urls: pd.Series, cfg: dict) -> pd.Series:
    """Partição por hash da URL: estável entre ciclos e entre máquinas."""
    p = cfg["particionamento"]
    sal = p["sal"]
    p_teste, p_val = p["proporcao_teste"], p["proporcao_validacao"]

    def bucket(u: str) -> float:
        return int(hashlib.sha256(f"{sal}|{u}".encode("utf-8")).hexdigest()[:12], 16) / float(16**12)

    b = urls.map(bucket)
    return pd.Series(
        np.where(b < p_teste, "teste", np.where(b < p_teste + p_val, "validacao", "treino")),
        index=urls.index,
        name="particao",
    )


# ---------------------------------------------------------------------------
# Pré-processamento ajustável (somente no treino)
# ---------------------------------------------------------------------------
class RecorteQuantis(BaseEstimator, TransformerMixin):
    """Winsorização: limita cada coluna aos quantis aprendidos no treino."""

    def __init__(self, inferior: float = 0.001, superior: float = 0.999):
        self.inferior = inferior
        self.superior = superior

    def fit(self, X, y=None):
        arr = np.asarray(X, dtype=float)
        self.limites_inferiores_ = np.nanquantile(arr, self.inferior, axis=0)
        self.limites_superiores_ = np.nanquantile(arr, self.superior, axis=0)
        self.n_features_in_ = arr.shape[1]
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        return self

    def transform(self, X):
        arr = np.clip(np.asarray(X, dtype=float), self.limites_inferiores_, self.limites_superiores_)
        if hasattr(X, "columns"):
            return pd.DataFrame(arr, columns=X.columns, index=X.index)
        return arr

    def get_feature_names_out(self, input_features=None):
        if input_features is not None:
            return np.asarray(input_features, dtype=object)
        return getattr(self, "feature_names_in_", np.array([f"x{i}" for i in range(self.n_features_in_)], dtype=object))


def construir_preprocessador(cfg: dict) -> ColumnTransformer:
    pp = cfg["preprocessamento"]
    numerico = Pipeline(
        [
            ("imputador", SimpleImputer(strategy="median")),
            ("winsorizacao", RecorteQuantis(pp["recorte_quantil_inferior"], pp["recorte_quantil_superior"])),
            ("padronizacao", StandardScaler()),
        ]
    )
    categorico = Pipeline(
        [
            ("imputador", SimpleImputer(strategy="constant", fill_value="desconhecido")),
            (
                "onehot",
                OneHotEncoder(
                    handle_unknown="infrequent_if_exist",
                    min_frequency=pp["onehot_min_frequencia"],
                    sparse_output=False,
                ),
            ),
        ]
    )
    ct = ColumnTransformer(
        [("num", numerico, COLUNAS_NUMERICAS), ("cat", categorico, COLUNAS_CATEGORICAS)],
        verbose_feature_names_out=False,
    )
    return ct.set_output(transform="pandas")
