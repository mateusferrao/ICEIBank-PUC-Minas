// Controller (MVC): liga os eventos da View às chamadas da Api e atualiza o
// Model. É a "cola" — a View não fala com a Api diretamente.
const Controller = {
  iniciar() {
    // Restaura a sessão (se houver token guardado) ao abrir a página.
    View.mostrarApp(Model.logado());
    View.preencherCabecalho(Model.usuario, Model.agencia);

    View.el("form-login").addEventListener("submit", (e) => this.aoLogar(e));
    View.el("btn-sair").addEventListener("click", () => this.aoSair());
    View.el("seletor-agencia").addEventListener("change", (e) => this.aoTrocarAgencia(e));
    View.el("form-criar").addEventListener("submit", (e) => this.aoCriarConta(e));
    View.el("form-saldo").addEventListener("submit", (e) => this.aoConsultarSaldo(e));
    View.el("form-deposito").addEventListener("submit", (e) => this.aoDepositar(e));
    View.el("form-saque").addEventListener("submit", (e) => this.aoSacar(e));
    View.el("form-transferencia").addEventListener("submit", (e) => this.aoTransferir(e));
  },

  // Trata erros de forma visível; 401 encerra a sessão (token expirado/ausente).
  _tratarErro(elId, erro) {
    if (erro.status === 401) {
      Model.encerrarSessao();
      View.mostrarApp(false);
      View.mensagem("msg-login", "Sessão expirada ou inválida. Faça login novamente.", "erro");
      return;
    }
    View.mensagem(elId, erro.message, "erro");
  },

  async aoLogar(e) {
    e.preventDefault();
    View.limparMensagem("msg-login");
    const usuario = View.el("login-usuario").value.trim();
    const senha = View.el("login-senha").value;
    try {
      const dados = await Api.login(usuario, senha);
      Model.token = dados.token;
      Model.usuario = dados.usuario;
      View.mostrarApp(true);
      View.preencherCabecalho(Model.usuario, Model.agencia);
    } catch (erro) {
      View.mensagem("msg-login", erro.message, "erro");
    }
  },

  aoSair() {
    Model.encerrarSessao();
    View.mostrarApp(false);
    View.mensagem("msg-login", "Você saiu.", "info");
  },

  aoTrocarAgencia(e) {
    Model.agencia = parseInt(e.target.value, 10);
    View.preencherCabecalho(Model.usuario, Model.agencia);
    View.mensagem("msg-operacoes", `Porta de entrada agora é a Agência ${Model.agencia}.`, "info");
  },

  async aoCriarConta(e) {
    e.preventDefault();
    const id = parseInt(View.el("criar-id").value, 10);
    const saldo = parseFloat(View.el("criar-saldo").value || "0");
    try {
      const conta = await Api.criarConta(id, saldo);
      View.mensagem("msg-operacoes", `Conta ${conta.id} criada (saldo ${View.formatarReais(conta.saldo)}).`, "sucesso");
    } catch (erro) {
      this._tratarErro("msg-operacoes", erro);
    }
  },

  async aoConsultarSaldo(e) {
    e.preventDefault();
    const id = parseInt(View.el("saldo-id").value, 10);
    try {
      const conta = await Api.saldo(id);
      View.mostrarSaldo(conta);
      View.limparMensagem("msg-operacoes");
    } catch (erro) {
      View.el("resultado-saldo").textContent = "";
      this._tratarErro("msg-operacoes", erro);
    }
  },

  async aoDepositar(e) {
    e.preventDefault();
    const id = parseInt(View.el("deposito-id").value, 10);
    const valor = parseFloat(View.el("deposito-valor").value);
    try {
      const conta = await Api.depositar(id, valor);
      View.mensagem("msg-operacoes", `Depósito ok. Novo saldo da conta ${id}: ${View.formatarReais(conta.saldo)}.`, "sucesso");
    } catch (erro) {
      this._tratarErro("msg-operacoes", erro);
    }
  },

  async aoSacar(e) {
    e.preventDefault();
    const id = parseInt(View.el("saque-id").value, 10);
    const valor = parseFloat(View.el("saque-valor").value);
    try {
      const conta = await Api.sacar(id, valor);
      View.mensagem("msg-operacoes", `Saque ok. Novo saldo da conta ${id}: ${View.formatarReais(conta.saldo)}.`, "sucesso");
    } catch (erro) {
      this._tratarErro("msg-operacoes", erro);
    }
  },

  async aoTransferir(e) {
    e.preventDefault();
    const idOrigem = parseInt(View.el("transf-origem").value, 10);
    const idDestino = parseInt(View.el("transf-destino").value, 10);
    const valor = parseFloat(View.el("transf-valor").value);
    try {
      // O frontend NÃO precisa saber se é local ou entre agências — o backend
      // resolve; a mensagem retornada deixa claro qual foi.
      const resultado = await Api.transferir(idOrigem, idDestino, valor);
      View.mensagem("msg-transferencia", resultado.mensagem, "sucesso");
    } catch (erro) {
      this._tratarErro("msg-transferencia", erro);
    }
  },
};

window.addEventListener("DOMContentLoaded", () => Controller.iniciar());
