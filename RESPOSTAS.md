# RESPOSTAS - ICEIBank (Sprint 1 e Sprint 2)

O ICEIBank é um banco dividido em 3 agências. O mesmo código roda três vezes, cada
processo com um `AGENCIA_ID` diferente. Cada agência é dona de uma parte das contas
e registra tudo com um relógio lógico. Também tem autenticação por JWT, um frontend
web e, como funcionalidade adicional, idempotência de transferências (Sprint 1) e
uma dead-letter queue (Sprint 2).

Escolhi Python com FastAPI, e vou manter essa linguagem da Sprint 1 até a 4. O
dinheiro é guardado em centavos (inteiro) por dentro e mostrado em reais na API,
para não ter erro de arredondamento.

Este arquivo tem duas partes: a **Sprint 2** logo abaixo (mensageria com RabbitMQ e
relógio vetorial) e a **Sprint 1** mais embaixo, que continua como foi entregue
(os textos dela descrevem o sistema daquela época, com Lamport e chamada REST
direta entre agências).

## Declaração de uso de IA

Usei o Claude (Anthropic), pelo Claude Code, como apoio no Sprint 2: para
planejar a ordem do trabalho, escrever e revisar código e testes, e redigir este
documento. Eu li e revisei o que foi entregue e consigo explicar cada parte. O
roteiro do Sprint 2 também foi organizado com apoio de IA, como ele mesmo declara.
Os trechos do roteiro foram adaptados (por exemplo, no lugar da `pika` usei a
`aio-pika`, que roda no mesmo event loop do FastAPI) e há partes que não estão no
roteiro: publisher confirms com estorno, deduplicação no consumidor, validação das
mensagens e a recuperação do relógio a partir do log.

## Como executar

Pré-requisitos: Python 3.11+ e uma instância do CloudAMQP (plano gratuito Little
Lemur). Copie a **AMQP URL** da instância para a variável `RABBITMQ_URL`, que pode
ficar num arquivo `.env` na raiz do repositório (o `.env` está no `.gitignore`; o
`.env.example` mostra o formato) ou ser definida em cada terminal:

```
$env:RABBITMQ_URL="amqps://usuario:senha@host.cloudamqp.com/vhost"
```

Backend (dentro de `agencia/`):

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Linux/Mac: . .venv/bin/activate
pip install -r requirements.txt

# Terminal 1:  $env:AGENCIA_ID=0; python -m uvicorn src.main:app --port 4000
# Terminal 2:  $env:AGENCIA_ID=1; python -m uvicorn src.main:app --port 4001
# Terminal 3:  $env:AGENCIA_ID=2; python -m uvicorn src.main:app --port 4002
```

Ao subir, cada agência conecta no RabbitMQ, declara a topologia inteira (as três
filas e as três dead-letter queues) e passa a consumir a própria fila. Sem
`RABBITMQ_URL` a agência não sobe e mostra uma mensagem pedindo a variável.

- Testes: `pytest` (dentro de `agencia/`). O teste de integração
  (`tests/test_integracao_rabbitmq.py`) só roda se `RABBITMQ_URL` estiver definida;
  ele usa a fila da agência 2, então não deve rodar junto com a agência 2 de verdade.
- Demonstração do Sprint 2 com as evidências guiadas: `.\demo-sprint2.ps1`. Ele sobe as
  3 agências, roda o cenário todo (transferência assíncrona, agência fora do ar, DLQ,
  linha do tempo) e para nos momentos de tirar print.
- Linha do tempo causal: `python mesclar_logs.py`. Estado das filas no broker:
  `python ver_filas.py` (e `--limpar-dlq` para esvaziar as DLQs).
- Demonstração do Sprint 1 (login, contas, transferências): `demo.ps1` ou `demo.sh`.
- Frontend: sirva a pasta `frontend/` (`python -m http.server 5500`) e abra
  `http://localhost:5500`. Escolha no seletor qual agência é a porta de entrada. Além
  de login, saldo, depósito, saque e transferência, tem a aba Extrato (eventos de uma
  conta, com o vetor de cada um) e a aba Painel das Agências (vetor atual e quantidade
  de contas das 3 agências).
- Docker (as 3 agências mais o frontend): `docker compose up --build`, com o
  `RABBITMQ_URL` no `.env` da raiz. Os logs vão para `agencia/data/` por um volume.
  (Esta parte do compose eu não cheguei a executar neste sprint.)

Usuários de teste (seed, iguais nas 3 agências): `ana`/`senha-ana`,
`bruno`/`senha-bruno`, `carla`/`senha-carla`.

---

# Sprint 2: mensageria e relógio vetorial

## O que mudou em relação ao Sprint 1

| Assunto | Sprint 1 | Sprint 2 |
|---|---|---|
| Crédito entre agências | `POST /contas/{id}/creditar-remoto` (REST, síncrono) | mensagem na exchange `iceibank.eventos`, consumida pela agência de destino |
| Resposta da transferência | 200 = crédito já aplicado no destino | 200 = o broker confirmou a mensagem (o crédito vem depois) |
| Destino fora do ar | 502 e débito pendurado | 200, a mensagem fica retida na fila durável |
| Relógio | Lamport (um inteiro) | vetorial (um contador por agência) |
| Log de eventos | `timestampLamport` | `timestampVetorial` (e `messageId` ligando débito e crédito) |
| `/health` | `lamport` | `vetor` |
| Token de serviço (`svc`) | usado na chamada entre agências | removido (não há mais chamada HTTP entre agências) |
| `mesclar_logs.py` | ordena por Lamport | ordem causal, pares concorrentes e pares causais |

O que continua igual: particionamento (`id % 3`), JWT com autorização por posse,
o frontend e a idempotência por `Idempotency-Key`.

## Como ficou a arquitetura

- **Topologia:** exchange `iceibank.eventos` (topic, durável). Uma fila durável por
  agência (`fila-agencia-N`), ligada pela routing key `agencia.N.creditar`. Mensagens
  `persistent`. Para a funcionalidade adicional, cada fila tem como dead-letter
  exchange a `iceibank.dlx`, e cada agência tem uma `fila-agencia-N.dlq`.
- **Todas as agências declaram todas as filas ao subir.** Assim, se uma agência ainda
  nunca subiu, a mensagem para ela também fica retida, em vez de ser descartada por
  falta de fila.
- **Publicação:** o canal usa publisher confirms e `mandatory`. O `publicar` só
  termina quando o broker confirma. Se não confirmar (broker fora do ar, sem rota ou
  timeout de 5 s), a origem estorna o débito, registra `TRANSFERENCIA_ESTORNADA` e
  responde 503. Por isso 200 quer dizer "o broker aceitou a mensagem".
- **Consumidor:** roda no mesmo event loop do FastAPI (começa no `lifespan`). Isso
  mantém a premissa que o projeto já tinha: o saldo muda sem `await` no meio, então
  não precisa de lock. Com `pika` numa thread eu teria que proteger saldo,
  idempotência e relógio.
- **Relógio vetorial:** `services/vetorial.py`, com as três regras do roteiro e a
  função `comparar` (ANTES, DEPOIS, IGUAIS ou CONCORRENTES). Cada agência também
  reconstrói o vetor a partir do próprio log ao subir (ver "Decisões extras").
- **Mensagem:** `messageId`, `idConta`, `valorCentavos` (inteiro), `vetorEnvio`,
  `origemAgencia`, `idOrigem` e `idDestino`.
- **Idempotência adaptada:** a `Idempotency-Key` do cliente vira o `messageId` (sem
  chave, gero um UUID). O consumidor ignora um `messageId` já creditado. O estado
  `FALHOU` e o 502 do Sprint 1 saíram, porque não existe mais falha síncrona. Se a
  transferência falha de verdade (estorno), a chave é liberada para o cliente tentar
  de novo.

## Decisões extras (além do roteiro)

- **Relógio reconstruído a partir do log.** Na primeira execução real percebi que, ao
  reiniciar, a agência voltava a contar do zero (o vetor fica só em memória), e um
  evento novo dela parecia concorrente com os que ela mesma registrou antes. O log
  sobrevive ao reinício, então ao subir a agência assume o máximo dos vetores
  gravados. Sem isso, a análise de concorrência ficava errada.
- **O consumidor valida a mensagem** (conta pertence à agência, valor inteiro e
  positivo, vetor com o tamanho certo). Um valor negativo debitaria a conta, e quem
  publica na exchange não passa por JWT (ver a pergunta 3 da Parte C).
- **Estorno com evento.** O débito desfeito (destino local inexistente ou falha ao
  publicar) agora deixa um evento `TRANSFERENCIA_ESTORNADA` no log. No Sprint 1 o
  extrato mostrava um débito que tinha sido desfeito sem rastro.
- **`origem == destino` é rejeitado** com 400.
- **XSS no extrato corrigido** no frontend (monta a tabela com `textContent` em vez
  de `innerHTML`). Testei no navegador com um `nomeAluno` malicioso.

## Funcionalidade adicional (Sprint 2): dead-letter queue com retry

O que faz: quando o consumidor não consegue aplicar o crédito (por exemplo, a conta
não existe), ele não descarta a mensagem. Ele repete a entrega até 3 vezes
(republicando a mensagem com o contador `x-tentativas` e esperando 1 s entre as
tentativas). Na terceira falha, a mensagem sai da fila principal com `nack` sem
requeue, o broker a encaminha pela `iceibank.dlx` e ela fica em
`fila-agencia-N.dlq`. Mensagem inválida (JSON quebrado, valor inválido, conta de
outra agência) vai direto para a DLQ, porque repetir não adianta. Cada tentativa vira
um evento `CREDITO_REMOTO_FALHOU` (com a tentativa e o motivo) e o fim vira
`CREDITO_REMOTO_DLQ`.

Por que escolhi: é a que resolve o problema que o próprio roteiro faz a gente
encontrar. No cenário da seção 7.4 o crédito para uma conta que sumiu no reinício
seria apenas registrado e perdido. Com a DLQ, a mensagem fica guardada para ser
reprocessada ou compensada depois.

O que ela **não** faz: não estorna o débito da origem. O dinheiro continua fora da
conta de origem enquanto a mensagem estiver na DLQ. Compensar isso automaticamente é
uma Saga, e fica para o Sprint 4.

A política (`processar_com_politica`) é uma função só, usada pelo broker real e pelo
broker de teste, então os testes cobrem a mesma lógica que roda no RabbitMQ. Evidência:
`evidencias/sprint2/dlq.png`. Testes: `tests/test_dlq.py`.

## Parte B - Relógio vetorial (seção 6.4)

1. Com 3 agências o vetor tem 3 posições. Se o sistema crescesse para 10 agências,
o que aconteceria com o tamanho do vetor anexado a cada mensagem? Isso é um problema?

O vetor teria 10 posições, e esse tamanho cresce linearmente com o número de
agências (e todo evento gravado no log também carrega o vetor inteiro). Com 10
inteiros por mensagem isso não é problema, são alguns bytes. O problema aparece
quando o número de processos é grande ou muda o tempo todo (centenas ou milhares de
nós, ou nós entrando e saindo): cada mensagem e cada evento passam a carregar um
vetor enorme, e todo mundo precisa concordar sobre qual posição é de quem. Nesses
casos usam-se variações, como enviar só as posições que mudaram, vetores de versão
com "pontos" (dotted version vectors) ou relógios que se adaptam à entrada e saída
de nós (interval tree clocks). Aqui o número de agências é fixo (`NUMERO_AGENCIAS`
em `config.py`), então o vetor simples serve.

2. Dado V1 = [3, 1, 0] e V2 = [3, 2, 0], qual aconteceu primeiro?

O evento de V1 aconteceu antes. Comparando posição a posição: 3 ≤ 3, 1 ≤ 2 e 0 ≤ 0.
Então V1 ≤ V2 em todas as posições, e os vetores são diferentes (a posição 1 é
menor em V1). Portanto V1 → V2 (V1 é causa possível de V2, ou seja, V2 "já sabia"
de tudo que V1 sabia). O `comparar` do código devolve `ANTES` para esse par, e
isso está no teste `test_comparar_exemplo_6_4_pergunta_2`.

3. Dado V1 = [3, 1, 0] e V2 = [1, 3, 0], qual aconteceu primeiro?

São concorrentes. Na posição 0, V1 tem 3 e V2 tem 1, então V1 não é ≤ V2. Na posição
1, V1 tem 1 e V2 tem 3, então V2 não é ≤ V1. Como nenhum domina o outro, nenhum
evento conhecia o outro: não existe relação de causa e efeito entre eles. O
`comparar` devolve `CONCORRENTES` (teste `test_comparar_exemplo_6_4_pergunta_3`).

## Parte C - Publish/Subscribe (seção 7.5)

Os resultados abaixo vêm de uma execução real com 3 agências (uvicorn) e o
CloudAMQP, no dia 05/10/2026, e estão reproduzidos pelo `demo-sprint2.ps1` e pelos
prints em `evidencias/sprint2/`. As mesmas situações estão nos testes
automatizados (`tests/test_mensageria.py`, `tests/test_dlq.py`).

**Caminho feliz** (`evidencias/sprint2/transferencia-assincrona.png`): a conta 0
(agência 0) transferiu R$ 30 para a conta 1 (agência 1). A origem respondeu 200 com
"Transferência publicada para a agência de destino (entrega assíncrona)", e o destino
creditou ao consumir a mensagem. Os vetores ficaram assim:

```
agencia-0  [2,0,0]  TRANSFERENCIA_DEBITO
agencia-0  [3,0,0]  TRANSFERENCIA_PUBLICADA        (ao_enviar)
agencia-1  [3,2,0]  TRANSFERENCIA_CREDITO_REMOTO   (ao_receber: max([0,1,0],[3,0,0]) = [3,1,0], +1 na posição 1)
```

1. No passo 4, o que aconteceu exatamente quando a Agência 1 voltou? Se a mensagem
"sumiu", foi por falha da mensageria ou por outro motivo?

Com a agência 1 fora do ar, a transferência de R$ 20 respondeu 200 e a mensagem
ficou retida: o `ver_filas.py` mostrava 1 mensagem pronta em `fila-agencia-1` e
nenhum consumidor. Quando a agência 1 voltou, ela conectou, consumiu a fila e a
mensagem **foi entregue**. O log dela mostrou o crédito falhando com o motivo
"conta nao encontrada": a agência reiniciou com o estado zerado, e a conta 1 existia
só na memória do processo antigo. Ou seja, a mensageria não falhou. Ela cumpriu o que
promete (não perder a mensagem enquanto a agência estava fora). O que falhou foi a
aplicação do crédito, porque as contas não são persistidas.

No log da primeira execução (antes de eu implementar a DLQ), isso virou um único
`CREDITO_REMOTO_FALHOU [5,1,0]` e a mensagem era confirmada (`ack`) e descartada:
aí ela de fato "sumia". Com a DLQ, a agência tenta 3 vezes (eventos com a tentativa
1, 2 e 3), registra `CREDITO_REMOTO_DLQ`, e a mensagem fica em
`fila-agencia-1.dlq` (o `ver_filas.py` mostra 1 mensagem lá). Enquanto isso o saldo
da conta de origem continua com o débito aplicado (R$ 50 depois das duas
transferências). Evidências: `resiliencia-fila.png` e `dlq.png`.

2. Compare com o Sprint 1: o que melhorou e o que continua sendo um problema em
aberto?

Melhorou: (a) o destino fora do ar deixou de derrubar a transferência: antes era um
502 na hora, agora a mensagem fica guardada em disco no broker (fila durável e
mensagem `persistent`) e é entregue quando a agência voltar; (b) o acoplamento
diminuiu, a origem não precisa conhecer a URL do destino nem esperar por ele, só
publica na exchange; (c) a falha de publicação é tratada (estorno e 503), então o
débito não fica pendurado por causa do broker.

Continua em aberto: "a mensagem não se perde" não é o mesmo que "o sistema está
correto". (a) O débito da origem e o crédito do destino ainda não são atômicos. Se o
crédito não puder ser aplicado, o dinheiro sai de uma conta e não entra na outra (a
DLQ guarda a mensagem, mas não compensa). (b) As contas e as chaves de idempotência
ficam em memória e somem no reinício. Isso gerou o cenário acima, e também
significa que uma mensagem reentregue depois de um reinício poderia creditar de novo
se a conta já existisse. (c) O RabbitMQ entrega pelo menos uma vez, então a
deduplicação por `messageId` é necessária, mas só vale enquanto o processo vive. (d)
200 agora só diz que a mensagem foi publicada: o cliente não sabe quando, nem se, o
crédito foi aplicado (uma confirmação de entrega resolveria). Persistência e
transações distribuídas (2PC ou Saga) ficam para o Sprint 4.

3. O consumidor processa créditos sem verificar JWT. Isso é um problema de segurança?

É uma preocupação real, mas a fronteira de confiança mudou de lugar: ela não está
mais na API HTTP, está no broker. Quem consegue publicar em `iceibank.eventos` pode
mandar um crédito para qualquer conta, sem token nenhum. No meu ambiente de
desenvolvimento, quem consegue publicar é quem tem a `RABBITMQ_URL`, que tem um único
usuário e senha usados pelas três agências (e a pessoa que tem a URL poderia até ler
as filas). Como só eu tenho essa URL, o risco é baixo aqui, mas num ambiente real
seria um problema sério: uma credencial vazada vira "imprimir dinheiro".

Para reduzir o risco: usuários e permissões diferentes por agência no broker (cada
uma só publica nas routing keys que precisa); TLS (a URL já é `amqps`); vhost
próprio; e assinatura da mensagem (por exemplo um HMAC ou um JWT de serviço dentro do
corpo, verificado no consumidor, como era o token `svc` do Sprint 1). Enquanto isso,
fiz o que dava dentro do código: o consumidor valida o conteúdo (valor inteiro e
positivo, vetor do tamanho certo, conta que pertence à agência), e o que é inválido
vai para a DLQ em vez de ser aplicado. Não implementei assinatura de mensagens.

## Parte D - Linha do tempo causal (seção 8.3)

O `mesclar_logs.py` ordena os eventos por soma do vetor (desempate por hora de parede
e agência), lista os pares concorrentes entre agências diferentes e lista os pares
causais débito → crédito ligados pelo `messageId`. A ordenação não usa só a hora de
parede de propósito: se um evento causou o outro, o vetor do primeiro é menor ou
igual em todas as posições, então a soma dele é menor e ele sempre vem antes, mesmo
que o relógio de uma máquina esteja adiantado (há teste para isso). Evidência:
`evidencias/sprint2/linha-do-tempo-causal.png`.

1. O que, no relógio vetorial, torna a comparação confiável?

O vetor guarda, para cada processo, quantos eventos dele o evento atual já conhece.
Então V1 ≤ V2 em todas as posições quer dizer que o evento 2 já conhecia tudo que o
evento 1 conhecia, ou seja, o 1 pode ter causado o 2. E se nenhum vetor domina o
outro, nenhum evento conhecia o outro. Isso vale nos dois sentidos (A aconteceu
antes de B se e somente se V(A) < V(B)). Já o Lamport comprime tudo em um número e
só garante um sentido (A antes de B implica ts(A) < ts(B)); o inverso não vale, por
isso timestamps diferentes não provavam causa. O vetor não perde essa informação
porque guarda uma contagem por processo, e as regras de `max` ao receber propagam o
conhecimento junto com a mensagem.

2. Encontre no seu teste um par classificado como concorrente. Faz sentido?

Na saída do `mesclar_logs.py` apareceram, por exemplo:

```
[agencia-0] CRIAR_CONTA [1,0,0]  x  [agencia-1] CRIAR_CONTA [0,1,0]
[agencia-0] TRANSFERENCIA_DEBITO [4,0,0]  x  [agencia-1] TRANSFERENCIA_CREDITO_REMOTO [3,2,0]
```

O primeiro par faz sentido de forma óbvia: cada agência criou uma conta por conta
própria, sem trocar mensagem, então nenhum evento pode ter influenciado o outro. O
segundo é mais interessante: o débito [4,0,0] é da segunda transferência e o crédito
[3,2,0] é da primeira. O crédito da primeira aconteceu sem que a agência 0 soubesse
do segundo débito (posição 0 do crédito é 3, menor que 4), e o segundo débito
aconteceu sem que a agência 0 soubesse do crédito da agência 1 (posição 1 do débito é
0, menor que 2). Cada um tem um pedaço de informação que o outro não tem, então são
concorrentes, mesmo sendo duas transferências da mesma conta.

O par causal certo aparece na seção de pares causais, e não na de concorrentes:
`TRANSFERENCIA_DEBITO [2,0,0]` ANTES de `TRANSFERENCIA_CREDITO_REMOTO [3,2,0]`, do
mesmo `messageId`, porque [2,0,0] ≤ [3,2,0] em todas as posições.

3. O algoritmo de comparação é O(n²). Seria um problema com milhões de eventos?

Seria. Com 1 milhão de eventos são cerca de 5 × 10¹¹ comparações de vetores, o que
é inviável de rodar numa só máquina e ainda leria tudo em memória. Para escalar:
(a) não procurar todos os pares, e sim perguntar sobre pares específicos (por
exemplo, só eventos que mexem na mesma conta, que são os que importam para
conflito); (b) dividir os eventos em janelas e por conta, comparando só dentro de
cada grupo; (c) processar em streaming, mantendo só a "fronteira" dos eventos ainda
abertos em vez do histórico inteiro; (d) usar a ordem parcial sem materializar
todos os pares, por exemplo reconstruindo o grafo de causa (envio → recebimento)
e consultando alcançabilidade; (e) paralelizar a análise por partições (MapReduce) e
(f) limitar a análise a uma amostra ou a um período. Também ajuda reduzir o custo de
cada comparação com vetores esparsos.

## Evidências do Sprint 2

Em `evidencias/sprint2/`: `transferencia-assincrona.png`, `resiliencia-fila.png`,
`linha-do-tempo-causal.png` e `dlq.png` (funcionalidade adicional).

## Regressão: o que continua funcionando

Verificado com os testes automatizados (JWT, posse, partição, contas, extrato,
idempotência local) e manualmente no frontend (login, criar contas, transferência
entre agências, extrato com vetor, painel das agências).

## Dívidas conhecidas (não tratadas neste sprint)

- Contas e chaves de idempotência só em memória (é o assunto do cenário da Parte C).
- O débito não é compensado quando o crédito vai para a DLQ (Sprint 4).
- O frontend tem a porta base 4000 fixa e ignora o `OFFSET`.
- O segredo do JWT tem um valor padrão de desenvolvimento no código.
- O `registrar` do log grava em arquivo de forma síncrona dentro de handlers async.
- Mensagens não são assinadas, e as três agências usam o mesmo usuário no RabbitMQ.
- Se o processo cai depois do débito e antes do `publicar`, o débito fica sem mensagem
  (um padrão de outbox resolveria).

---

# Sprint 1 (como foi entregue)

> Os textos abaixo descrevem o sistema do Sprint 1 (relógio de Lamport e chamada
> REST `creditar-remoto`). As partes que mudaram estão resumidas na tabela do
> Sprint 2 acima.

## Funcionalidade adicional: idempotência de transferências

O que faz: toda transferência aceita um cabeçalho `Idempotency-Key`, que é único
por operação. A agência de origem guarda o resultado dessa chave. Se a mesma
requisição chegar de novo (a pessoa clicou duas vezes, ou o navegador/rede fez um
retry), o débito não é aplicado outra vez, e ela recebe a resposta que já tinha
sido dada. Essa chave também vai junto na chamada para a agência de destino
(`creditar-remoto`), que faz a mesma checagem. Assim um retry de rede entre
agências não credita duas vezes. É idempotência dos dois lados.

Por que escolhi: débito em dobro por reenvio é um problema real e sério num banco,
e retry é algo que sempre acontece quando tem rede no meio, então combina bem com
o tema de sistemas distribuídos e ajuda a pensar na Sprint 4. Além disso é um
comportamento novo de verdade (um endpoint que passa a responder diferente quando
é reenviado), diferente de autenticação e frontend, que já são obrigatórios.

Sobre os estados: cada chave fica como `EM_ANDAMENTO` (uma cópia concorrente da
mesma operação recebe 409), `CONCLUIDA` (o reenvio devolve a resposta guardada) ou
`FALHOU`. No caso `FALHOU`, que é a falha conhecida, o reenvio não debita de novo,
ele só tenta o crédito remoto outra vez. Isso não resolve a atomicidade da falha
(o débito continua sem estorno automático, o que é assunto da Sprint 4), só
garante que a transferência aconteça no máximo uma vez para cada chave.

Evidência: `evidencias/sprint1/funcionalidade-adicional.png`.

## Parte B - Relógio de Lamport (seção 6.4)

1. Por que usar `max(contador_local, timestampRecebido) + 1` ao receber, em vez de
adotar o timestamp recebido direto?

Porque o relógio precisa respeitar a causalidade e nunca voltar para trás. Se a
agência que recebe já está num contador maior que o valor recebido, adotar o valor
recebido faria o contador diminuir, e aí eventos novos poderiam ganhar um timestamp
menor que eventos que já aconteceram antes, o que quebra a regra "se A aconteceu
antes de B, então ts(A) < ts(B)". O `max` garante que o contador não diminui, e o
`+1` garante que o evento de recebimento fica depois tanto do último evento local
quanto do envio na outra agência, porque a mensagem só chega depois de ter sido
enviada.

2. A Agência 0 está no contador 10 e recebe uma mensagem com timestamp 3. Qual o
novo valor?

`max(10, 3) + 1 = 11`. A mensagem atrasada (timestamp 3) não puxa o relógio para
baixo. O que isso mostra: agências que processam muitos eventos rápido ficam com
contadores altos, e quando falam com agências mais devagar acabam "puxando" o
relógio delas para cima (a mais lenta pula para o valor da rápida mais um). O
contrário nunca acontece, uma agência nunca é rebaixada por causa de outra mais
atrasada. Os contadores contam quantidade de eventos ordenados por causa, não tempo
de relógio de parede.

## Parte D - Transferências (seção 8.3)

1. Por que a transferência local não precisa de `ao_enviar()/ao_receber()` e a
transferência entre agências precisa?

Porque `ao_enviar`/`ao_receber` servem para ordenar eventos de processos diferentes
que trocam mensagem. Na transferência local, o débito e o crédito acontecem no
mesmo processo, já que a mesma agência é dona das duas contas. Não tem mensagem
saindo de um processo para outro, então os dois são só eventos locais
(`evento_local`), já ordenados pelo contador único daquela agência. Na
transferência entre agências existe uma mensagem REST que sai de uma agência e
chega na outra. É aí que entram a regra 2 (incrementa e manda o timestamp junto ao
enviar) e a regra 3 (`max+1` ao receber), para o crédito no destino ficar depois do
débito na origem, mesmo sendo processos separados com relógios independentes.

2. Reproduza a falha conhecida e veja o saldo da origem depois do erro. Foi
revertido? O que isso significa para a consistência?

Não foi revertido. Quando derrubo a agência de destino, a origem já aplicou o
débito local (`TRANSFERENCIA_DEBITO`) e a chamada `creditar-remoto` falha com 502
(fica registrado `TRANSFERENCIA_FALHOU` no log). O dinheiro sai da origem mas não
chega no destino, então o sistema fica inconsistente por um tempo, a soma dos
saldos das agências diminui. Não tem atomicidade, a operação não é tudo ou nada.
Num banco de verdade isso não pode acontecer, mas aqui é de propósito, para o
problema ficar visível.

3. Pensando na Sprint 4, cite duas formas de corrigir isso (em alto nível):

- 2PC (Two-Phase Commit): um coordenador pergunta para as duas agências se elas
  conseguem efetivar (fase de preparação). Só se as duas responderem que sim ele
  manda efetivar (fase de commit). Se alguma não conseguir, tudo é abortado e o
  débito nem chega a ser confirmado. Garante atomicidade, mas em troca trava
  recursos e depende do coordenador.
- Saga com compensação: a transferência vira uma sequência de passos locais, e se
  um passo falha roda-se uma ação de compensação para desfazer os passos anteriores
  (no caso, estornar o débito). É mais resistente e não trava, mas a consistência é
  eventual, tem uma janela em que o sistema fica inconsistente até a compensação
  rodar.

## Parte E - Linha do tempo unificada (seção 10.3)

O que observei na saída do `mesclar_logs.py`: dois eventos `CRIAR_CONTA`, um na
`agencia-0` e outro na `agencia-1`, ficaram com o mesmo `timestampLamport = 1`, com
horas de parede parecidas mas diferentes. Esses dois eventos são concorrentes,
nenhum influenciou o outro, cada agência criou uma conta por conta própria, sem
trocar mensagem. Nesses casos a ordem por hora de parede pode até não bater com a
ordem por Lamport, justamente porque não tem relação de causa entre eles.

1. O relógio garante que se A aconteceu antes de B então ts(A) < ts(B), mas não
garante a volta. O que isso significa na prática?

Significa que, ao ver `ts(A) < ts(B)`, não dá para afirmar que A influenciou B.
Pode ser causa de verdade, ou pode ser só coincidência de dois eventos concorrentes
que caíram nessa ordem. O relógio de Lamport dá uma ordem total que respeita a
causalidade, mas ele perde a informação de quais pares são concorrentes, porque
coloca eventos concorrentes numa ordem qualquer (só que sempre a mesma).

2. O relógio de Lamport sozinho dá para distinguir com certeza "concorrente" de
"aconteceu antes"? Por que isso motiva o relógio vetorial?

Não dá. Com Lamport, timestamps iguais sugerem concorrência, mas timestamps
diferentes não separam causa de concorrência (é o caso da questão 1). Para afirmar
com certeza que "A e B são concorrentes" precisa do relógio vetorial, que guarda um
contador por processo. Comparando os vetores, se nenhum é maior que o outro em tudo
os eventos são concorrentes de fato, e se um domina o outro tem causa. Essa certeza
sobre concorrência é justamente o que a Sprint 2 acrescenta.

## Parte F - Autenticação JWT (seção 11.3)

Decisões de design (pedidas na seção 11.1):

- Formato das credenciais: usuário e senha, comparados com uma lista de usuários
  fixa (`config.USUARIOS`), igual nas 3 agências, com as senhas guardadas só como
  hash Argon2id (usando pwdlib). Fiz assim porque a pessoa pode entrar por qualquer
  uma das 3 agências, então as três precisam conhecer os mesmos usuários. Uma lista
  fixa compartilhada mais um segredo de JWT compartilhado resolve isso sem eu ter
  que sincronizar cadastro entre agências, o que já seria um problema distribuído
  fora do escopo desta sprint. Cada conta tem um `dono` (um usuário da lista), e é
  isso que permite a autorização por posse.
- Chamada entre agências (`creditar-remoto`): decidi que ela leva um token de
  serviço, que é um JWT com o campo `tipo=svc`, gerado pela agência de origem e
  assinado com o mesmo segredo, e a de destino valida esse token. Não uso o token
  do usuário porque o crédito remoto é uma confiança entre sistemas, não uma ação
  de um usuário específico. Separar as duas identidades é mais correto e evita
  amarrar a chamada interna à sessão do usuário, que poderia até expirar no meio.
  Mesmo assim continua valendo a regra de que toda rota que mexe em conta exige um
  token válido.
- Expiração: o token de usuário dura 30 minutos, e o de serviço 60 segundos (curto
  porque ele é gerado a cada chamada).

1. Qual a diferença entre autenticação e autorização? Sua implementação faz uma ou
as duas? Um usuário logado consegue sacar de uma conta que não é dele?

Autenticação é provar quem você é (o login confere a senha e emite o JWT).
Autorização é decidir o que você pode fazer. A minha implementação faz as duas.
Além de exigir um token válido (autenticação), cada operação direta numa conta
confere se o `sub` do token é o `dono` da conta (função `garantir_posse`). Então um
usuário logado não consegue consultar, depositar, sacar ou transferir de uma conta
que não é dele, ele recebe 403. A conta de destino de uma transferência pode ser de
outro dono, o que é o esperado numa transferência.

2. Por que o servidor não precisa consultar um banco para validar a assinatura do
JWT a cada requisição? O que isso implica em escalabilidade, comparado a guardar
sessões em memória?

Porque o JWT é assinado e carrega tudo dentro dele. O servidor só recalcula a
assinatura com o segredo e confere, e a identidade e a validade estão no próprio
token, sem precisar buscar uma sessão em lugar nenhum. Isso escala melhor que
guardar sessão na memória do servidor, porque qualquer agência valida o token sem
depender de um estado compartilhado. É por isso que aqui dá para logar numa agência
e usar o token em outra. Se fosse sessão em memória, precisaria de um lugar comum
para guardar as sessões (ou fixar a pessoa sempre no mesmo servidor), o que vira um
ponto central de coordenação.

3. O que aconteceria com a segurança se a chave secreta vazasse?

Qualquer pessoa conseguiria forjar tokens válidos, inclusive tokens de serviço, se
passando por qualquer usuário e autorizando qualquer operação. O sistema todo
estaria comprometido, porque toda a confiança está nessa chave. O que dá para fazer:
trocar o segredo na hora (isso invalida todos os tokens que estão em uso), manter o
segredo fora do código e do repositório (em variável de ambiente ou num cofre) e
usar expiração curta para diminuir a janela de estrago.

## Parte G - Frontend (seção 12.3)

1. Como o frontend "lembra" de reenviar o token em cada requisição?

No login, o token é guardado no `localStorage` (no Model). O módulo `Api`
(`api.js`) concentra todo `fetch` e, antes de cada requisição, coloca sozinho o
cabeçalho `Authorization: Bearer <token>` lendo do Model. Assim nenhuma tela
precisa lembrar do token na mão, ele fica num único lugar.

2. Se o token expira no meio de uma operação, o que acontece? A interface avisa?

Avisa. Qualquer resposta 401 é tratada no Controller: a sessão é encerrada (o token
é apagado), a tela volta para o login e aparece a mensagem "Sessão expirada ou
inválida. Faça login novamente". Não é um erro genérico só no console, é uma
mensagem que a pessoa vê na tela.

3. No seu frontend, onde ficam o M, o V e o C?

A separação está em arquivos diferentes. O Model (`model.js`) guarda o estado e o
token no localStorage. A View (`view.js`) só mexe no DOM, mostrando telas,
mensagens e formatando valores. O Controller (`controller.js`) liga os eventos dos
formulários às chamadas da API e atualiza o Model e a View. O `api.js` é a camada
que fala com a API, usada pelo Controller. A View não fala direto com a API e o
Model não conhece o DOM, então o MVC está bem separado e não ficou tudo misturado.
