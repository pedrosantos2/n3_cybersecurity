## Ciclo `c0004-20261122T170836Z` — decisão: **MANTER**

| Campo | Valor |
|---|---|
| cycle_id | `c0004-20261122T170836Z` |
| data_version | `dv004-e76b61ae` |
| gatilho | `schedule` |
| execução | https://github.com/pedrosantos2/n3_cybersecurity/actions/runs/45047632944 |
| commit | `98c46eaae2` |

### Dados
- Lotes novos incorporados: lote_0004 (4955 registros novos únicos)
- Base consolidada: 44740 registros; partições: {'treino': 31399, 'teste': 6735, 'validacao': 6606}

### Votação de features (3 métodos)
- 30 features eleitas: `kw_cms, num_params, num_path_tokens, num_slash, digits_in_host, path_depth, tld_com, num_ampersand, has_ip, num_hyphen, has_query, ratio_digits, ratio_letters, num_equal, ratio_special, num_letters, num_digits, num_special, path_length, url_length, entropy, num_question, kw_malware, query_length, host_length, ext_php, num_dots, longest_token, num_suspicious_words, tld_ip`
- vs. c0003-20261121T164655Z: entraram -; saíram ['has_exec_extension']
- Estabilidade entre folds (Jaccard médio): 0.955

### Competição (validação cruzada, f1_macro)
| Papel | Algoritmo | Média | Desvio |
|---|---|---|---|
| modelo_a | random_forest | 0.7342 | 0.0070 |
| modelo_b | xgboost | 0.7601 | 0.0035 |

Vencedor do ciclo: **modelo_b (xgboost)** — maior média de f1_macro na validação cruzada (Δ=0.0259)

### Promoção controlada (holdout de validação)
- Desafiante: 0.7618 | Vigente: 0.7651 | Δ: -0.0032 | limiar: 0.002
- Decisão: **manter** — supera_vigente: Δ=-0.0032 (desafiante 0.7618 x vigente 0.7651); limiar 0.002

### Previsões com o vigente (teste reservado)
- Vigente: v0002 | f1_macro = 0.7653 | accuracy = 0.7678
- Teste integrado: todas as verificações OK

### Monitoramento de drift (critério 10)
- Nível: **estavel**
- PSI máximo 0.010 (`tld`)
