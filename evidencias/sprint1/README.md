# Evidências - Sprint 1

Aqui vão os prints de tela da execução. São prints reais, com o `Get-Date`
aparecendo em algum terminal para mostrar que a execução foi recente. Capture cada
arquivo da lista abaixo. Os scripts `agencia/demo.ps1` (PowerShell) e
`agencia/demo.sh` (Linux/Mac) ajudam a gerar as saídas. Rode com as 3 agências no
ar.

## Backend (seção 4.2)
- `transferencia-local.png`: uma transferência dentro da mesma agência (passo 5 do
  demo) e o saldo das contas envolvidas.
- `transferencia-entre-agencias.png`: uma transferência entre agências diferentes
  (passo 6), com os logs das duas agências (as janelas do uvicorn) e os saldos.
- `falha-conhecida.png`: a agência de destino derrubada no meio da transferência,
  mostrando a resposta 502, o log `TRANSFERENCIA_FALHOU` na origem e o saldo da
  conta de origem sem estorno.
- `linha-do-tempo.png`: a saída do `python mesclar_logs.py`, mostrando um par de
  eventos com o mesmo `timestampLamport` vindos de agências diferentes.

## Autenticação (seção 11.2)
- `auth-sem-token.png`: uma requisição sem token dando 401 (passo 2 do demo).
- `auth-com-token.png`: a mesma requisição com token válido funcionando (201/200).
- `auth-token-expirado.png`: uma requisição com token expirado dando 401. Para
  gerar um token já expirado, no shell da agência:
  `python -c "from src.services import auth_service as a; print(a.emitir_token_usuario('ana', minutos=-1))"`
  e depois use ele em `Authorization: Bearer <token>`.

## Frontend (seção 12.2)
- `frontend-login.png`: a tela de login, ou já logado.
- `frontend-transferencia.png`: uma transferência feita pela interface, com o
  resultado aparecendo na tela.
- `frontend-erro.png`: um erro visível na tela (por exemplo, saque acima do saldo
  mostrando "Saldo insuficiente", ou 401 por sessão expirada).

## Funcionalidade adicional (seção 2.1)
- `funcionalidade-adicional.png`: a idempotência, com a mesma transferência
  reenviada usando o mesmo `Idempotency-Key` (passo 8 do demo) e o saldo continuando
  igual depois do reenvio, ou seja, o débito aconteceu uma vez só.
