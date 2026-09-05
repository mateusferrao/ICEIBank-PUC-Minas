# RESPOSTAS - ICEIBank Sprint 1

O ICEIBank é um banco dividido em 3 agências. O mesmo código roda três vezes, cada
processo com um `AGENCIA_ID` diferente. Cada agência é dona de uma parte das contas
e registra tudo com um relógio de Lamport. Também tem autenticação por JWT, um
frontend web e idempotência de transferências como funcionalidade adicional.

Escolhi Python com FastAPI, e vou manter essa linguagem da Sprint 1 até a 4. O
dinheiro é guardado em centavos (inteiro) por dentro e mostrado em reais na API,
para não ter erro de arredondamento.

## Como executar

Backend (3 agências, cada uma em um terminal, dentro de `agencia/`):

```
python -m venv .venv && . .venv/bin/activate   # (Windows: .venv\Scripts\Activate.ps1)
pip install -r requirements.txt

# Terminal 1:  AGENCIA_ID=0 python -m uvicorn src.main:app --port 4000
# Terminal 2:  AGENCIA_ID=1 python -m uvicorn src.main:app --port 4001
# Terminal 3:  AGENCIA_ID=2 python -m uvicorn src.main:app --port 4002
```

No PowerShell: `$env:AGENCIA_ID=0; python -m uvicorn src.main:app --port 4000`.

Testes: `pytest` (dentro de `agencia/`). Demonstração: `demo.ps1` no PowerShell ou
`demo.sh` no Linux/Mac. Linha do tempo: `python mesclar_logs.py`. Frontend: abra o
`frontend/index.html` (ou sirva com `python -m http.server`) e escolha no seletor
qual agência é a porta de entrada. Além de login, saldo, depósito, saque e
transferência, o frontend tem a aba Extrato (histórico de eventos de uma conta,
via `GET /contas/{id}/extrato`) e a aba Painel das Agências, que mostra o relógio
de Lamport e a quantidade de contas das 3 agências ao vivo.

Também dá para subir tudo com Docker (as 3 agências mais o frontend de uma vez),
já pensando na Sprint 4:

```
docker compose up --build
# API: localhost:4000/4001/4002   Frontend: http://localhost:5500
```

Dentro do compose as agências se acham pelo nome do serviço (`AGENCIA_*_HOST`),
então a chamada entre agências funciona na rede do Docker.

Usuários de teste (seed, iguais nas 3 agências): `ana`/`senha-ana`,
`bruno`/`senha-bruno`, `carla`/`senha-carla`.

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
