## Ciclo `c0005-20261123T211722Z` — decisão: **MANTER**

| Campo | Valor |
|---|---|
| cycle_id | `c0005-20261123T211722Z` |
| data_version | `dv005-e930a6b0` |
| gatilho | `schedule` |
| execução | https://github.com/pedrosantos2/n3_cybersecurity/actions/runs/45267993081 |
| commit | `1fdb4996ae` |

### Dados
- Lotes novos incorporados: lote_0005 (4961 registros novos únicos)
- Base consolidada: 49701 registros; partições: {'treino': 34878, 'teste': 7484, 'validacao': 7339}

### Votação de features (3 métodos)
- 29 features eleitas: `kw_cms, url_length, path_length, num_path_tokens, num_letters, query_length, num_slash, path_depth, tld_com, has_exec_extension, has_ip, has_query, host_length, ratio_letters, ratio_digits, num_params, digits_in_host, ratio_special, num_digits, entropy, num_ampersand, num_equal, num_special, num_question, kw_malware, num_dots, ext_php, longest_token, tld_ip`
- vs. c0004-20261122T170836Z: entraram ['has_exec_extension']; saíram ['num_hyphen', 'num_suspicious_words']
- Estabilidade entre folds (Jaccard médio): 0.936

### Competição (validação cruzada, f1_macro)
| Papel | Algoritmo | Média | Desvio |
|---|---|---|---|
| modelo_a | random_forest | 0.7363 | 0.0034 |
| modelo_b | xgboost | 0.7638 | 0.0044 |

Vencedor do ciclo: **modelo_b (xgboost)** — maior média de f1_macro na validação cruzada (Δ=0.0274)

### Promoção controlada (holdout de validação)
- Desafiante: 0.7588 | Vigente: 0.7645 | Δ: -0.0057 | limiar: 0.002
- Decisão: **manter** — supera_vigente: Δ=-0.0057 (desafiante 0.7588 x vigente 0.7645); limiar 0.002

### Previsões com o vigente (teste reservado)
- Vigente: v0002 | f1_macro = 0.7676 | accuracy = 0.7692
- Teste integrado: todas as verificações OK

### Monitoramento de drift (critério 10)
- Nível: **estavel**
- PSI máximo 0.008 (`tld`)
