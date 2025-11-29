import re
from urllib.parse import urlparse

def extract_features(url: str):
    # Garante que é string e tira espaços
    url = str(url).strip()
    if not url:
        # URL vazia: devolve tudo zero
        return {
            "url_length": 0,
            "domain_length": 0,
            "path_length": 0,
            "query_length": 0,
            "num_dots": 0,
            "num_slash": 0,
            "num_hyphen": 0,
            "num_at": 0,
            "num_question": 0,
            "num_equal": 0,
            "num_digits": 0,
            "num_letters": 0,
            "num_special": 0,
            "num_subdomains": 0,
            "has_https": 0,
            "has_ip": 0,
            "ratio_digits": 0,
            "ratio_letters": 0,
            "ratio_special": 0,
            "tld_suspicious": 0,
        }

    # ---- PARSE SEGURO ----
    try:
        # garante um esquema pra ajudar o parser
        url_to_parse = url if "://" in url else "http://" + url
        parsed = urlparse(url_to_parse)
        domain = parsed.netloc or ""
        path = parsed.path or ""
        query = parsed.query or ""
    except ValueError:
        # se der erro (tipo Invalid IPv6 URL), cai aqui
        domain = ""
        path = url
        query = ""

    # Partes do domínio
    domain_parts = domain.split(".") if domain else []
    tld = domain_parts[-1] if len(domain_parts) > 0 else ""
    num_subdomains = max(len(domain_parts) - 2, 0)  # ignora domínio+TLD

    # Contagens básicas
    url_length = len(url)
    domain_length = len(domain)
    path_length = len(path)
    query_length = len(query)

    num_dots = url.count(".")
    num_slash = url.count("/")
    num_hyphen = url.count("-")
    num_at = url.count("@")
    num_question = url.count("?")
    num_equal = url.count("=")

    num_digits = sum(c.isdigit() for c in url)
    num_letters = sum(c.isalpha() for c in url)
    num_special = sum(not c.isalnum() for c in url)

    has_https = int(url.startswith("https"))
    has_ip = int(bool(re.search(r"\d+\.\d+\.\d+\.\d+", domain)))

    # Proporções
    ratio_digits = num_digits / url_length if url_length > 0 else 0
    ratio_letters = num_letters / url_length if url_length > 0 else 0
    ratio_special = num_special / url_length if url_length > 0 else 0

    # TLD "suspeita" (toy example, pode mexer depois)
    suspicious_tlds = {"ru", "cn", "tk", "top", "xyz"}
    tld_suspicious = int(tld.lower() in suspicious_tlds)

    return {
        "url_length": url_length,
        "domain_length": domain_length,
        "path_length": path_length,
        "query_length": query_length,
        "num_dots": num_dots,
        "num_slash": num_slash,
        "num_hyphen": num_hyphen,
        "num_at": num_at,
        "num_question": num_question,
        "num_equal": num_equal,
        "num_digits": num_digits,
        "num_letters": num_letters,
        "num_special": num_special,
        "num_subdomains": num_subdomains,
        "has_https": has_https,
        "has_ip": has_ip,
        "ratio_digits": ratio_digits,
        "ratio_letters": ratio_letters,
        "ratio_special": ratio_special,
        "tld_suspicious": tld_suspicious,
    }
