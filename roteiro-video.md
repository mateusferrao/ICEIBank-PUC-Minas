# Roteiro do vídeo - ICEIBank Sprint 1

Ideia geral: mostrar o sistema funcionando e explicar as principais decisões, que é
o que a avaliação pede. Dá para fazer em uns 7 a 9 minutos. Antes de gravar, deixe
as 3 agências rodando em terminais separados e o frontend aberto no navegador. Em
algum terminal, rode `Get-Date` uma vez no começo para provar que a gravação é
recente.

Preparação (fora da gravação):
- 3 terminais com `AGENCIA_ID=0/1/2 python -m uvicorn src.main:app --port 4000/4001/4002`.
- 1 terminal para os comandos (ou rode o `demo.ps1`).
- navegador em `frontend/index.html`.

## 1. Abertura (30s)
Fale: "Esse é o ICEIBank, um banco dividido em 3 agências. É a Sprint 1, feita em
Python com FastAPI. Escolhi Python porque vou manter a mesma linguagem até a Sprint
4, e o FastAPI ajuda bastante com validação e com a documentação automática."
Mostre: os 3 terminais das agências ligados.

## 2. Arquitetura e partição (1min)
Fale: "As 3 agências rodam o mesmo código, o que muda é o `AGENCIA_ID`. Cada conta
pertence a uma agência pela conta `id % 3`. A conta 0 é da agência 0, a 1 da agência
1, a 2 da agência 2, a 3 volta pra 0, e assim por diante. É partição, não cópia,
cada agência cuida só das contas dela."
Mostre: o `config.py` (a função `agencia_responsavel`) e a estrutura de pastas, com
`agencia/` (backend) e `frontend/` separados. Comente que o backend segue MVC, com
`routes.py` separado dos `controllers/` e a lógica em `services/`.

## 3. Relógio de Lamport (1min)
Fale: "Toda operação é carimbada com um relógio de Lamport. São três regras: em um
evento local o contador soma 1, ao enviar uma mensagem também soma 1 e manda o valor
junto, e ao receber o contador vira o máximo entre o local e o recebido, mais 1.
Cada evento é gravado num arquivo `.jsonl`."
Mostre: o `services/lamport.py` e um arquivo `data/eventos-agencia-0.jsonl` com
alguns eventos.

## 4. Contas e operações (1min)
Fale: "Vou criar uma conta, depositar e sacar."
Mostre (pelo frontend ou pelo terminal): login como ana, criar a conta 0 com saldo
100, depositar 50, sacar 20, consultar o saldo. Aponte que cada operação apareceu no
log da agência com o timestamp de Lamport crescendo.

## 5. Transferências (1min30)
Fale: "Tem dois tipos de transferência. A local, na mesma agência, e a que cruza
agências."
Mostre:
- transferência local (por exemplo conta 0 para conta 3, as duas da agência 0) e o
  saldo das duas mudando.
- transferência entre agências (conta 0 da agência 0 para a conta 1 da agência 1).
  Mostre o log das duas agências: na origem sai `TRANSFERENCIA_DEBITO`, e na de
  destino entra `TRANSFERENCIA_CREDITO_REMOTO`, com o relógio de Lamport tendo sido
  ajustado ao receber.
Fale: "Repare que só a transferência entre agências usa as regras de enviar e
receber do Lamport, porque só ela tem mensagem indo de um processo para o outro. A
local é tudo no mesmo processo."

## 6. Falha conhecida (1min)
Fale: "Esse é o problema que a Sprint 1 não resolve de propósito."
Mostre: derrube a agência de destino (feche o terminal dela) e tente uma
transferência para uma conta dela. Aparece o erro 502 e, no log da origem,
`TRANSFERENCIA_DEBITO` seguido de `TRANSFERENCIA_FALHOU`. Consulte o saldo da origem
e mostre que o dinheiro saiu e não voltou.
Fale: "O débito não é estornado, então o dinheiro some por um tempo. Isso é a falta
de atomicidade, e é justamente o que a Sprint 4 vai resolver, com 2PC ou Saga."

## 7. Linha do tempo unificada (45s)
Mostre: religue a agência que caiu, gere mais alguns eventos e rode
`python mesclar_logs.py`. Aponte dois eventos com o mesmo `timestampLamport` vindos
de agências diferentes.
Fale: "Esses dois eventos têm o mesmo timestamp e são concorrentes, nenhum causou o
outro. O Lamport não consegue afirmar com certeza que dois eventos são concorrentes,
e é por isso que a Sprint 2 usa relógio vetorial."

## 8. Autenticação JWT (1min30)
Fale: "Todas as rotas de conta exigem um token JWT."
Mostre os três cenários:
- requisição sem token dá 401;
- login e a mesma requisição com o token funciona;
- um token expirado dá 401 (dá pra gerar um já expirado com
  `emitir_token_usuario('ana', minutos=-1)`).
Depois mostre a autorização de posse: logado como bruno, tente mexer numa conta da
ana e mostre o 403.
Fale: "Além de autenticar, eu confiro a posse: cada um só mexe na própria conta. E a
chamada interna entre agências usa um token de serviço, separado do token do
usuário, porque ali é uma confiança entre sistemas, não uma ação de uma pessoa."

## 9. Frontend (1min)
Mostre pelo navegador: login, consulta de saldo, um depósito, uma transferência, e um
erro visível na tela (tente sacar mais do que o saldo, aparece "Saldo insuficiente").
Mostre também as abas Extrato e Painel das Agências, com os relógios de Lamport ao
vivo.
Fale: "O frontend guarda o token no localStorage e reenvia em toda requisição. Se o
token expira, ele avisa na tela e volta pro login. O código está separado em Model,
View e Controller."

## 10. Funcionalidade adicional: idempotência (1min)
Fale: "A minha funcionalidade adicional é a idempotência de transferências."
Mostre: faça uma transferência com um `Idempotency-Key`, veja o saldo, e reenvie a
mesma requisição com a mesma chave. Mostre que o saldo não muda, o débito aconteceu
uma vez só.
Fale: "A chave também vai pra agência de destino, então nem um retry de rede credita
duas vezes. Isso não conserta a falha conhecida, mas garante que a transferência
aconteça no máximo uma vez para cada chave."

## 11. Fechamento e decisões (45s)
Fale, resumindo as principais decisões:
- "Dinheiro é guardado em centavos, como inteiro, pra não ter erro de arredondamento,
  mas a API fala em reais."
- "Os endpoints são async num worker só, então uma operação numa conta não é cortada
  no meio por outra."
- "As senhas usam hash Argon2id."
- "E deixei um docker-compose que sobe as 3 agências e o frontend de uma vez, já
  pensando na Sprint 4."
Encerre agradecendo.

Dica final: não precisa decorar. Deixe esse roteiro do lado, vá seguindo os passos e
falando com naturalidade. Se errar, corte e regrave só aquele trecho.
