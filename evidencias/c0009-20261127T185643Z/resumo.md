## Ciclo `c0009-20261127T185643Z` — decisão: **MANTER**

| Campo | Valor |
|---|---|
| cycle_id | `c0009-20261127T185643Z` |
| data_version | `dv009-d59b5486` |
| gatilho | `schedule` |
| execução | https://github.com/pedrosantos2/n3_cybersecurity/actions/runs/46052988345 |
| commit | `7b915ae4f6` |

### Dados
- Lotes novos incorporados: lote_0009 (4940 registros novos únicos)
- Base consolidada: 69484 registros; partições: {'treino': 48663, 'teste': 10503, 'validacao': 10318}

### Votação de features (3 métodos)
- 29 features eleitas: `kw_cms, num_path_tokens, num_params, num_equal, num_ampersand, path_depth, num_special, tld_com, digits_in_host, num_slash, has_exec_extension, has_ip, num_hyphen, ratio_digits, ratio_letters, ratio_special, num_letters, num_digits, path_length, entropy, url_length, kw_malware, num_dots, query_length, ext_php, num_suspicious_words, has_query, tld_ip, longest_token`
- vs. c0008-20261126T185946Z: entraram -; saíram -
- Estabilidade entre folds (Jaccard médio): 0.905

### Competição (validação cruzada, f1_macro)
| Papel | Algoritmo | Média | Desvio |
|---|---|---|---|
| modelo_a | random_forest | 0.7350 | 0.0066 |
| modelo_b | xgboost | 0.7599 | 0.0042 |

Vencedor do ciclo: **modelo_b (xgboost)** — maior média de f1_macro na validação cruzada (Δ=0.0249)

### Promoção controlada (holdout de validação)
- Desafiante: 0.7594 | Vigente: 0.7705 | Δ: -0.0111 | limiar: 0.002
- Decisão: **manter** — supera_vigente: Δ=-0.0111 (desafiante 0.7594 x vigente 0.7705); limiar 0.002

### Previsões com o vigente (teste reservado)
- Vigente: v0003 | f1_macro = 0.7708 | accuracy = 0.7661
- Teste integrado: todas as verificações OK

### Monitoramento de drift (critério 10)
- Nível: **estavel**
- PSI máximo 0.004 (`tld`)
