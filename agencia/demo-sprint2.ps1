# Demonstracao guiada do Sprint 2 (RabbitMQ + relogio vetorial) e geracao das evidencias.
#
# Como usar (a partir da pasta agencia/):
#   .\demo-sprint2.ps1
#
# O script sobe as 3 agencias em janelas separadas, roda o cenario completo e para
# nos momentos em que voce deve tirar print (Win+Shift+S). Os prints vao para
# evidencias\sprint2\ com os nomes indicados na tela.
#
# Requisitos: .venv criado em agencia\ e RABBITMQ_URL definida (variavel de ambiente
# ou arquivo .env na raiz do repositorio).
#
# -SemPausas: roda tudo sem parar e com as janelas minimizadas (para testar o script).
# -CapturarPrints: em vez de esperar voce, organiza as janelas e salva os prints
# sozinho em evidencias\sprint2\ (so da area das janelas do demo).
param([switch]$SemPausas, [switch]$CapturarPrints)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
. "$PSScriptRoot\capturar-janelas.ps1"
if ($CapturarPrints) { $host.UI.RawUI.WindowTitle = "Demo Sprint 2" }
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PY = ".\.venv\Scripts\python.exe"

if (-not $env:RABBITMQ_URL) {
  $linha = Get-Content "..\.env" -ErrorAction SilentlyContinue | Where-Object { $_ -match "^RABBITMQ_URL=" } | Select-Object -First 1
  if ($linha) { $env:RABBITMQ_URL = $linha.Substring("RABBITMQ_URL=".Length) }
}
if (-not $env:RABBITMQ_URL) { throw "Defina RABBITMQ_URL (variavel de ambiente ou arquivo .env na raiz)." }

function Pausa($texto, $arquivo = $null, $modo = "tela-cheia") {
  if ($CapturarPrints -and $arquivo) { Capturar-Print $arquivo $modo; return }
  if ($SemPausas) { return }
  Write-Host "`n>>> $texto" -ForegroundColor Yellow
  Read-Host "    Depois do print, aperte ENTER para continuar" | Out-Null
}

function Titulo($texto) {
  if ($CapturarPrints) { Clear-Host }
  Write-Host "`n== $texto ==" -ForegroundColor Cyan
}

$janelas = @{}
function Subir-Agencia($id) {
  $estilo = if ($SemPausas) { "Minimized" } else { "Normal" }
  $cmd = "`$host.UI.RawUI.WindowTitle='Agencia $id'; `$env:AGENCIA_ID=$id; & '$PY' -m uvicorn src.main:app --port $(4000 + $id)"
  $janelas[$id] = Start-Process powershell -WorkingDirectory $PSScriptRoot -WindowStyle $estilo `
    -ArgumentList "-NoExit", "-Command", $cmd -PassThru
  for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-RestMethod "http://localhost:$(4000 + $id)/health" | Out-Null; return } catch { Start-Sleep -Milliseconds 500 }
  }
  throw "Agencia $id nao subiu."
}

function Derrubar-Agencia($id) {
  taskkill /PID $janelas[$id].Id /T /F | Out-Null
  Start-Sleep -Milliseconds 800
  Fechar-Janela "Agencia $id"   # o terminal fica aberto depois do processo morrer
}

# O FastAPI responde JSON em UTF-8 sem declarar o charset, e o Invoke-RestMethod do
# Windows PowerShell 5.1 leria como ISO-8859-1 (acentos quebrados). Por isso decodifico
# o corpo da resposta como UTF-8 na mao.
function Req($metodo, $url, $headers = @{}, $corpo = $null) {
  $p = @{ Uri = $url; Method = $metodo; Headers = $headers; UseBasicParsing = $true }
  if ($corpo) { $p.Body = [System.Text.Encoding]::UTF8.GetBytes($corpo); $p.ContentType = "application/json" }
  $r = Invoke-WebRequest @p
  return [System.Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json
}

function Login($id, $usuario, $senha) {
  $r = Req Post "http://localhost:$(4000 + $id)/auth/login" @{} (@{ usuario = $usuario; senha = $senha } | ConvertTo-Json)
  return @{ Authorization = "Bearer $($r.token)" }
}

function Post($id, $caminho, $corpo, $headers) {
  Req Post "http://localhost:$(4000 + $id)$caminho" $headers $corpo
}

function Ultimos-Eventos($id, $n) {
  Get-Content "data\eventos-agencia-$id.jsonl" -Tail $n | ForEach-Object {
    $e = $_ | ConvertFrom-Json
    "{0}  vetor=[{1}]  {2}  {3}" -f $e.agencia, ($e.timestampVetorial -join ","), $e.tipo, ($e.detalhes | ConvertTo-Json -Compress)
  }
}

try {
  Remove-Item data -Recurse -Force -ErrorAction SilentlyContinue
  & $PY ver_filas.py --limpar-dlq | Out-Null
  New-Item -ItemType Directory -Force -Path "..\evidencias\sprint2" | Out-Null

  Titulo "0) Subindo as 3 agencias"
  0, 1, 2 | ForEach-Object { Subir-Agencia $_ }
  $H = @{}
  0, 1, 2 | ForEach-Object { $H[$_] = Login $_ "ana" "senha-ana" }
  Write-Host "Agencias 0, 1 e 2 no ar, ana autenticada nas tres."

  # ---------------------------------------------------------------- PRINT 1
  Titulo "1) Transferencia ASSINCRONA entre agencias (conta 0 da ag0 -> conta 1 da ag1)"
  Get-Date
  Post 0 "/contas" '{"id":0,"saldoInicial":100}' $H[0] | Out-Null
  Post 1 "/contas" '{"id":1,"saldoInicial":0}' $H[1] | Out-Null
  Write-Host "Resposta da transferencia (200 = o broker aceitou a mensagem):"
  Post 0 "/transferencias" '{"idOrigem":0,"idDestino":1,"valor":30}' $H[0]
  Start-Sleep -Seconds 2
  Write-Host "`nSaldo da conta 1 (ag1) apos consumir a mensagem:"
  Req Get "http://localhost:4001/contas/1" $H[1]
  Write-Host "`nEventos da agencia 0 (origem):"
  Ultimos-Eventos 0 3
  Write-Host "`nEventos da agencia 1 (destino):"
  Ultimos-Eventos 1 2
  Write-Host "`nVetores: ag0 = $((Req Get http://localhost:4000/health).vetor -join ',')   ag1 = $((Req Get http://localhost:4001/health).vetor -join ',')"
  Pausa "PRINT 1 -> evidencias\sprint2\transferencia-assincrona.png  (este terminal + as janelas 'Agencia 0' e 'Agencia 1' visiveis)" "transferencia-assincrona" "lado-a-lado"

  # ---------------------------------------------------------------- PRINT 2
  Titulo "2) Resiliencia: agencia 1 FORA DO AR"
  Get-Date
  Derrubar-Agencia 1
  Write-Host "Agencia 1 derrubada. Transferindo R`$ 20 para a conta 1 mesmo assim:"
  Post 0 "/transferencias" '{"idOrigem":0,"idDestino":1,"valor":20}' $H[0]
  Write-Host "`nFilas (a mensagem fica retida em fila-agencia-1, sem consumidor):"
  & $PY ver_filas.py
  Write-Host "`nSubindo a agencia 1 de novo (as contas em memoria sumiram)..."
  Subir-Agencia 1
  Start-Sleep -Seconds 6
  Write-Host "`nO que a agencia 1 registrou ao consumir a fila:"
  Ultimos-Eventos 1 5
  Write-Host "`nSaldo da conta 0 (ag0) - o debito continua aplicado:"
  Req Get "http://localhost:4000/contas/0" $H[0]
  Pausa "PRINT 2 -> evidencias\sprint2\resiliencia-fila.png  (este terminal + a janela 'Agencia 1' com o log das tentativas)" "resiliencia-fila" "lado-a-lado"

  # ---------------------------------------------------------------- PRINT 4
  Titulo "3) Dead-letter queue (funcionalidade adicional)"
  Get-Date
  Write-Host "Depois de 3 tentativas a mensagem foi para a DLQ, em vez de sumir:"
  & $PY ver_filas.py
  Write-Host "`nEventos de falha e de DLQ na agencia 1:"
  Get-Content "data\eventos-agencia-1.jsonl" | ForEach-Object { $_ | ConvertFrom-Json } |
    Where-Object { $_.tipo -like "CREDITO_REMOTO_*" } | ForEach-Object {
      "{0}  vetor=[{1}]  {2}  tentativa={3}  motivo={4}" -f $_.agencia, ($_.timestampVetorial -join ","), $_.tipo, $_.detalhes.tentativa, $_.detalhes.motivo
    }
  Pausa "PRINT 4 -> evidencias\sprint2\dlq.png  (este terminal; opcional: tambem o RabbitMQ Manager mostrando fila-agencia-1.dlq com 1 mensagem)" "dlq" "tela-cheia"

  # ---------------------------------------------------------------- PRINT 3
  Titulo "4) Linha do tempo causal (eventos concorrentes x causais)"
  Get-Date
  Post 2 "/contas" '{"id":2,"saldoInicial":5}' $H[2] | Out-Null
  Write-Host "Conta 2 criada na agencia 2, sem relacao com as transferencias. Rodando mesclar_logs.py:`n"
  & $PY mesclar_logs.py
  Pausa "PRINT 3 -> evidencias\sprint2\linha-do-tempo-causal.png  (mostre os pares CONCORRENTES e o par CAUSAL; pode rolar o terminal)" "linha-do-tempo-causal" "tela-cheia"
}
finally {
  if (-not $SemPausas -and -not $CapturarPrints) { Read-Host "`nAperte ENTER para encerrar as 3 agencias" | Out-Null }
  foreach ($id in @($janelas.Keys)) { try { taskkill /PID $janelas[$id].Id /T /F | Out-Null } catch {} }
  Write-Host "Agencias encerradas."
}
