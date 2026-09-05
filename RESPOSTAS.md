# RESPOSTAS — ICEIBank Sprint 1

Aplicação: banco particionado em 3 agências (mesmo código, `AGENCIA_ID`
diferente), com relógio de Lamport, autenticação JWT, frontend web e
idempotência de transferências como funcionalidade adicional.

Stack escolhida: **Python + FastAPI** (mantida da Sprint 1 à 4). Dinheiro é
tratado em **centavos (int)** internamente e exposto em **reais** na API.

---

## Como executar

Backend (3 agências, cada uma em um terminal, a partir de `agencia/`):

```
python -m venv .venv && . .venv/bin/activate   # (Windows: .venv\Scripts\Activate.ps1)
pip install -r requirements.txt

# Terminal 1:  AGENCIA_ID=0 python -m uvicorn src.main:app --port 4000
# Terminal 2:  AGENCIA_ID=1 python -m uvicorn src.main:app --port 4001
# Terminal 3:  AGENCIA_ID=2 python -m uvicorn src.main:app --port 4002
```

No PowerShell: `$env:AGENCIA_ID=0; python -m uvicorn src.main:app --port 4000`.

Testes: `pytest` (a partir de `agencia/`). Demonstração: `demo.ps1` (PowerShell)
ou `demo.sh` (Linux/Mac). Linha do tempo: `python mesclar_logs.py`.
Frontend: abra `frontend/index.html` (ou sirva com `python -m http.server`) e
escolha a agência de entrada no seletor.

Usuários de teste (seed, iguais nas 3 agências): `ana`/`senha-ana`,
`bruno`/`senha-bruno`, `carla`/`senha-carla`.

---

## Funcionalidade adicional: Idempotência de transferências

**O que faz:** cada transferência aceita um cabeçalho `Idempotency-Key` único
por operação. A agência de origem guarda o resultado por chave; se a mesma
requisição for reenviada (usuário clica duas vezes, retry automático do
navegador/rede), o débito **não** é aplicado de novo — devolve o resultado
anterior. A chave é **propagada à agência de destino** na chamada
`creditar-remoto`, que também faz deduplicação; assim um retry de rede entre
agências não credita duas vezes. É a idempotência **ponta a ponta**.

**Por que escolhi:** é o tipo de falha que o domínio bancário torna crítica
(débito em duplicidade por reenvio) e tem sabor de sistemas distribuídos —
retries são inevitáveis quando há rede no meio, e prepara terreno para o
Sprint 4. Diferente de autenticação e frontend, é comportamento novo e
observável (um endpoint que passa a se comportar de forma diferente sob
reenvio).

**Detalhe do estado:** cada chave tem estado `EM_ANDAMENTO` (duplicata
concorrente → 409), `CONCLUIDA` (replay devolve a resposta guardada) ou
`FALHOU` (a "falha conhecida": o replay **não redebita**, apenas retenta a
perna de crédito remoto — recuperação idempotente). Isso **não** resolve a
atomicidade sob falha (o débito continua sem rollback automático — isso é o
Sprint 4); a idempotência apenas garante que a transferência seja aplicada
**no máximo uma vez** por chave.

Evidência: `evidencias/sprint1/funcionalidade-adicional.png`.

---

## Parte B — Relógio de Lamport (seção 6.4)

**1. Por que `max(contador_local, timestampRecebido) + 1` ao receber, em vez de
adotar o timestamp recebido diretamente?**

Porque o relógio precisa preservar a causalidade **e** nunca andar para trás. Se
a agência receptora já está num contador maior que o recebido, adotar o valor
recebido faria o relógio **retroceder**, e eventos futuros locais poderiam
receber timestamps menores que eventos passados — violando a propriedade "se A
aconteceu-antes de B, então ts(A) < ts(B)". O `max` garante que o contador nunca
diminui; o `+1` garante que o evento de recebimento é estritamente posterior
tanto ao último evento local quanto ao evento de envio na outra agência (a
mensagem chegou *depois* de ter sido enviada).

**2. Agência 0 no contador 10 recebe uma mensagem com timestamp 3. Novo valor?**

`max(10, 3) + 1 = 11`. A mensagem "atrasada" (timestamp 3) não puxa o relógio
para baixo. Implicação: agências que processam muitos eventos rapidamente
acumulam contadores altos; ao se comunicarem com agências mais lentas, "puxam"
o relógio destas para cima (a lenta salta para o valor da rápida + 1), mas o
contrário nunca acontece — uma agência nunca é rebaixada por uma mensagem de
outra mais atrasada. Os contadores refletem quantidade de eventos causalmente
ordenados, não tempo físico.

---

## Parte D — Transferências (seção 8.3)

**1. Por que a transferência local não precisa de `ao_enviar()/ao_receber()`,
mas a transferência entre agências precisa?**

Porque `ao_enviar`/`ao_receber` existem para ordenar eventos **entre processos
diferentes** que trocam mensagem. Na transferência local, débito e crédito
acontecem no **mesmo processo** (a mesma agência é dona das duas contas): não há
mensagem cruzando fronteira de processo, então os dois são apenas eventos locais
(`evento_local`), já naturalmente ordenados pelo contador único daquele
processo. Na transferência entre agências há uma mensagem REST saindo de uma
agência e chegando na outra — é aí que entram a regra 2 (incrementa e anexa o
timestamp ao enviar) e a regra 3 (`max+1` ao receber), para que o crédito no
destino seja causalmente posterior ao débito na origem, mesmo sendo processos
distintos com relógios independentes.

**2. Reproduza a falha conhecida e observe o saldo da origem depois do erro. Foi
revertido? O que significa em termos de consistência?**

Não foi revertido. Ao derrubar a agência de destino, a origem já aplicou o
débito localmente (`TRANSFERENCIA_DEBITO`), e a chamada `creditar-remoto` falha
com 502 (`TRANSFERENCIA_FALHOU` no log). O dinheiro sai da origem mas nunca chega
ao destino: o sistema fica **temporariamente inconsistente** — a soma total dos
saldos das agências diminui. Não há atomicidade: a operação não é "tudo ou
nada". Em um banco real isso é inaceitável; aqui é intencional, para deixar o
problema visível.

**3. Duas formas de corrigir isso no Sprint 4 (alto nível):**

- **2PC (Two-Phase Commit):** um coordenador pergunta às duas agências se podem
  efetivar (fase de preparação); só se ambas responderem "sim" ele manda
  efetivar (fase de commit). Se qualquer uma não puder, tudo é abortado e o
  débito não chega a ser confirmado. Garante atomicidade ao custo de bloqueio e
  dependência do coordenador.
- **Saga (com compensação):** a transferência é uma sequência de passos locais;
  se um passo falha, executa-se uma **ação compensatória** dos passos já feitos
  (aqui: estornar o débito). É mais resiliente e não bloqueia, mas a consistência
  é eventual (há uma janela em que o sistema está inconsistente até a compensação
  rodar).

---

## Parte E — Linha do tempo unificada (seção 10.3)

Observação real (saída de `mesclar_logs.py` na demonstração): dois eventos
`CRIAR_CONTA` — um na `agencia-0` e outro na `agencia-1` — receberam o **mesmo**
`timestampLamport = 1`, com horas de parede próximas mas distintas. Esses dois
eventos são **concorrentes**: nenhum influenciou o outro (cada agência criou uma
conta independentemente, sem troca de mensagem entre elas). A ordem por hora de
parede pode até divergir da ordem por Lamport nesses casos, justamente porque
são eventos sem relação causal.

**1. O relógio garante A→B ⟹ ts(A) < ts(B), mas não a volta. O que isso significa
na prática?**

Significa que, ao ver `ts(A) < ts(B)`, você **não pode concluir** que A
influenciou B: pode ser causalidade real, ou pode ser mero acaso de dois eventos
concorrentes que caíram em ordem. O relógio de Lamport dá uma ordem total
*consistente com* a causalidade, mas perde a informação de quais pares são
concorrentes — ele "achata" eventos concorrentes numa ordem arbitrária porém
determinística.

**2. O relógio de Lamport sozinho basta para distinguir "concorrente" de
"aconteceu-antes"? Por que isso motiva o relógio vetorial?**

Não basta. Com Lamport, timestamps iguais sugerem concorrência, mas timestamps
**diferentes** não distinguem causalidade de concorrência (ver questão 1). Para
afirmar com certeza "A e B são concorrentes" é preciso um **relógio vetorial**,
que guarda um contador por processo: comparando os vetores, se nenhum domina o
outro, os eventos são provadamente concorrentes; se um domina, há causalidade.
Essa capacidade de detectar concorrência com certeza é exatamente o que o
Sprint 2 acrescenta.

---

## Parte F — Autenticação JWT (seção 11.3)

**Decisões de design (pedidas na seção 11.1):**

- **Formato das credenciais:** usuário + senha, contra um diretório de usuários
  em *seed* fixo, idêntico nas 3 agências (`config.USUARIOS`, senhas guardadas só
  como hash bcrypt). Escolhi assim porque cada usuário pode entrar por **qualquer**
  agência (a "porta de entrada"), então o diretório precisa ser conhecido pelas
  três; um seed compartilhado + segredo JWT compartilhado resolve isso sem
  precisar propagar cadastro entre agências (o que seria um problema distribuído
  fora do escopo). Cada conta tem um `dono` (um usuário do seed), o que habilita
  a autorização de posse.
- **Chamada entre agências (`creditar-remoto`):** decidi que ela carrega um
  **token de serviço** (JWT com claim `tipo=svc`), gerado pela agência de origem
  e assinado com o mesmo segredo, e a de destino o valida. Não uso o token do
  usuário: o crédito remoto é uma confiança **sistema-a-sistema**, não uma ação
  de um usuário específico — separar as duas identidades é mais correto e evita
  acoplar a chamada interna ao ciclo de vida da sessão do usuário (que poderia
  expirar no meio). Ainda assim, mantém o requisito de que toda rota que altera
  conta exija um token válido.
- **Expiração:** token de usuário expira em 30 min; token de serviço em 60 s
  (curto porque é gerado por chamada).

**1. Diferença entre autenticação e autorização. Sua implementação faz uma ou as
duas? Um usuário logado consegue sacar de conta que não é dele?**

Autenticação = provar **quem** você é (o login valida a senha e emite o JWT).
Autorização = decidir **o que** você pode fazer. Minha implementação faz **as
duas**: além de exigir token válido (autenticação), cada operação direta em uma
conta verifica se o `sub` do token é o `dono` da conta (`garantir_posse`). Logo,
um usuário autenticado **não** consegue sacar/consultar/depositar/transferir de
uma conta que não é dele — recebe **403**. (A conta de *destino* de uma
transferência pode ser de outro dono, o que é o comportamento esperado de uma
transferência.)

**2. Por que o servidor não precisa consultar um banco para validar a assinatura
do JWT? Implicação para escalabilidade vs. sessões em memória.**

O JWT é **auto-contido e assinado**: o servidor só precisa recalcular a
assinatura com o segredo e conferir; a identidade e a expiração vêm dentro do
próprio token. Não há lookup de sessão. Isso escala melhor que sessões em
memória no servidor: qualquer agência (qualquer réplica) valida o token sem
estado compartilhado — é justamente o que permite, aqui, logar em uma agência e
usar o token em outra. Sessões em memória exigiriam um store compartilhado
(sticky sessions ou um Redis central), criando um ponto de coordenação.

**3. O que aconteceria se a chave secreta vazasse?**

Qualquer um poderia **forjar** tokens válidos (inclusive tokens de serviço),
personificando qualquer usuário e autorizando qualquer operação — o sistema
inteiro estaria comprometido, pois toda a confiança está na chave. Mitigação:
rotacionar o segredo imediatamente (invalida todos os tokens em circulação),
manter o segredo fora do código/repositório (variável de ambiente/cofre) e usar
expirações curtas para reduzir a janela de abuso.

---

## Parte G — Frontend (seção 12.3)

**1. Como o frontend "lembra" de reenviar o token a cada requisição?**

No login, o token é guardado no `localStorage` (Model). O módulo `Api`
(`api.js`) centraliza todo `fetch` e, antes de cada requisição, injeta
automaticamente o cabeçalho `Authorization: Bearer <token>` lido do Model. Assim
nenhuma tela precisa lembrar do token manualmente — está em um único ponto.

**2. Se o token expira no meio do uso, o que acontece? A interface avisa?**

Sim, avisa. Qualquer resposta **401** é detectada no tratamento de erros do
Controller: a sessão é encerrada (token removido), a tela volta ao login e é
exibida a mensagem "Sessão expirada ou inválida. Faça login novamente" — não é
um erro genérico no console, é uma mensagem visível para a pessoa.

**3. Onde ficam o M, o V e o C no seu frontend?**

A separação é explícita em arquivos: **Model** (`model.js`) guarda o estado e o
token (localStorage); **View** (`view.js`) só toca o DOM (mostrar telas,
mensagens, formatar valores); **Controller** (`controller.js`) liga os eventos
dos formulários às chamadas da API e atualiza Model/View. O `api.js` é a camada
de acesso à API usada pelo Controller. A View não fala com a API diretamente e o
Model não conhece o DOM — a separação MVC está clara, não misturada.
