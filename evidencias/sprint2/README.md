# Evidências - Sprint 2

Prints reais da execução, com o `Get-Date` aparecendo no terminal (o script imprime
a data antes de cada cenário). O jeito mais simples de gerar tudo é rodar, dentro de
`agencia/`:

```
.\demo-sprint2.ps1
```

Ele sobe as 3 agências em janelas separadas, roda o cenário e para em cada momento
em que você deve tirar o print (Win+Shift+S). Salve cada imagem aqui, com o nome
indicado na tela:

- `transferencia-assincrona.png`: uma transferência entre agências completando via
  mensageria, com o terminal do script e as janelas das Agências 0 e 1 visíveis (o
  log da origem e o do destino, com os vetores).
- `resiliencia-fila.png`: a agência 1 derrubada, a transferência respondendo 200 mesmo
  assim, a mensagem retida em `fila-agencia-1` (saída do `ver_filas.py`) e o que a
  agência 1 registra quando volta (conta não encontrada, tentativas).
- `linha-do-tempo-causal.png`: a saída do `mesclar_logs.py` com pares CONCORRENTES e o
  par CAUSAL débito -> crédito.
- `dlq.png` (funcionalidade adicional): `ver_filas.py` mostrando 1 mensagem em
  `fila-agencia-1.dlq` e os eventos `CREDITO_REMOTO_FALHOU` / `CREDITO_REMOTO_DLQ`.
  Opcional: o RabbitMQ Manager do CloudAMQP mostrando a mesma fila.

Para a regressão do frontend (JWT e telas), vale um print extra do frontend
(`frontend-vetor.png`): login, extrato com a coluna "Vetor" e o Painel das Agências.
