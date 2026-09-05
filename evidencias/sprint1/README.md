# Evidências — Sprint 1

Prints de tela reais (execução sua), com `Get-Date` visível em algum terminal
para comprovar execução recente. Capture cada arquivo abaixo. Os scripts
`agencia/demo.ps1` (PowerShell) e `agencia/demo.sh` (Linux/Mac) facilitam gerar
as saídas — rode com as 3 agências no ar.

## Backend (seção 4.2)
- `transferencia-local.png` — uma transferência dentro da mesma agência (passo 5
  do demo) e o saldo das contas envolvidas.
- `transferencia-entre-agencias.png` — uma transferência entre agências
  diferentes (passo 6), incluindo os logs das **duas** agências (janelas do
  uvicorn) e os saldos.
- `falha-conhecida.png` — a agência de destino derrubada no meio de uma
  transferência: a resposta **502** e o log `TRANSFERENCIA_FALHOU` na origem, com
  o saldo da conta de origem **não** revertido.
- `linha-do-tempo.png` — a saída de `python mesclar_logs.py`, destacando um par
  de eventos com o **mesmo** `timestampLamport` vindos de agências diferentes.

## Autenticação (seção 11.2)
- `auth-sem-token.png` — requisição sem token retornando **401** (passo 2 do demo).
- `auth-com-token.png` — a mesma requisição com token válido funcionando (201/200).
- `auth-token-expirado.png` — requisição com token expirado retornando **401**.
  Para gerar um token já expirado, no shell da agência:
  `python -c "from src.services import auth_service as a; print(a.emitir_token_usuario('ana', minutos=-1))"`
  e use-o em `Authorization: Bearer <token>`.

## Frontend (seção 12.2)
- `frontend-login.png` — tela de login e/ou já logado.
- `frontend-transferencia.png` — uma transferência feita pela interface, com o
  resultado exibido na tela.
- `frontend-erro.png` — um erro visível na tela (ex.: saque acima do saldo →
  "Saldo insuficiente", ou 401 por sessão expirada).

## Funcionalidade adicional (seção 2.1)
- `funcionalidade-adicional.png` — idempotência: a mesma transferência reenviada
  com o mesmo `Idempotency-Key` (passo 8 do demo) e o saldo **inalterado** após o
  reenvio (débito aplicado uma única vez).
