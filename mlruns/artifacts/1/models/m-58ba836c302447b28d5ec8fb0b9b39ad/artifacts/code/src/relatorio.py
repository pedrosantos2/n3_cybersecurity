"""Resumo de cada ciclo (Markdown) e relatório técnico em PDF.

* ``salvar_resumo_ciclo``: gera ``evidencias/<cycle_id>/resumo.md`` ao final
  do notebook 05; no GitHub Actions o mesmo texto vai para o resumo do job.
* ``python -m src.relatorio resumo``  -> imprime/anexa o resumo ao job summary
* ``python -m src.relatorio pdf``     -> gera ``reports/relatorio_n3.pdf`` a
  partir das evidências versionadas (manifesto, histórico, ciclos).
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

from src.config import RAIZ, caminho, carregar_config, configurar_saida_utf8, ler_json


def _fmt(x, casas=4):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "-"
    return f"{x:.{casas}f}" if isinstance(x, float) else str(x)


def resumo_ciclo_md(ctx: dict) -> str:
    cfg = carregar_config()
    ev = caminho(ctx["dir_evidencias"])
    metrica = cfg["avaliacao"]["metrica_principal"]
    vot = ler_json(ev / "votacao_features.json") or {}
    dec = ler_json(ev / "decisao_promocao.json") or {}
    prev = ler_json(ev / "previsoes_verificacoes.json") or {}
    mon = ler_json(ev / "monitoramento_drift.json") or {}
    etl = ctx.get("etapas", {}).get("01_etl", {})
    gh = ctx.get("github") or {}
    decisao = dec.get("decisao", {})
    eleicao = dec.get("eleicao", {})

    linhas = [
        f"## Ciclo `{ctx['cycle_id']}` — decisão: **{str(decisao.get('decisao', '-')).upper()}**",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| cycle_id | `{ctx['cycle_id']}` |",
        f"| data_version | `{ctx.get('data_version')}` |",
        f"| gatilho | `{ctx.get('gatilho')}` |",
        f"| execução | {gh.get('run_url', 'local')} |",
        f"| commit | `{(ctx.get('git_commit') or '-')[:10]}` |",
        "",
        "### Dados",
        f"- Lotes novos incorporados: {', '.join(etl.get('lotes_novos', [])) or 'nenhum'} "
        f"({etl.get('registros_novos', 0)} registros novos únicos)",
        f"- Base consolidada: {etl.get('registros', '-')} registros; partições: {etl.get('particoes', {})}",
        "",
        "### Votação de features (3 métodos)",
        f"- {len(vot.get('eleitas', []))} features eleitas: `{', '.join(vot.get('eleitas', []))}`",
    ]
    mud = vot.get("mudancas") or {}
    if mud.get("ciclo_anterior"):
        linhas.append(f"- vs. {mud['ciclo_anterior']}: entraram {mud.get('entraram') or '-'}; saíram {mud.get('sairam') or '-'}")
    if vot.get("estabilidade"):
        linhas.append(f"- Estabilidade entre folds (Jaccard médio): {vot['estabilidade']['jaccard_medio_entre_folds']:.3f}")
    linhas += ["", f"### Competição (validação cruzada, {metrica})"]
    cv_path = ev / "treino_cv_folds.csv"
    if cv_path.exists():
        cv = pd.read_csv(cv_path)
        linhas += ["| Papel | Algoritmo | Média | Desvio |", "|---|---|---|---|"]
        for (papel, alg), g in cv.groupby(["papel", "algoritmo"]):
            linhas.append(f"| {papel} | {alg} | {g[metrica].mean():.4f} | {g[metrica].std():.4f} |")
    if eleicao:
        linhas.append(f"\nVencedor do ciclo: **{eleicao['vencedor']} ({eleicao['algoritmo_vencedor']})** — {eleicao['motivo']}")
    if decisao:
        linhas += [
            "",
            "### Promoção controlada (holdout de validação)",
            f"- Desafiante: {_fmt(decisao.get('valor_desafiante'))} | Vigente: {_fmt(decisao.get('valor_vigente'))} | "
            f"Δ: {_fmt(decisao.get('delta'))} | limiar: {decisao.get('limiar')}",
            f"- Decisão: **{decisao.get('decisao')}** — {decisao.get('motivo')}",
        ]
    if prev:
        mt = prev.get("metricas_teste", {})
        ok = all(v["ok"] for v in prev.get("verificacoes", []))
        linhas += [
            "",
            "### Previsões com o vigente (teste reservado)",
            f"- Vigente: {prev.get('vigente')} | {metrica} = {_fmt(mt.get(metrica))} | accuracy = {_fmt(mt.get('accuracy'))}",
            f"- Teste integrado: {'todas as verificações OK' if ok else 'FALHAS'}",
        ]
    if mon:
        linhas += ["", "### Monitoramento de drift (critério 10)", f"- Nível: **{mon.get('nivel')}**"]
        if mon.get("drift"):
            linhas.append(f"- PSI máximo {mon['drift']['psi_max']:.3f} (`{mon['drift']['feature_psi_max']}`)")
        for m in mon.get("motivos", []):
            linhas.append(f"- {m}")
    return "\n".join(linhas) + "\n"


def salvar_resumo_ciclo(ctx: dict) -> str:
    texto = resumo_ciclo_md(ctx)
    destino = caminho(ctx["dir_evidencias"]) / "resumo.md"
    destino.write_text(texto, encoding="utf-8", newline="\n")
    return texto


def publicar_resumo() -> None:
    ctx = ler_json(RAIZ / "evidencias" / "ciclo_atual.json")
    texto = resumo_ciclo_md(ctx)
    print(texto)
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write(texto + "\n")


def main(argv: list[str] | None = None) -> None:
    configurar_saida_utf8()
    parser = argparse.ArgumentParser(description="Resumo do ciclo e relatório técnico")
    parser.add_argument("cmd", choices=["resumo", "pdf"])
    parser.add_argument("--saida", default="reports/relatorio_n3.pdf")
    args = parser.parse_args(argv)
    if args.cmd == "resumo":
        publicar_resumo()
    else:
        from src.relatorio_pdf import gerar_pdf

        print(f"Relatório gerado em {gerar_pdf(caminho(args.saida))}")


if __name__ == "__main__":
    main()
