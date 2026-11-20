## Ciclo `c0002-20261120T174720Z` — decisão: **PROMOVER**

| Campo | Valor |
|---|---|
| cycle_id | `c0002-20261120T174720Z` |
| data_version | `dv002-ef484fad` |
| gatilho | `schedule` |
| execução | https://github.com/pedrosantos2/n3_cybersecurity/actions/runs/44786465060 |
| commit | `ef1e016476` |

### Dados
- Lotes novos incorporados: lote_0002 (4960 registros novos únicos)
- Base consolidada: 34835 registros; partições: {'treino': 24468, 'teste': 5200, 'validacao': 5167}

### Votação de features (3 métodos)
- 30 features eleitas: `kw_cms, num_path_tokens, path_length, num_letters, num_params, num_slash, query_length, path_depth, tld_com, num_special, has_ip, num_hyphen, ratio_digits, ratio_special, ratio_letters, digits_in_host, num_equal, url_length, num_digits, has_exec_extension, num_ampersand, kw_malware, entropy, num_dots, num_suspicious_words, has_query, longest_token, host_length, ext_php, tld_ip`
- vs. c0001-20261119T181544Z: entraram ['host_length']; saíram ['num_question']
- Estabilidade entre folds (Jaccard médio): 0.906

### Competição (validação cruzada, f1_macro)
| Papel | Algoritmo | Média | Desvio |
|---|---|---|---|
| modelo_a | random_forest | 0.7320 | 0.0088 |
| modelo_b | xgboost | 0.7546 | 0.0109 |

Vencedor do ciclo: **modelo_b (xgboost)** — maior média de f1_macro na validação cruzada (Δ=0.0226)

### Promoção controlada (holdout de validação)
- Desafiante: 0.7682 | Vigente: 0.7532 | Δ: 0.0150 | limiar: 0.002
- Decisão: **promover** — todas as regras de promoção foram satisfeitas

### Previsões com o vigente (teste reservado)
- Vigente: v0002 | f1_macro = 0.7713 | accuracy = 0.7713
- Teste integrado: todas as verificações OK

### Monitoramento de drift (critério 10)
- Nível: **estavel**
- PSI máximo 0.005 (`tld`)
