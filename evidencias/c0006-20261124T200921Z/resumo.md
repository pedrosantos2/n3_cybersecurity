## Ciclo `c0006-20261124T200921Z` — decisão: **PROMOVER**

| Campo | Valor |
|---|---|
| cycle_id | `c0006-20261124T200921Z` |
| data_version | `dv006-f2efc620` |
| gatilho | `schedule` |
| execução | https://github.com/pedrosantos2/n3_cybersecurity/actions/runs/45477560255 |
| commit | `147b9715bf` |

### Dados
- Lotes novos incorporados: lote_0006 (4934 registros novos únicos)
- Base consolidada: 54635 registros; partições: {'treino': 38328, 'teste': 8228, 'validacao': 8079}

### Votação de features (3 métodos)
- 31 features eleitas: `kw_cms, num_params, path_length, num_path_tokens, num_letters, num_ampersand, tld_com, num_slash, query_length, path_depth, has_query, num_equal, digits_in_host, ratio_special, ratio_letters, ratio_digits, url_length, num_digits, has_exec_extension, has_ip, entropy, num_special, kw_malware, num_hyphen, num_dots, host_length, num_question, longest_token, num_suspicious_words, ext_php, tld_ip`
- vs. c0005-20261123T211722Z: entraram ['num_hyphen', 'num_suspicious_words']; saíram -
- Estabilidade entre folds (Jaccard médio): 0.961

### Competição (validação cruzada, f1_macro)
| Papel | Algoritmo | Média | Desvio |
|---|---|---|---|
| modelo_a | random_forest | 0.7365 | 0.0029 |
| modelo_b | xgboost | 0.7611 | 0.0034 |

Vencedor do ciclo: **modelo_b (xgboost)** — maior média de f1_macro na validação cruzada (Δ=0.0246)

### Promoção controlada (holdout de validação)
- Desafiante: 0.7736 | Vigente: 0.7673 | Δ: 0.0062 | limiar: 0.002
- Decisão: **promover** — todas as regras de promoção foram satisfeitas

### Previsões com o vigente (teste reservado)
- Vigente: v0003 | f1_macro = 0.7718 | accuracy = 0.7674
- Teste integrado: todas as verificações OK

### Monitoramento de drift (critério 10)
- Nível: **estavel**
- PSI máximo 0.006 (`num_special`)
