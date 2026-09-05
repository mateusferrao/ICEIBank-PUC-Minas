# Roteiro do vídeo - ICEIBank Sprint 1

Este roteiro é para você seguir do lado enquanto grava. Cada cena tem três partes:
o que fazer na tela, a fala pronta para ler, e uma linha rápida do porquê aquilo
conta para a nota. Não precisa decorar nada, é só ir lendo e clicando.

Tempo total: por volta de 8 minutos. Dá para gravar tudo de uma vez ou cortar e
gravar cena por cena.

## Antes de começar (fora da gravação)

1. Abra 4 janelas de terminal na pasta `agencia/` e ative o ambiente em cada uma:
   `.\.venv\Scripts\Activate.ps1` (no Windows) ou `. .venv/bin/activate` (Linux/Mac).
2. Nos 3 primeiros terminais, suba as agências:
   - Terminal 1: `$env:AGENCIA_ID=0; python -m uvicorn src.main:app --port 4000`
   - Terminal 2: `$env:AGENCIA_ID=1; python -m uvicorn src.main:app --port 4001`
   - Terminal 3: `$env:AGENCIA_ID=2; python -m uvicorn src.main:app --port 4002`
3. O terminal 4 é o que você vai usar para os comandos. Nele, rode uma vez:
   `Get-Date`. Isso prova que a gravação é recente. Deixe essa saída visível no
   começo do vídeo.
4. Abra o `frontend/index.html` no navegador (ou sirva com `python -m http.server`
   dentro da pasta `frontend/` e acesse `http://localhost:8000`).
5. Deixe os logs das 3 agências à vista, porque você vai mostrar eles nas cenas de
   transferência.

Números que eu vou usar o vídeo inteiro (para os saldos baterem sempre):
- ana é dona das contas 0 e 3, que ficam na agência 0.
- bruno é dono da conta 1, que fica na agência 1.
- a conta 0 começa com 100 reais.

Cole isto no terminal 4 uma vez, para já ter o token da ana guardado (vou usar o
`$HANA` nos comandos das próximas cenas):

```powershell
$AG0 = "http://localhost:4000"
$AG1 = "http://localhost:4001"
$TOKEN_ANA = (Invoke-RestMethod "$AG0/auth/login" -Method Post -ContentType "application/json" -Body '{"usuario":"ana","senha":"senha-ana"}').token
$HANA = @{ Authorization = "Bearer $TOKEN_ANA" }
```

## Cena 1 - Abertura (30s)

Tela: mostre os 3 terminais com as agências rodando.

Fala: "Esse é o ICEIBank, um banco dividido em 3 agências. É a Sprint 1, e eu fiz
em Python com FastAPI. Escolhi Python porque vou usar a mesma linguagem até a
Sprint 4, e o FastAPI me ajuda com a validação dos dados e já gera a documentação
da API sozinho. As três agências que estão aqui rodando são o mesmo código, só que
cada uma subiu com um número diferente."

Por que conta: mostra a escolha de tecnologia e a ideia central do projeto logo de
cara.

## Cena 2 - Arquitetura e partição (1min)

Tela: abra o `agencia/src/config.py` e mostre a função `agencia_responsavel`.
Depois mostre a estrutura de pastas, apontando `agencia/` (backend) e `frontend/`
separados, e dentro de `agencia/src` as pastas `controllers/` e `services/` e o
arquivo `routes.py`.

Fala: "Cada conta pertence a uma agência pela conta id módulo 3. A conta 0 é da
agência 0, a 1 da agência 1, a 2 da agência 2, a 3 volta pra 0, e assim por diante.
Isso é partição, cada agência cuida só das contas dela, e se você tentar mexer numa
conta na agência errada ela recusa. O backend segue MVC: as rotas ficam no
`routes.py`, separadas dos controllers, e a lógica de verdade fica nos services. O
frontend é uma pasta à parte, porque é um cliente web separado que só conversa com
a API."

Por que conta: particionamento e separação MVC valem pontos direto na avaliação.

## Cena 3 - Relógio de Lamport (1min)

Tela: abra o `agencia/src/services/lamport.py`. Depois abra um arquivo de log, por
exemplo `agencia/data/eventos-agencia-0.jsonl`, e mostre algumas linhas.

Fala: "Toda operação é marcada com um relógio de Lamport. São três regras. Num
evento local o contador soma 1. Ao enviar uma mensagem para outra agência ele
também soma 1 e manda o valor junto. E ao receber, o contador vira o maior entre o
valor local e o recebido, mais 1. Cada evento é gravado nesse arquivo, com o
timestamp de Lamport e a hora normal do relógio, que uso só para comparar."

Por que conta: o relógio de Lamport é um dos itens de maior peso na nota.

## Cena 4 - Criar conta, depositar e sacar (1min)

Você pode fazer pelo frontend ou pelo terminal. Vou deixar pelo terminal aqui,
porque dá pra mostrar o log reagindo.

Tela e comandos (terminal 4):
```powershell
# criar a conta 0 (ana, agência 0) com 100 reais
Invoke-RestMethod "$AG0/contas" -Method Post -Headers $HANA -ContentType "application/json" -Body '{"id":0,"saldoInicial":100}'
# depositar 50  (saldo vai para 150)
Invoke-RestMethod "$AG0/contas/0/depositar" -Method Post -Headers $HANA -ContentType "application/json" -Body '{"valor":50}'
# sacar 20  (saldo vai para 130)
Invoke-RestMethod "$AG0/contas/0/sacar" -Method Post -Headers $HANA -ContentType "application/json" -Body '{"valor":20}'
```

Fala: "Vou criar a conta 0 com 100 reais, depositar 50 e sacar 20, então o saldo
fica em 130. Repare no terminal da agência 0: cada operação apareceu no log com o
Lamport crescendo, um por evento."

Por que conta: é o CRUD de contas com depósito e saque funcionando, mais o Lamport
em cada operação.

## Cena 5 - Transferências local e entre agências (1min30)

Tela e comandos:
```powershell
# criar a conta 3 (ana, agência 0) vazia, e a conta 1 (bruno, agência 1) vazia
Invoke-RestMethod "$AG0/contas" -Method Post -Headers $HANA -ContentType "application/json" -Body '{"id":3,"saldoInicial":0}'
$TOKEN_BRUNO = (Invoke-RestMethod "$AG1/auth/login" -Method Post -ContentType "application/json" -Body '{"usuario":"bruno","senha":"senha-bruno"}').token
$HBRUNO = @{ Authorization = "Bearer $TOKEN_BRUNO" }
Invoke-RestMethod "$AG1/contas" -Method Post -Headers $HBRUNO -ContentType "application/json" -Body '{"id":1,"saldoInicial":0}'

# transferência LOCAL: conta 0 para conta 3, as duas na agência 0, valor 10
Invoke-RestMethod "$AG0/transferencias" -Method Post -Headers ($HANA + @{ "Idempotency-Key" = [guid]::NewGuid().ToString() }) -ContentType "application/json" -Body '{"idOrigem":0,"idDestino":3,"valor":10}'

# transferência ENTRE AGÊNCIAS: conta 0 (agência 0) para conta 1 (agência 1), valor 30
$CHAVE = [guid]::NewGuid().ToString()
Invoke-RestMethod "$AG0/transferencias" -Method Post -Headers ($HANA + @{ "Idempotency-Key" = $CHAVE }) -ContentType "application/json" -Body '{"idOrigem":0,"idDestino":1,"valor":30}'
```

Fala: "Agora as transferências. A primeira é local, da conta 0 para a conta 3, as
duas na mesma agência. A segunda cruza agências, da conta 0 aqui na agência 0 para
a conta 1 lá na agência 1. Olha os dois logs: na origem sai o débito, e na agência
de destino entra o crédito remoto, com o relógio de Lamport tendo sido ajustado na
hora de receber. Só a transferência entre agências usa as regras de enviar e
receber, porque só ela manda mensagem de um processo para o outro. A local é tudo
no mesmo processo, então são só eventos locais."

Guarde a variável `$CHAVE`, porque você vai usar ela de novo na cena da
idempotência. Depois da transferência entre agências, o saldo da conta 0 é 90 e o
da conta 1 é 30.

Por que conta: as duas formas de transferência funcionando, e o Lamport aplicado na
troca de mensagem entre agências.

## Cena 6 - A falha conhecida (1min)

Tela: vá até o terminal da agência 1 e feche ele (ou aperte Ctrl+C), para simular a
agência de destino caindo. Depois rode:
```powershell
try {
  Invoke-RestMethod "$AG0/transferencias" -Method Post -Headers ($HANA + @{ "Idempotency-Key" = [guid]::NewGuid().ToString() }) -ContentType "application/json" -Body '{"idOrigem":0,"idDestino":1,"valor":5}'
} catch {
  "Deu erro: $($_.Exception.Response.StatusCode.value__)"
}
# conferir o saldo da conta 0 (era 90, virou 85 e não voltou)
Invoke-RestMethod "$AG0/contas/0" -Headers $HANA
```

Fala: "Esse é o problema que a Sprint 1 não resolve, de propósito. Eu derrubei a
agência de destino e tentei transferir 5 reais para ela. A resposta é 502, e no log
da agência 0 aparece o débito seguido de uma linha de falha. Só que o débito não é
desfeito: o saldo da conta 0 saiu de 90 e foi para 85, e esse dinheiro sumiu. É a
falta de atomicidade, e é exatamente isso que a Sprint 4 vai resolver, com 2PC ou
Saga."

Por que conta: reproduzir e explicar a falha conhecida faz parte da nota, ela não
pode estar escondida.

## Cena 7 - Linha do tempo unificada (45s)

Tela: religue a agência 1 (rode de novo o comando dela no terminal), gere mais um
ou dois eventos se quiser, e no terminal da pasta `agencia/` rode:
```powershell
python mesclar_logs.py
```
Procure na saída dois eventos com o mesmo número de Lamport, vindos de agências
diferentes, e aponte para eles.

Fala: "Esse script junta os logs das 3 agências numa linha do tempo só, ordenada
pelo Lamport. Olha esses dois eventos aqui: eles têm o mesmo timestamp e são
concorrentes, um não causou o outro, cada agência fez a sua coisa sem falar com a
outra. O Lamport não consegue afirmar com certeza que dois eventos são
concorrentes, e é por isso que a Sprint 2 vai usar relógio vetorial."

Por que conta: mostra o algoritmo funcionando de verdade e liga com a teoria.

## Cena 8 - Autenticação JWT (1min30)

Tela e comandos, mostrando os três cenários:
```powershell
# 1) sem token: tem que dar 401
try {
  Invoke-RestMethod "$AG0/contas/0" 
} catch {
  "Sem token: $($_.Exception.Response.StatusCode.value__)"
}

# 2) com token válido: funciona
Invoke-RestMethod "$AG0/contas/0" -Headers $HANA

# 3) token expirado: tem que dar 401
#   (gere um token que já nasce vencido)
$EXPIRADO = python -c "from src.services import auth_service as a; print(a.emitir_token_usuario('ana', minutos=-1))"
try {
  Invoke-RestMethod "$AG0/contas/0" -Headers @{ Authorization = "Bearer $EXPIRADO" }
} catch {
  "Token expirado: $($_.Exception.Response.StatusCode.value__)"
}

# autorização de posse: bruno tentando sacar da conta da ana dá 403
try {
  Invoke-RestMethod "$AG0/contas/0/sacar" -Method Post -Headers $HBRUNO -ContentType "application/json" -Body '{"valor":10}'
} catch {
  "Bruno na conta da ana: $($_.Exception.Response.StatusCode.value__)"
}
```

Fala: "Todas as rotas de conta exigem um token. Sem token dá 401. Com o token do
login funciona. Com um token expirado dá 401 de novo. E além de autenticar, eu
confiro a posse: aqui o bruno, mesmo logado, tenta mexer na conta da ana e leva um
403, porque cada um só mexe na própria conta. A chamada interna entre agências usa
um token de serviço, separado do token do usuário, porque ali é uma confiança entre
sistemas, não uma ação de uma pessoa."

Por que conta: os três cenários de token e as decisões de design são cobrados
diretamente.

## Cena 9 - Frontend (1min)

Tela: vá para o navegador com o frontend aberto.

Passo a passo (clicando):
1. Faça login com usuário `ana` e senha `senha-ana`.
2. Na aba Operações, consulte o saldo da conta 0.
3. Faça um depósito qualquer na conta 0 e mostre a mensagem de sucesso.
4. Vá na aba Transferência e faça uma transferência da conta 0 para a conta 1.
5. Provoque um erro: tente sacar um valor maior que o saldo. Vai aparecer "Saldo
   insuficiente" na tela.
6. Passe pela aba Extrato (digite a conta 0 e veja o histórico) e pela aba Painel
   das Agências, mostrando os relógios de Lamport ao vivo.

Fala: "Esse é o frontend. Ele guarda o token no navegador e reenvia em toda
requisição, então depois do login eu não preciso ficar passando o token na mão. Se
o token expira, ele avisa na tela e volta para o login, não é um erro escondido no
console. O erro de saldo insuficiente também aparece pra pessoa. O código é
separado em Model, View e Controller. Ainda tem a aba de extrato de uma conta e o
painel que mostra o relógio de Lamport das três agências ao vivo."

Por que conta: o fluxo completo pela interface e o tratamento de erro visível valem
os 3 pontos do frontend.

## Cena 10 - Funcionalidade adicional: idempotência (1min)

Tela e comandos (reusando a `$CHAVE` da cena 5):
```powershell
# reenviar a MESMA transferência de antes, com a MESMA chave
Invoke-RestMethod "$AG0/transferencias" -Method Post -Headers ($HANA + @{ "Idempotency-Key" = $CHAVE }) -ContentType "application/json" -Body '{"idOrigem":0,"idDestino":1,"valor":30}'
# conferir o saldo: continua o mesmo, o débito não aconteceu de novo
Invoke-RestMethod "$AG0/contas/0" -Headers $HANA
```

Fala: "A minha funcionalidade adicional é a idempotência. Toda transferência leva
uma chave única. Se a mesma requisição chega de novo com a mesma chave, tipo quando
a pessoa clica duas vezes ou a rede faz um retry, o débito não acontece outra vez, e
ela recebe a resposta que já tinha sido dada. Repara que reenviei a mesma
transferência de 30 reais e o saldo não mudou. Essa chave também vai pra agência de
destino, então nem um retry de rede credita duas vezes. Isso não conserta a falha
conhecida, mas garante que a transferência aconteça no máximo uma vez pra cada
chave."

Por que conta: é a funcionalidade adicional obrigatória, e precisa aparecer
funcionando.

## Cena 11 - Fechamento e decisões (45s)

Tela: pode voltar para o código ou para os terminais, o que preferir.

Fala: "Pra fechar, as decisões principais. O dinheiro é guardado em centavos, como
número inteiro, pra não ter erro de arredondamento, mas a API fala em reais. Os
endpoints são async num worker só, então uma operação numa conta não é cortada no
meio por outra requisição. As senhas usam hash Argon2id. E eu deixei um
docker-compose que sobe as três agências e o frontend de uma vez, já pensando na
Sprint 4, que é a parte de nuvem e containers. É isso, obrigado."

Por que conta: fecha mostrando que você pensou nas decisões de projeto, não só no
que o roteiro pediu.

## Dica final

Deixe este arquivo aberto do lado enquanto grava e vá seguindo. Se travar em alguma
cena, corta e grava só aquele trecho de novo, depois junta na edição. Se quiser um
vídeo mais curto, junte as cenas 4 e 5 e corte a cena 7.
