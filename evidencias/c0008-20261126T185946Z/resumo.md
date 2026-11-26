## Ciclo `c0008-20261126T185946Z` — decisão: **MANTER**

| Campo | Valor |
|---|---|
| cycle_id | `c0008-20261126T185946Z` |
| data_version | `dv008-b8cc0f28` |
| gatilho | `schedule` |
| execução | https://github.com/pedrosantos2/n3_cybersecurity/actions/runs/45880089431 |
| commit | `1ca1ea2ef6` |

### Dados
- Lotes novos incorporados: lote_0008 (4956 registros novos únicos)
- Base consolidada: 64544 registros; partições: {'treino': 45235, 'teste': 9751, 'validacao': 9558}

### Votação de features (3 métodos)
- 29 features eleitas: `kw_cms, num_path_tokens, num_params, path_length, num_letters, num_slash, tld_com, query_length, path_depth, num_ampersand, has_exec_extension, has_ip, ratio_letters, ratio_digits, num_equal, num_digits, ratio_special, num_special, digits_in_host, entropy, url_length, kw_malware, num_hyphen, num_dots, ext_php, longest_token, has_query, num_suspicious_words, tld_ip`
- vs. c0007-20261125T191453Z: entraram -; saíram ['host_length']
- Estabilidade entre folds (Jaccard médio): 0.905

### Competição (validação cruzada, f1_macro)
| Papel | Algoritmo | Média | Desvio |
|---|---|---|---|
| modelo_a | random_forest | 0.7317 | 0.0114 |
| modelo_b | xgboost | 0.7580 | 0.0096 |

Vencedor do ciclo: **modelo_b (xgboost)** — maior média de f1_macro na validação cruzada (Δ=0.0264)

### Promoção controlada (holdout de validação)
- Desafiante: 0.7559 | Vigente: 0.7711 | Δ: -0.0151 | limiar: 0.002
- Decisão: **manter** — supera_vigente: Δ=-0.0151 (desafiante 0.7559 x vigente 0.7711); limiar 0.002

### Previsões com o vigente (teste reservado)
- Vigente: v0003 | f1_macro = 0.7712 | accuracy = 0.7665
- Teste integrado: todas as verificações OK

### Monitoramento de drift (critério 10)
- Nível: **estavel**
- PSI máximo 0.005 (`tld`)
