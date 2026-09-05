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

  // Alterna a aba visível e destaca o botão correspondente.
  trocarAba(painelId) {
    document.querySelectorAll(".aba").forEach((b) => {
      b.classList.toggle("ativa", b.dataset.painel === painelId);
    });
    ["painel-operacoes", "painel-transferencia", "painel-extrato", "painel-agencias"].forEach((id) => {
      this.el(id).hidden = id !== painelId;
    });
  },

  mostrarExtrato(eventos) {
    const corpo = this.el("tabela-extrato").querySelector("tbody");
    corpo.innerHTML = "";
    for (const ev of eventos) {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${ev.timestampLamport}</td><td>${ev.tipo}</td>` +
        `<td>${JSON.stringify(ev.detalhes)}</td><td>${ev.horaParede}</td>`;
      corpo.appendChild(tr);
    }
    this.el("tabela-extrato").hidden = eventos.length === 0;
  },

  mostrarPainelAgencias(linhas) {
    const alvo = this.el("cartoes-agencias");
    alvo.innerHTML = "";
    for (const l of linhas) {
      const div = document.createElement("div");
      div.className = "cartao-agencia " + (l.ok ? "ok" : "off");
      div.innerHTML = l.ok
        ? `<strong>Agência ${l.agencia}</strong><br>Lamport: <b>${l.lamport}</b><br>Contas: ${l.contas}`
        : `<strong>Agência ${l.agencia}</strong><br><span class="off-txt">fora do ar</span>`;
      alvo.appendChild(div);
    }
  },
};
