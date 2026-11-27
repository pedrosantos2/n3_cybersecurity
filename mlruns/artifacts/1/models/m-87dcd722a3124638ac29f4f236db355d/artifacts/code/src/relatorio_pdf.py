"""Relatório técnico do Trabalho N3 em PDF, gerado a partir das evidências.

Fonte dos números: arquivos versionados em ``evidencias/<cycle_id>/``,
``models/modelo_vigente.json``, ``models/historico_decisoes.csv`` e
``data/registro_lotes.json``. O workflow regenera o PDF a cada ciclo, então o
relatório sempre reflete as execuções reais (inclusive as agendadas).

    python -m src.relatorio pdf
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.config import RAIZ, carregar_config, ler_json
from src.preprocessamento import COLUNAS_CATEGORICAS, COLUNAS_NUMERICAS

AZUL = colors.HexColor("#1F3A5F")
CINZA = colors.HexColor("#F2F4F7")
_SUBST = {"→": "->", "Δ": "delta","≥": ">=", "≤": "<=", "≈": "~", "✓": "OK", "·": "-", "⚠️": "", "🟢": "", "🔴": "", "🟡": ""}

_estilos = getSampleStyleSheet()
E = {
    "titulo": ParagraphStyle("titulo", parent=_estilos["Title"], fontSize=20, leading=24, textColor=AZUL),
    "sub": ParagraphStyle("sub", parent=_estilos["Normal"], fontSize=12, leading=16, alignment=TA_CENTER),
    "centro": ParagraphStyle("centro", parent=_estilos["Normal"], fontSize=10, leading=14, alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", parent=_estilos["Heading1"], fontSize=14, leading=18, textColor=AZUL, spaceBefore=10, spaceAfter=6),
    "h2": ParagraphStyle("h2", parent=_estilos["Heading2"], fontSize=11.5, leading=15, textColor=AZUL, spaceBefore=8, spaceAfter=4),
    "p": ParagraphStyle("p", parent=_estilos["BodyText"], fontSize=9.5, leading=13, spaceAfter=4),
    "pq": ParagraphStyle("pq", parent=_estilos["BodyText"], fontSize=8, leading=10),
    "cel": ParagraphStyle("cel", parent=_estilos["BodyText"], fontSize=7.5, leading=9),
    "celb": ParagraphStyle("celb", parent=_estilos["BodyText"], fontSize=7.5, leading=9, textColor=colors.white, fontName="Helvetica-Bold"),
    "legenda": ParagraphStyle("legenda", parent=_estilos["Italic"], fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.grey),
}


def _t(texto) -> str:
    texto = "" if texto is None else str(texto)
    for k, v in _SUBST.items():
        texto = texto.replace(k, v)
    return texto


def P(texto, estilo="p", bruto=False) -> Paragraph:
    """Parágrafo; ``bruto=True`` permite tags simples (<b>, <i>) no texto fixo."""
    return Paragraph(_t(texto) if bruto else escape(_t(texto)), E[estilo])


def fmt(x, casas=4):
    if x is None or (isinstance(x, float) and pd.isna(x)) or x == "":
        return "-"
    if isinstance(x, (float,)):
        return f"{x:.{casas}f}"
    return str(x)


def tabela(linhas: list[list], larguras=None, cabecalho=True) -> Table:
    dados = []
    for i, linha in enumerate(linhas):
        estilo = "celb" if (cabecalho and i == 0) else "cel"
        dados.append([c if isinstance(c, Paragraph) else P(c, estilo) for c in linha])
    t = Table(dados, colWidths=larguras, repeatRows=1 if cabecalho else 0)
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9CED6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    if cabecalho:
        estilo.append(("BACKGROUND", (0, 0), (-1, 0), AZUL))
    for i in range(1 if cabecalho else 0, len(dados)):
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), CINZA))
    t.setStyle(TableStyle(estilo))
    return t


def figura(caminho: Path, legenda: str, largura_cm=16):
    if not caminho.exists():
        return []
    img = Image(str(caminho))
    proporcao = img.imageHeight / img.imageWidth
    img.drawWidth = largura_cm * cm
    img.drawHeight = largura_cm * cm * proporcao
    return [KeepTogether([img, P(legenda, "legenda")]), Spacer(1, 6)]


def _ciclos_concluidos() -> list[dict]:
    ciclos = []
    for d in sorted((RAIZ / "evidencias").glob("c[0-9][0-9][0-9][0-9]-*")):
        ctx = ler_json(d / "ciclo.json")
        if ctx and ctx.get("status") == "concluido":
            ciclos.append(ctx)
    return ciclos


def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2 * cm, 1.2 * cm, "Católica de Santa Catarina - Análise Preditiva - Trabalho N3")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


def gerar_pdf(destino: Path) -> Path:
    cfg = carregar_config()
    ciclos = _ciclos_concluidos()
    if not ciclos:
        raise RuntimeError("Nenhum ciclo concluído em evidencias/: execute o pipeline antes de gerar o relatório.")
    ult = ciclos[-1]
    EV = RAIZ / ult["dir_evidencias"]
    etl = ler_json(EV / "etl_resumo.json") or {}
    vot = ler_json(EV / "votacao_features.json") or {}
    dec = ler_json(EV / "decisao_promocao.json") or {}
    prev = ler_json(EV / "previsoes_verificacoes.json") or {}
    manifesto = ler_json(RAIZ / "models" / "modelo_vigente.json") or {}
    hist_path = RAIZ / "models" / "historico_decisoes.csv"
    historico = pd.read_csv(hist_path) if hist_path.exists() else pd.DataFrame()
    metrica = cfg["avaliacao"]["metrica_principal"]
    proj = cfg["projeto"]
    s: list = []

    # ------------------------------------------------------------------ capa
    s += [Spacer(1, 3 * cm), P("TRABALHO AVALIATIVO N3 - ANÁLISE PREDITIVA", "titulo"), Spacer(1, 6)]
    s += [P("Projeto Integrador de MLOps: detecção de URLs maliciosas com votação de features, "
            "competição de modelos e atualização automatizada", "sub"), Spacer(1, 1.2 * cm)]
    s += [P(proj["instituicao"], "centro"), P(proj["professor"], "centro"), Spacer(1, 0.8 * cm)]
    s += [P("<b>Integrantes</b>", "centro", bruto=True)] + [P(n, "centro") for n in proj["integrantes"]]
    s += [Spacer(1, 0.8 * cm), P(f"Repositório: {proj.get('repositorio', '-')}", "centro")]
    gerado = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    s += [P(f"Relatório gerado automaticamente em {gerado} a partir das evidências versionadas "
            f"({len(ciclos)} ciclo(s) concluído(s); último: {ult['cycle_id']}).", "centro"), PageBreak()]

    # ------------------------------------------------- 1. problema e dados
    prob, dados, aval, part = cfg["problema"], cfg["dados"], cfg["avaliacao"], cfg["particionamento"]
    s += [P("1. Problema, dados e avaliação", "h1")]
    s += [P(prob["descricao"].strip())]
    s += [tabela([
        ["Item", "Definição"],
        ["Tipo de problema", "Classificação multiclasse"],
        ["Unidade de observação", prob["unidade_observacao"]],
        ["Variável-alvo", f"{prob['variavel_alvo']} - classes {', '.join(dados['classes'])}"],
        ["Atributos", f"{len(COLUNAS_NUMERICAS)} numéricos léxicos + {len(COLUNAS_CATEGORICAS)} categórico (TLD), "
                      f"extraídos só do texto da URL; {etl.get('n_colunas_transformadas', '-')} colunas após o ColumnTransformer"],
        ["Fonte / licença", f"{dados['fonte']['nome']} - {dados['fonte']['url']} - {dados['fonte']['licenca']}"],
        ["Chegada de novos registros", f"Lote inicial de {dados['chegada']['tamanho_lote_inicial']:,} linhas versionado em data/raw/; "
                                       f"a cada ciclo agendado chega um lote de {dados['chegada']['tamanho_lote_novo']:,} linhas "
                                       "(fonte pública embaralhada com semente fixa) ou qualquer CSV novo colocado em data/raw/."],
        ["Métrica principal", f"{metrica} ({aval['direcao']}). {aval['justificativa'].strip()}"],
        ["Particionamento", f"Hash SHA-256 da URL (sal fixo): teste {part['proporcao_teste']:.0%} reservado à avaliação final; "
                            f"validação {part['proporcao_validacao']:.0%} para desafiante x vigente; treino com StratifiedKFold "
                            f"k={aval['cv_folds']} para votação e eleição A x B. A mesma URL fica sempre na mesma partição."],
    ], [4 * cm, 12.5 * cm])]
    pxc = etl.get("particao_x_classe") or {}
    if pxc:
        classes = dados["classes"]
        linhas = [["Partição", *classes, "Total"]]
        for nome in ("treino", "validacao", "teste"):
            c = pxc.get(nome, {})
            linhas.append([nome, *[c.get(k, 0) for k in classes], sum(c.values())])
        s += [Spacer(1, 6), P(f"Base consolidada no ciclo {ult['cycle_id']} (data_version {ult['data_version']}):", "pq"),
              tabela(linhas, [3 * cm] + [2.5 * cm] * (len(classes) + 1))]
    s += [P("Limitações dos dados: o dataset agrega listas públicas de origens diferentes, com vieses de formato por fonte "
            "(tratados no ETL) e ruído de rótulo; não é série temporal, e a chegada de lotes é simulada a partir da fonte.")]

    # ------------------------------------------------------------- 2. ETL
    s += [P("2. ETL e engenharia de atributos", "h1")]
    s += [P("O notebook 01 consolida os lotes incorporados na ordem de chegada, diagnostica ausentes, duplicações, "
            "inconsistências de rótulo e outliers, aplica os tratamentos abaixo e registra o diagnóstico antes/depois. "
            "Cada lote novo passa por uma validação de qualidade antes de ser incorporado (lotes com menos de "
            f"{dados['qualidade']['proporcao_minima_validos_lote']:.0%} de linhas válidas são rejeitados).")]
    acoes = etl.get("acoes") or []
    if acoes:
        s += [tabela([["Ação", "Removidos", "Restantes", "Justificativa"]] +
                     [[a["acao"], a["removidos"], a["restantes"], a["justificativa"]] for a in acoes],
                     [3.6 * cm, 1.7 * cm, 1.7 * cm, 9.5 * cm])]
    antes, depois = etl.get("antes") or {}, etl.get("depois") or {}
    if antes:
        chaves = ["linhas", "url_ausente", "alvo_ausente", "url_vazia", "rotulo_invalido", "linhas_duplicadas",
                  "urls_com_rotulos_conflitantes", "comprimento_mediano", "comprimento_p99", "comprimento_maximo",
                  "outliers_comprimento_iqr3", "acima_comprimento_maximo"]
        s += [Spacer(1, 6), tabela([["Indicador", "Antes", "Depois"]] + [[k, antes.get(k), depois.get(k)] for k in chaves],
                                   [6 * cm, 3 * cm, 3 * cm])]
    vies = etl.get("vies_coleta") or {}
    s += [P("Viés de coleta (inconsistência de formato entre fontes)", "h2")]
    s += [P("As classes vêm de fontes diferentes e cada fonte grava a URL num formato: quase nenhuma URL benigna traz esquema "
            "(http/https) ou 'www.', todas as de defacement trazem 'http://', e entre as URLs só de domínio quase todas as benignas "
            "terminam em '/', ao contrário das de phishing. Um modelo treinado assim aprende o formato da fonte, não o risco da URL "
            "(no desenvolvimento, https://www.google.com era classificada como phishing). Tratamento: a URL é normalizada sem "
            "esquema, sem 'www.' e sem '/' final antes da extração, e nenhum atributo deriva desses elementos. Na validação "
            "cruzada de desenvolvimento a F1 macro caiu de ~0,87 (com os artefatos) para ~0,76: uma métrica menor, porém honesta.")]
    if vies:
        s += [tabela([["Classe", "Com esquema", "https", "www", "'/' final (só domínio)"]] +
                     [[c, fmt(v.get("com_esquema"), 3), fmt(v.get("https"), 3), fmt(v.get("www"), 3),
                       fmt(v.get("barra_final_dominio"), 3)] for c, v in vies.items()],
                     [3.5 * cm, 3 * cm, 3 * cm, 3 * cm, 3.5 * cm])]
    s += [P("Atributos e pré-processamento", "h2")]
    s += [P(f"Atributos numéricos: {', '.join(COLUNAS_NUMERICAS)}. Categórico: TLD. A extração não tem estado (não aprende dos dados). "
            "O ColumnTransformer - imputação pela mediana, winsorização nos quantis 0,1%/99,9%, padronização e one-hot do TLD com "
            "categoria 'infrequente' - é ajustado somente com dados de treino (e refeito dentro de cada fold na validação cruzada) "
            "e serializado dentro do pipeline de cada modelo.")]
    s += figura(EV / "etl_distribuicoes.png", "Figura 1 - Distribuição das classes e comprimento da URL por classe (último ciclo).", 15)

    # ------------------------------------------------- 3. votação
    regra = vot.get("regra") or cfg["votacao"]
    s += [PageBreak(), P("3. Três métodos de seleção e votação de features", "h1")]
    s += [P("No notebook 02, sobre o treino do ciclo pré-processado: (1) SelectKBest com informação mútua - estatística não "
            "paramétrica adequada a alvo multiclasse; (2) importância MDI de Random Forest; (3) RFE com Regressão Logística "
            "multinomial sobre dados padronizados. Cada método entrega ranking completo e um top-k.")]
    s += [P(f"<b>Regra de votação definida antes da comparação (config.yaml):</b> cada método elege o top-{regra['top_k']}; "
            f"a feature é eleita com pelo menos {regra['votos_minimos']} de 3 votos; mínimo de {regra['min_features']} "
            f"(completado pelo menor rank médio) e máximo de {regra['max_features']} (corte pelo maior rank médio); "
            "desempate pelo rank médio e, depois, ordem alfabética. A seleção é ajustada só no treino e refeita dentro de cada "
            "fold da validação cruzada.", bruto=True)]
    tab_path = EV / "votacao_tabela.csv"
    if tab_path.exists():
        tv = pd.read_csv(tab_path).head(36)
        s += [tabela([["Feature", "Votos", "Rank SKB", "Rank RF", "Rank RFE", "Rank médio", "Eleita", "Motivo"]] +
                     [[r.feature, r.votos, r.rank_selectkbest, r.rank_random_forest, r.rank_rfe, f"{r.rank_medio:.1f}",
                       "sim" if r.eleita else "não", r.motivo] for r in tv.itertuples()],
                     [3.4 * cm, 1.1 * cm, 1.4 * cm, 1.3 * cm, 1.4 * cm, 1.5 * cm, 1.1 * cm, 5.3 * cm])]
    est = vot.get("estabilidade") or {}
    mud = vot.get("mudancas") or {}
    s += [Spacer(1, 4), P(f"Features eleitas no ciclo {ult['cycle_id']} ({len(vot.get('eleitas', []))}): {', '.join(vot.get('eleitas', []))}.")]
    if est:
        s += [P(f"Estabilidade: Jaccard médio entre os conjuntos eleitos nos folds = {est['jaccard_medio_entre_folds']:.3f}; "
                f"entre cada fold e o conjunto do ciclo = {est['jaccard_medio_vs_ciclo']:.3f}.")]
    if mud.get("ciclo_anterior"):
        s += [P(f"Em relação ao ciclo {mud['ciclo_anterior']}: entraram {mud.get('entraram') or 'nenhuma'}; "
                f"saíram {mud.get('sairam') or 'nenhuma'}.")]
    s += figura(EV / "votacao_votos.png", "Figura 2 - Votos por feature (verde = eleita).", 13)

    # ------------------------------------------------- 4. comparação
    s += [PageBreak(), P("4. Comparação dos dois algoritmos", "h1")]
    especs = cfg["modelos"]
    s += [P("No notebook 03, Random Forest (modelo A) e XGBoost (modelo B) são treinados com as MESMAS features eleitas e o "
            "MESMO treino; a avaliação usa os mesmos folds estratificados e, em cada fold, as features eleitas naquele fold. "
            "Hiperparâmetros, sementes, métricas, features e o modelo serializado de ambos vão para o MLflow com o mesmo cycle_id.")]
    s += [tabela([["Papel", "Algoritmo", "Hiperparâmetros"]] +
                 [[p, especs[p]["algoritmo"], ", ".join(f"{k}={v}" for k, v in especs[p]["params"].items())] for p in ("modelo_a", "modelo_b")],
                 [2.5 * cm, 3 * cm, 11 * cm])]
    cv_path = EV / "treino_cv_folds.csv"
    if cv_path.exists():
        cv = pd.read_csv(cv_path)
        linhas = [["Papel", "Algoritmo", "F1 macro", "Accuracy", "Bal. accuracy", "Log loss", "Treino (s)"]]
        for (papel, alg), g in cv.groupby(["papel", "algoritmo"]):
            linhas.append([papel, alg] + [f"{g[c].mean():.4f} +/- {g[c].std():.4f}" for c in ("f1_macro", "accuracy", "balanced_accuracy", "log_loss")]
                          + [f"{g['tempo_treino_s'].mean():.1f}"])
        s += [Spacer(1, 6), P(f"Validação cruzada ({cfg['avaliacao']['cv_folds']} folds) no ciclo {ult['cycle_id']}:", "pq"),
              tabela(linhas, [1.8 * cm, 2.4 * cm, 2.7 * cm, 2.7 * cm, 2.7 * cm, 2.7 * cm, 1.5 * cm])]
    s += figura(EV / "treino_cv_por_fold.png", "Figura 3 - Métrica principal por fold para os dois candidatos.", 12)
    comp_path = EV / "promocao_comparacao_validacao.csv"
    if comp_path.exists():
        comp = pd.read_csv(comp_path, index_col=0)
        chaves = [k for k in ("f1_macro", "accuracy", "balanced_accuracy", "recall_benign", "recall_defacement", "recall_phishing", "recall_malware") if k in comp.index]
        s += [P("Holdout de validação (mesmos registros para todos os modelos):", "pq"),
              tabela([["Métrica", *comp.columns]] + [[k, *[fmt(float(v)) for v in comp.loc[k]]] for k in chaves],
                     [3 * cm] + [13.5 * cm / len(comp.columns)] * len(comp.columns))]

    # ------------------------------------------------- 5. promoção
    eleicao, decisao = dec.get("eleicao", {}), dec.get("decisao", {})
    s += [PageBreak(), P("5. Eleição do vencedor e decisão de promoção", "h1")]
    pr = cfg["promocao"]
    s += [P(f"<b>Eleição:</b> vence o candidato com maior média de {metrica} na validação cruzada; diferença menor que "
            f"{cfg['eleicao']['tolerancia_empate']} é empate técnico e vence o menor desvio-padrão. "
            f"<b>Promoção:</b> o vencedor do ciclo enfrenta o vigente no holdout de validação; só é promovido se superar o vigente em "
            f"pelo menos {pr['limiar_melhoria']} e atender aos pisos de salvaguarda ({metrica} >= {pr['metrica_minima']}; recall de "
            f"cada classe >= {pr['recall_minimo_por_classe']}). Inconsistências de integridade bloqueiam a promoção e interrompem o "
            "fluxo. Caso contrário, o vigente é mantido. Versões anteriores são preservadas em models/versoes/.", bruto=True)]
    if eleicao:
        s += [P(f"Ciclo {ult['cycle_id']}: vencedor {eleicao['vencedor']} ({eleicao['algoritmo_vencedor']}) - {eleicao['motivo']}.")]
    if decisao:
        s += [tabela([["Regra", "OK", "Detalhe"]] + [[c["regra"], "sim" if c["ok"] else "NÃO", c["detalhe"]] for c in decisao.get("checagens", [])],
                     [4.5 * cm, 1.2 * cm, 10.8 * cm])]
        s += [Spacer(1, 4), P(f"<b>Decisão automática: {escape(str(decisao.get('decisao')).upper())}</b> - {escape(_t(decisao.get('motivo')))}", bruto=True)]
    v = manifesto.get("vigente") or {}
    if v:
        s += [P("Manifesto do modelo vigente (models/modelo_vigente.json)", "h2"),
              tabela([["Campo", "Valor"],
                      ["Versão / algoritmo", f"{v['versao']} / {v['algoritmo']}"],
                      ["Promovido no ciclo", v["cycle_id"]], ["data_version", v["data_version"]],
                      [f"{metrica} (validação)", fmt(v["valor_metrica_validacao"])],
                      ["CV (média +/- desvio)", f"{fmt(v['metrica_cv_media'])} +/- {fmt(v['metrica_cv_desvio'])}"],
                      ["run_id (MLflow)", v["run_id"]],
                      ["Model Registry", str(v.get("modelo_registrado"))],
                      ["Arquivo / SHA-256", f"{v['arquivo_modelo']} / {v['sha256'][:16]}..."],
                      ["Features", ", ".join(v["features"])]], [4 * cm, 12.5 * cm])]
    if not historico.empty:
        s += [P("Histórico de decisões (models/historico_decisoes.csv)", "h2"),
              tabela([["Ciclo", "data_version", "Gatilho", "Vencedor", "CV venc.", "Desafiante", "Vigente", "Delta", "Decisão", "Versão"]] +
                     [[r.cycle_id[:5], r.data_version, r.gatilho, r.algoritmo_vencedor, fmt(r.cv_vencedor), fmt(r.metrica_desafiante_validacao),
                       fmt(r.metrica_vigente_validacao), fmt(r.delta), r.decisao, r.versao_vigente_apos] for r in historico.itertuples()],
                     [1.2 * cm, 2.3 * cm, 2.3 * cm, 2 * cm, 1.4 * cm, 1.6 * cm, 1.4 * cm, 1.4 * cm, 1.6 * cm, 1.3 * cm])]
    s += figura(EV / "evolucao_ciclos.png", "Figura 4 - Evolução da métrica principal entre ciclos e decisões.", 15)

    # ------------------------------------------------- 6. arquitetura
    s += [PageBreak(), P("6. Arquitetura do fluxo único", "h1")]
    etapas = [
        ["#", "Passo do fluxo", "Onde", "Saídas / evidências"],
        ["1", "Agendamento (cron diário) ou workflow_dispatch", ".github/workflows/pipeline_mlops.yml", "cycle_id, gatilho, link da execução"],
        ["2", "Entrada e versionamento de dados novos", "notebook 01 + src/ingestao.py", "data/raw/lote_*.csv, data/registro_lotes.json (SHA-256), data_version"],
        ["3", "ETL, validação e atributos", "notebook 01 + src/preprocessamento.py", "diagnóstico antes/depois, partição por hash, ColumnTransformer"],
        ["4", "Três métodos de seleção", "notebook 02 + src/features.py", "rankings SelectKBest / RF / RFE"],
        ["5", "Votação -> features eleitas", "notebook 02", "tabela de votos, conjunto do ciclo, votação por fold"],
        ["6", "Treino dos modelos A e B", "notebook 03 + src/modelagem.py", "CV com protocolo idêntico, 2 runs MLflow"],
        ["7", "Avaliação comparativa e eleição", "notebook 04 + src/promocao.py", "vencedor do ciclo"],
        ["8", "Registro no MLflow", "todos + src/rastreamento.py", "run pai do ciclo + runs filhos, Model Registry"],
        ["9", "Regra de promoção", "notebook 04", "models/modelo_vigente.json, historico_decisoes.csv, models/versoes/"],
        ["10", "Previsões com o vigente + evidências", "notebook 05", "previsões no teste, teste integrado, comparação de ciclos"],
    ]
    s += [tabela(etapas, [0.7 * cm, 4.6 * cm, 4.6 * cm, 6.6 * cm])]
    s += [Spacer(1, 6), P("Um único workflow com um único job executa, em sequência, os notebooks 01 -> 02 -> 03 -> 04 -> 05 "
            "(jupyter nbconvert --execute); qualquer erro interrompe o job antes da persistência, então nenhuma promoção indevida é "
            "gravada. Cada etapa exige que as anteriores do mesmo cycle_id/data_version estejam concluídas (src/ciclo.py).")]
    s += [P("<b>Persistência entre ciclos:</b> o estado (lotes, registro de lotes, manifesto e versões do modelo, banco SQLite e "
            "artefatos do MLflow, evidências e este relatório) é versionado no próprio repositório: o workflow o lê do checkout e, ao "
            "final, faz commit do novo estado. Nada depende de arquivos de runners anteriores. O pacote completo de cada ciclo também é "
            "publicado como artifact baixável (90 dias).", bruto=True)]
    s += [P("<b>MLflow:</b> servidor local com backend SQLite (mlruns/mlflow.db) e artefatos via proxy (mlruns/artifacts). URIs "
            "relativas (mlflow-artifacts:/) tornam o histórico consultável em qualquer máquina: python -m src.rastreamento ui. "
            "Por ciclo há um run pai (ciclo-&lt;cycle_id&gt;) com runs filhos 01_etl, 02_votacao_features, 03_modelo_a, 03_modelo_b, "
            "04_promocao e 05_previsoes, todos com as tags cycle_id e data_version.", bruto=True)]

    # ------------------------------------------------- 7. evidências
    s += [P("7. Evidências de execução", "h1")]
    linhas = [["Ciclo", "Gatilho", "data_version", "Lotes novos", "Registros", "Decisão", "Vigente", f"{metrica} teste", "Execução"]]
    for c in ciclos:
        e1 = c["etapas"].get("01_etl", {})
        e4 = c["etapas"].get("04_promocao", {})
        e5 = c["etapas"].get("05_previsoes", {})
        url = (c.get("github") or {}).get("run_url", "local")
        linhas.append([c["cycle_id"], c["gatilho"], c["data_version"], ", ".join(e1.get("lotes_novos", [])) or "-",
                       e1.get("registros", "-"), e4.get("decisao", "-"), e4.get("versao_vigente", "-"),
                       fmt((e5.get("metricas_teste") or {}).get(metrica)), url])
    s += [tabela(linhas, [2.9 * cm, 1.8 * cm, 2 * cm, 1.5 * cm, 1.4 * cm, 1.4 * cm, 1.2 * cm, 1.4 * cm, 3 * cm])]
    contagem = pd.Series([c["gatilho"] for c in ciclos]).value_counts().to_dict()
    contagem_txt = "; ".join(f"{k}: {v}" for k, v in contagem.items())
    s += [Spacer(1, 4), P(f"Ciclos concluídos por gatilho - {contagem_txt}. Execuções com gatilho 'schedule' comprovam o agendamento; "
                          "os logs ficam na aba Actions e os notebooks executados (com saídas) em evidencias/&lt;cycle_id&gt;/notebooks/.", bruto=True)]
    if prev:
        mt = prev.get("metricas_teste", {})
        s += [P(f"Avaliação final do vigente ({prev.get('vigente')}) no teste reservado do último ciclo: "
                f"{metrica} = {fmt(mt.get(metrica))}, accuracy = {fmt(mt.get('accuracy'))}, balanced accuracy = {fmt(mt.get('balanced_accuracy'))}.")]
        s += [tabela([["Verificação automática (notebook 05)", "OK"]] + [[x["verificacao"], "sim" if x["ok"] else "NÃO"] for x in prev.get("verificacoes", [])],
                     [13 * cm, 2 * cm])]

    # ------------------------------------------------- 8. critério 10
    s += [PageBreak(), P("8. Critério 10 - Monitoramento de drift com alerta", "h1")]
    s += [P("<b>Problema identificado.</b> URLs maliciosas mudam rápido (novos TLDs, encurtadores, campanhas). O pipeline re-treina a "
            "cada ciclo, mas sem monitoramento ninguém sabe quando os dados que chegam deixaram de se parecer com os dados do modelo "
            "vigente, nem se o vigente já erra mais no lote novo - informação necessária para interpretar e auditar a decisão de manter "
            "ou promover.", bruto=True)]
    s += [P("<b>Justificativa.</b> Não é exigido pelos critérios 1-9 e responde a uma necessidade real de operação: o vigente atende "
            "usuários (API/painel) entre ciclos, e drift é o primeiro sinal de que ele pode estar desatualizado.", bruto=True)]
    s += [P("<b>Solução implementada.</b> Ao promover um modelo, um perfil de referência das features do seu treino (bins por quantis "
            "e frequência de TLD) é salvo no bundle. A cada ciclo, o notebook 01 calcula o PSI de cada feature do lote novo contra esse "
            "perfil e a F1 macro do vigente no lote novo (rotulado) antes do re-treino. Níveis: estável (PSI &lt; "
            f"{cfg['monitoramento']['psi_atencao']}), atenção, alerta (PSI >= {cfg['monitoramento']['psi_alerta']} ou queda de F1 >= "
            f"{cfg['monitoramento']['queda_f1_alerta']}).", bruto=True)]
    s += [P("<b>Ponto de integração.</b> notebook 01 (cálculo, MLflow: psi_max, f1_vigente_lote_novo, tag nivel_drift) e passo "
            "'Notificações' do workflow (python -m src.monitoramento alertar): anotação ::warning::, painel no resumo do job e abertura "
            "automática de issue no repositório em caso de alerta.", bruto=True)]
    linhas = [["Ciclo", "Nível", "PSI máx (feature)", "F1 vigente no lote", "Queda", "Controle enviesado (PSI máx)"]]
    for c in ciclos:
        m = ler_json(RAIZ / c["dir_evidencias"] / "monitoramento_drift.json") or {}
        d, dv, ts = m.get("drift") or {}, m.get("desempenho_vigente_no_lote") or {}, m.get("teste_sensibilidade") or {}
        linhas.append([c["cycle_id"], m.get("nivel", "-"),
                       f"{d['psi_max']:.3f} ({d['feature_psi_max']})" if d else "-",
                       fmt(dv.get("f1_macro_lote")), fmt(dv.get("queda_f1")),
                       f"{ts['psi_max']:.3f} -> {ts['nivel_drift']}" if ts else "-"])
    s += [P("<b>Resultado demonstrado.</b> Tabela por ciclo; a coluna 'controle enviesado' aplica o mesmo detector a uma amostra "
            "deliberadamente deslocada (apenas phishing) e mostra que o alerta dispara quando há drift real.", bruto=True),
          tabela(linhas, [3.2 * cm, 1.8 * cm, 3.6 * cm, 2.4 * cm, 1.6 * cm, 3.9 * cm])]

    # ------------------------------------------------- 9. limitações / conclusões
    s += [P("9. Limitações e conclusões", "h1")]
    lim = [
        "Dados: listas públicas heterogêneas, com vieses de formato (tratados no ETL) e ruído de rótulo - por exemplo, páginas de "
        "tools.ietf.org rotuladas como phishing; as métricas valem para este dataset, não para tráfego real.",
        "Atributos apenas léxicos (sem WHOIS, conteúdo da página ou reputação), o que limita a separação entre phishing e benign: "
        "domínios curtos sem caminho (ex.: google.com) são a região de maior sobreposição e podem ser classificados como phishing.",
        "A chegada de lotes é simulada a partir de uma permutação da fonte; drift real tende a ser maior que o observado.",
        "O holdout de validação é reutilizado nas decisões de promoção ao longo dos ciclos (o teste permanece intocado), o que pode "
        "gerar leve otimismo acumulado na métrica de validação.",
        "O estado versionado no Git cresce a cada ciclo (modelos e MLflow); para operação longa, migrar para armazenamento de objetos.",
        "O GitHub pode atrasar execuções agendadas; o cron usa minuto 'quebrado' e há workflow_dispatch para depuração.",
    ]
    s += [P(f"- {x}") for x in lim]
    if v:
        s += [Spacer(1, 4), P(f"Conclusão: o fluxo único executa automaticamente, a cada ciclo, ingestão versionada, ETL sem vazamento, "
                              f"votação entre três métodos, competição entre dois algoritmos com protocolo idêntico e promoção controlada "
                              f"com rastreabilidade completa no MLflow. O vigente atual é {v['versao']} ({v['algoritmo']}), com {metrica} "
                              f"de validação {fmt(v['valor_metrica_validacao'])}, servido pela API/painel do repositório.")]

    destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(destino), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Trabalho N3 - Análise Preditiva - Relatório técnico", author=", ".join(proj["integrantes"]))
    doc.build(s, onFirstPage=_rodape, onLaterPages=_rodape)
    return destino
