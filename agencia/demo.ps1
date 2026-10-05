# Demonstração do ICEIBank (Sprint 1, ainda valido no Sprint 2) via PowerShell / Invoke-RestMethod.
# Pré-requisito: as 3 agências rodando em janelas separadas:
#   $env:AGENCIA_ID=0; python -m uvicorn src.main:app --port 4000
#   $env:AGENCIA_ID=1; python -m uvicorn src.main:app --port 4001
#   $env:AGENCIA_ID=2; python -m uvicorn src.main:app --port 4002
#
# Dica para as evidências: deixe "Get-Date" visível no início do print.
Get-Date

$AG0 = "http://localhost:4000"
$AG1 = "http://localhost:4001"

function Login($base, $usuario, $senha) {
  $r = Invoke-RestMethod -Uri "$base/auth/login" -Method Post -ContentType "application/json" `
    -Body (@{ usuario = $usuario; senha = $senha } | ConvertTo-Json)
  return $r.token
}

Write-Host "`n== 1) Login (ana na ag0, bruno na ag1) ==" -ForegroundColor Cyan
$TOKEN_ANA = Login $AG0 "ana" "senha-ana"
$TOKEN_BRUNO = Login $AG1 "bruno" "senha-bruno"
$HANA = @{ Authorization = "Bearer $TOKEN_ANA" }
$HBRUNO = @{ Authorization = "Bearer $TOKEN_BRUNO" }
Write-Host "Tokens obtidos."

Write-Host "`n== 2) Requisicao SEM token deve dar 401 ==" -ForegroundColor Cyan
try {
  Invoke-RestMethod -Uri "$AG0/contas" -Method Post -ContentType "application/json" -Body '{"id":0}' | Out-Null
} catch { Write-Host "OK -> $($_.Exception.Response.StatusCode.value__) (esperado 401)" }

Write-Host "`n== 3) Criar contas (0 e 3 na ag0 = ana; 1 na ag1 = bruno) ==" -ForegroundColor Cyan
Invoke-RestMethod -Uri "$AG0/contas" -Method Post -Headers $HANA -ContentType "application/json" -Body '{"id":0,"saldoInicial":100}'
Invoke-RestMethod -Uri "$AG0/contas" -Method Post -Headers $HANA -ContentType "application/json" -Body '{"id":3,"saldoInicial":0}'
Invoke-RestMethod -Uri "$AG1/contas" -Method Post -Headers $HBRUNO -ContentType "application/json" -Body '{"id":1,"saldoInicial":0}'

Write-Host "`n== 4) Deposito e saque na conta 0 ==" -ForegroundColor Cyan
Invoke-RestMethod -Uri "$AG0/contas/0/depositar" -Method Post -Headers $HANA -ContentType "application/json" -Body '{"valor":50}'
Invoke-RestMethod -Uri "$AG0/contas/0/sacar" -Method Post -Headers $HANA -ContentType "application/json" -Body '{"valor":20}'

Write-Host "`n== 5) Transferencia LOCAL (0 -> 3, mesma agencia) ==" -ForegroundColor Cyan
Invoke-RestMethod -Uri "$AG0/transferencias" -Method Post -Headers ($HANA + @{ "Idempotency-Key" = [guid]::NewGuid().ToString() }) `
  -ContentType "application/json" -Body '{"idOrigem":0,"idDestino":3,"valor":10}'

Write-Host "`n== 6) Transferencia ENTRE AGENCIAS (0 -> 1) ==" -ForegroundColor Cyan
$CHAVE = [guid]::NewGuid().ToString()
Invoke-RestMethod -Uri "$AG0/transferencias" -Method Post -Headers ($HANA + @{ "Idempotency-Key" = $CHAVE }) `
  -ContentType "application/json" -Body '{"idOrigem":0,"idDestino":1,"valor":30}'

Write-Host "`n== 7) Saldos apos as transferencias ==" -ForegroundColor Cyan
Invoke-RestMethod -Uri "$AG0/contas/0" -Method Get -Headers $HANA
Invoke-RestMethod -Uri "$AG1/contas/1" -Method Get -Headers $HBRUNO

Write-Host "`n== 8) Idempotencia: reenviar a MESMA chave nao debita de novo ==" -ForegroundColor Cyan
Invoke-RestMethod -Uri "$AG0/transferencias" -Method Post -Headers ($HANA + @{ "Idempotency-Key" = $CHAVE }) `
  -ContentType "application/json" -Body '{"idOrigem":0,"idDestino":1,"valor":30}'
Write-Host "Saldo da conta 0 (deve continuar o mesmo do passo 7):"
Invoke-RestMethod -Uri "$AG0/contas/0" -Method Get -Headers $HANA

Write-Host "`n== RESILIENCIA (Sprint 2) ==" -ForegroundColor Yellow
Write-Host "Para o cenario de agencia fora do ar com RabbitMQ (mensagem retida, reinicio, DLQ), use .\demo-sprint2.ps1" -ForegroundColor Yellow
