## Ciclo `c0003-20261121T164655Z` — decisão: **MANTER**

| Campo | Valor |
|---|---|
| cycle_id | `c0003-20261121T164655Z` |
| data_version | `dv003-87c663bd` |
| gatilho | `schedule` |
| execução | https://github.com/pedrosantos2/n3_cybersecurity/actions/runs/44926352826 |
| commit | `433d06f083` |

### Dados
- Lotes novos incorporados: lote_0003 (4950 registros novos únicos)
- Base consolidada: 39785 registros; partições: {'treino': 27929, 'teste': 5969, 'validacao': 5887}

### Votação de features (3 métodos)
- 31 features eleitas: `kw_cms, num_params, path_length, num_path_tokens, num_letters, num_slash, query_length, tld_com, path_depth, has_exec_extension, num_ampersand, has_ip, has_query, ratio_digits, ratio_letters, digits_in_host, ratio_special, num_digits, url_length, num_equal, num_special, entropy, num_hyphen, kw_malware, num_question, num_dots, longest_token, host_length, ext_php, num_suspicious_words, tld_ip`
- vs. c0002-20261120T174720Z: entraram ['num_question']; saíram -
- Estabilidade entre folds (Jaccard médio): 0.892

### Competição (validação cruzada, f1_macro)
| Papel | Algoritmo | Média | Desvio |
|---|---|---|---|
| modelo_a | random_forest | 0.7321 | 0.0079 |
| modelo_b | xgboost | 0.7552 | 0.0073 |

Vencedor do ciclo: **modelo_b (xgboost)** — maior média de f1_macro na validação cruzada (Δ=0.0231)

### Promoção controlada (holdout de validação)
- Desafiante: 0.7628 | Vigente: 0.7645 | Δ: -0.0016 | limiar: 0.002
- Decisão: **manter** — supera_vigente: Δ=-0.0016 (desafiante 0.7628 x vigente 0.7645); limiar 0.002

### Previsões com o vigente (teste reservado)
- Vigente: v0002 | f1_macro = 0.7678 | accuracy = 0.7690
- Teste integrado: todas as verificações OK

### Monitoramento de drift (critério 10)
- Nível: **estavel**
- PSI máximo 0.007 (`tld`)
