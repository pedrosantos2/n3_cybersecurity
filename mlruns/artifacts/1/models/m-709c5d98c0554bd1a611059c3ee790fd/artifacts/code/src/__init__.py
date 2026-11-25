"""Pacote do pipeline MLOps do Trabalho N3 (detecção de URLs maliciosas).

Os notebooks em ``notebooks/`` documentam o processo e chamam as funções
reutilizáveis destes módulos:

- ``config``          carregamento da configuração e caminhos do projeto
- ``ciclo``           contexto do ciclo (cycle_id, data_version, etapas concluídas)
- ``ingestao``        chegada, registro e versionamento de lotes de dados
- ``preprocessamento``limpeza, partição, engenharia de atributos e ColumnTransformer
- ``features``        três métodos de seleção e votação de features
- ``modelagem``       algoritmos, validação cruzada, métricas e bundle do modelo
- ``promocao``        eleição do vencedor, promoção controlada e manifesto
- ``rastreamento``    integração com o MLflow (servidor com artefatos portáveis)
- ``monitoramento``   critério 10: monitoramento de drift com alerta
- ``relatorio``       resumo do ciclo e relatório técnico em PDF
- ``pipeline``        execução local do fluxo único (mesma ordem do workflow)
"""
