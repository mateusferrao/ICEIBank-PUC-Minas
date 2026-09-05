// View (MVC): tudo que toca o DOM — mostrar telas, mensagens e resultados.
// Não conhece a API nem as regras; só recebe dados e renderiza.
const View = {
  el(id) {
    return document.getElementById(id);
  },

  formatarReais(valor) {
    return valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  },

  // Alterna entre a tela de login e a tela principal.
  mostrarApp(logado) {
    this.el("tela-login").hidden = logado;
    this.el("tela-app").hidden = !logado;
  },

  preencherCabecalho(usuario, agencia) {
    this.el("info-usuario").textContent = usuario ? `Usuário: ${usuario}` : "";
    this.el("seletor-agencia").value = String(agencia);
    this.el("info-agencia").textContent = `Agência ${agencia} (porta ${Model.portaBase + agencia})`;
  },

  // Mensagens visíveis para quem usa a tela (sucesso ou erro).
  mensagem(elId, texto, tipo = "info") {
    const alvo = this.el(elId);
    alvo.textContent = texto;
    alvo.className = `mensagem ${tipo}`;
  },

  limparMensagem(elId) {
    const alvo = this.el(elId);
    alvo.textContent = "";
    alvo.className = "mensagem";
  },

  mostrarSaldo(conta) {
    this.el("resultado-saldo").innerHTML =
      `Conta <strong>${conta.id}</strong> (dono: ${conta.dono || "-"}) — ` +
      `saldo: <strong>${this.formatarReais(conta.saldo)}</strong>`;
  },
};
