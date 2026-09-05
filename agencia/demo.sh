#!/usr/bin/env bash
# Demonstração do ICEIBank (Sprint 1) via curl (Linux/Mac).
# Pré-requisito: as 3 agências rodando (em outros terminais):
#   AGENCIA_ID=0 python -m uvicorn src.main:app --port 4000
#   AGENCIA_ID=1 python -m uvicorn src.main:app --port 4001
#   AGENCIA_ID=2 python -m uvicorn src.main:app --port 4002
set -e
AG0=http://localhost:4000
AG1=http://localhost:4001

token() { curl -s "$1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"usuario\":\"$2\",\"senha\":\"$3\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])"; }

# Gera um UUID de forma portável (sem depender do utilitário uuidgen).
uuid() {
  if [ -r /proc/sys/kernel/random/uuid ]; then cat /proc/sys/kernel/random/uuid;
  else python3 -c "import uuid;print(uuid.uuid4())"; fi
}

date
echo -e "\n== 1) Login =="
TOKEN_ANA=$(token $AG0 ana senha-ana)
TOKEN_BRUNO=$(token $AG1 bruno senha-bruno)
HANA="Authorization: Bearer $TOKEN_ANA"; HBRUNO="Authorization: Bearer $TOKEN_BRUNO"
echo "tokens obtidos"

echo -e "\n== 2) SEM token deve dar 401 =="
curl -s -o /dev/null -w "HTTP %{http_code} (esperado 401)\n" $AG0/contas -H 'Content-Type: application/json' -d '{"id":0}'

echo -e "\n== 3) Criar contas (0 e 3 = ana/ag0; 1 = bruno/ag1) =="
curl -s $AG0/contas -H "$HANA" -H 'Content-Type: application/json' -d '{"id":0,"saldoInicial":100}'; echo
curl -s $AG0/contas -H "$HANA" -H 'Content-Type: application/json' -d '{"id":3,"saldoInicial":0}'; echo
curl -s $AG1/contas -H "$HBRUNO" -H 'Content-Type: application/json' -d '{"id":1,"saldoInicial":0}'; echo

echo -e "\n== 4) Deposito e saque =="
curl -s $AG0/contas/0/depositar -H "$HANA" -H 'Content-Type: application/json' -d '{"valor":50}'; echo
curl -s $AG0/contas/0/sacar -H "$HANA" -H 'Content-Type: application/json' -d '{"valor":20}'; echo

echo -e "\n== 5) Transferencia LOCAL (0 -> 3) =="
curl -s $AG0/transferencias -H "$HANA" -H 'Content-Type: application/json' -H "Idempotency-Key: $(uuid)" -d '{"idOrigem":0,"idDestino":3,"valor":10}'; echo

echo -e "\n== 6) Transferencia ENTRE AGENCIAS (0 -> 1) =="
CHAVE=$(uuid)
curl -s $AG0/transferencias -H "$HANA" -H 'Content-Type: application/json' -H "Idempotency-Key: $CHAVE" -d '{"idOrigem":0,"idDestino":1,"valor":30}'; echo

echo -e "\n== 7) Saldos =="
curl -s $AG0/contas/0 -H "$HANA"; echo
curl -s $AG1/contas/1 -H "$HBRUNO"; echo

echo -e "\n== 8) Idempotencia: mesma chave nao debita de novo =="
curl -s $AG0/transferencias -H "$HANA" -H 'Content-Type: application/json' -H "Idempotency-Key: $CHAVE" -d '{"idOrigem":0,"idDestino":1,"valor":30}'; echo
echo "saldo conta 0 (deve ser igual ao do passo 7):"; curl -s $AG0/contas/0 -H "$HANA"; echo

echo -e "\n== FALHA CONHECIDA (rode manualmente) =="
echo "Derrube a agencia 1 e refaça uma transferencia 0->1:"
echo "  curl -s -w '\\nHTTP %{http_code}\\n' $AG0/transferencias -H \"\$HANA\" -H 'Content-Type: application/json' -d '{\"idOrigem\":0,\"idDestino\":1,\"valor\":5}'"
echo "Esperado: HTTP 502 + log TRANSFERENCIA_FALHOU; saldo da conta 0 NAO revertido."
