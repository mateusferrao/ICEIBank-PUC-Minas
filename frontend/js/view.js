// View (MVC): tudo que mexe no DOM, como mostrar telas, mensagens e resultados.
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

  // Monta um elemento com texto puro (textContent), sem interpretar HTML. Tudo que
  // vem da API passa por aqui para não abrir brecha de XSS.
  _no(tag, texto) {
    const no = document.createElement(tag);
    no.textContent = texto;
    return no;
  },

  mostrarSaldo(conta) {
    const alvo = this.el("resultado-saldo");
    alvo.replaceChildren(
      "Conta ",
      this._no("strong", conta.id),
      ` (dono: ${conta.dono || "-"}), saldo: `,
      this._no("strong", this.formatarReais(conta.saldo))
    );
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
      tr.append(
        this._no("td", `[${ev.timestampVetorial.join(", ")}]`),
        this._no("td", ev.tipo),
        this._no("td", JSON.stringify(ev.detalhes)),
        this._no("td", ev.horaParede)
      );
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
      const titulo = this._no("strong", `Agência ${l.agencia}`);
      if (l.ok) {
        div.append(
          titulo,
          document.createElement("br"),
          "Vetor: ",
          this._no("b", `[${l.vetor.join(", ")}]`),
          document.createElement("br"),
          `Contas: ${l.contas}`
        );
      } else {
        const fora = this._no("span", "fora do ar");
        fora.className = "off-txt";
        div.append(titulo, document.createElement("br"), fora);
      }
      alvo.appendChild(div);
    }
  },
};
