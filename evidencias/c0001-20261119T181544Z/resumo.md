## Ciclo `c0001-20261119T181544Z` — decisão: **PROMOVER**

| Campo | Valor |
|---|---|
| cycle_id | `c0001-20261119T181544Z` |
| data_version | `dv001-98e802be` |
| gatilho | `schedule` |
| execução | https://github.com/pedrosantos2/n3_cybersecurity/actions/runs/44585677269 |
| commit | `c72d9c10d4` |

### Dados
- Lotes novos incorporados: lote_0001 (29875 registros novos únicos)
- Base consolidada: 29875 registros; partições: {'treino': 20990, 'teste': 4483, 'validacao': 4402}

### Votação de features (3 métodos)
- 30 features eleitas: `kw_cms, path_length, num_letters, num_path_tokens, tld_com, num_slash, query_length, path_depth, has_exec_extension, has_ip, has_query, num_hyphen, num_params, ratio_digits, ratio_special, digits_in_host, num_equal, ratio_letters, url_length, num_digits, num_special, kw_malware, entropy, longest_token, num_question, num_ampersand, num_dots, ext_php, num_suspicious_words, tld_ip`
- Estabilidade entre folds (Jaccard médio): 0.930

### Competição (validação cruzada, f1_macro)
| Papel | Algoritmo | Média | Desvio |
|---|---|---|---|
| modelo_a | random_forest | 0.7314 | 0.0075 |
| modelo_b | xgboost | 0.7506 | 0.0101 |

Vencedor do ciclo: **modelo_b (xgboost)** — maior média de f1_macro na validação cruzada (Δ=0.0192)

### Promoção controlada (holdout de validação)
- Desafiante: 0.7493 | Vigente: - | Δ: - | limiar: 0.002
- Decisão: **promover** — todas as regras de promoção foram satisfeitas

### Previsões com o vigente (teste reservado)
- Vigente: v0001 | f1_macro = 0.7545 | accuracy = 0.7562
- Teste integrado: todas as verificações OK

### Monitoramento de drift (critério 10)
- Nível: **sem_referencia**
