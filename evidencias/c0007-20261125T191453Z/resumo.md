## Ciclo `c0007-20261125T191453Z` — decisão: **MANTER**

| Campo | Valor |
|---|---|
| cycle_id | `c0007-20261125T191453Z` |
| data_version | `dv007-9f944e58` |
| gatilho | `schedule` |
| execução | https://github.com/pedrosantos2/n3_cybersecurity/actions/runs/45683117851 |
| commit | `400a09339b` |

### Dados
- Lotes novos incorporados: lote_0007 (4953 registros novos únicos)
- Base consolidada: 59588 registros; partições: {'treino': 41780, 'teste': 9015, 'validacao': 8793}

### Votação de features (3 métodos)
- 30 features eleitas: `kw_cms, ratio_digits, num_path_tokens, ratio_letters, num_params, num_letters, url_length, num_ampersand, num_slash, path_depth, num_special, tld_com, ratio_special, digits_in_host, num_digits, path_length, kw_malware, entropy, has_exec_extension, num_equal, has_ip, num_hyphen, query_length, ext_php, host_length, num_dots, has_query, longest_token, num_suspicious_words, tld_ip`
- vs. c0006-20261124T200921Z: entraram -; saíram ['num_question']
- Estabilidade entre folds (Jaccard médio): 0.923

### Competição (validação cruzada, f1_macro)
| Papel | Algoritmo | Média | Desvio |
|---|---|---|---|
| modelo_a | random_forest | 0.7267 | 0.0095 |
| modelo_b | xgboost | 0.7594 | 0.0094 |

Vencedor do ciclo: **modelo_b (xgboost)** — maior média de f1_macro na validação cruzada (Δ=0.0327)

### Promoção controlada (holdout de validação)
- Desafiante: 0.7702 | Vigente: 0.7736 | Δ: -0.0035 | limiar: 0.002
- Decisão: **manter** — supera_vigente: Δ=-0.0035 (desafiante 0.7702 x vigente 0.7736); limiar 0.002

### Previsões com o vigente (teste reservado)
- Vigente: v0003 | f1_macro = 0.7707 | accuracy = 0.7667
- Teste integrado: todas as verificações OK

### Monitoramento de drift (critério 10)
- Nível: **estavel**
- PSI máximo 0.004 (`tld`)
