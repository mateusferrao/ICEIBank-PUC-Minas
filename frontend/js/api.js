// Api (parte do "Controller" no MVC): fala com a API REST da agência.
// Centraliza o fetch, injeta automaticamente o cabeçalho Authorization com o
// token guardado no Model e gera o Idempotency-Key nas transferências.
const Api = {
  async _requisicao(caminho, { metodo = "GET", corpo = null, idempotencyKey = null } = {}) {
    const cabecalhos = { "Content-Type": "application/json" };
    if (Model.token) cabecalhos["Authorization"] = `Bearer ${Model.token}`;
    if (idempotencyKey) cabecalhos["Idempotency-Key"] = idempotencyKey;

    let resposta;
    try {
      resposta = await fetch(Model.baseUrl() + caminho, {
        method: metodo,
        headers: cabecalhos,
        body: corpo ? JSON.stringify(corpo) : undefined,
      });
    } catch (e) {
      // Falha de rede (agência fora do ar, CORS, etc.)
      const erro = new Error("Não foi possível contatar a agência. Ela está no ar?");
      erro.status = 0;
      throw erro;
    }

    let dados = null;
    try {
      dados = await resposta.json();
    } catch (e) {
      /* resposta sem corpo JSON */
    }

    if (!resposta.ok) {
      const erro = new Error((dados && dados.detail) || `Erro ${resposta.status}`);
      erro.status = resposta.status;
      erro.dados = dados;
      throw erro;
    }
    return dados;
  },

  login(usuario, senha) {
    return this._requisicao("/auth/login", { metodo: "POST", corpo: { usuario, senha } });
  },
  criarConta(id, saldoInicial) {
    return this._requisicao("/contas", { metodo: "POST", corpo: { id, saldoInicial } });
  },
  saldo(id) {
    return this._requisicao(`/contas/${id}`);
  },
  extrato(id) {
    return this._requisicao(`/contas/${id}/extrato`);
  },
  // Health de uma agência específica (rota pública), para o Painel das Agências.
  async healthDe(agenciaId) {
    const url = `http://localhost:${Model.portaBase + agenciaId}/health`;
    const resposta = await fetch(url);
    if (!resposta.ok) throw new Error(`Agência ${agenciaId} indisponível`);
    return resposta.json();
  },
  depositar(id, valor) {
    return this._requisicao(`/contas/${id}/depositar`, { metodo: "POST", corpo: { valor } });
  },
  sacar(id, valor) {
    return this._requisicao(`/contas/${id}/sacar`, { metodo: "POST", corpo: { valor } });
  },
  transferir(idOrigem, idDestino, valor) {
    // Uma chave única por operação: se a requisição for reenviada, o backend
    // não aplica a transferência duas vezes (idempotência).
    return this._requisicao("/transferencias", {
      metodo: "POST",
      corpo: { idOrigem, idDestino, valor },
      idempotencyKey: crypto.randomUUID(),
    });
  },
};
