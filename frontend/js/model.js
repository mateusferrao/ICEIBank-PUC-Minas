// Model (MVC): estado da aplicação e persistência do token.
// Guarda token/usuário/agência no localStorage para "lembrar" a sessão entre
// requisições e recarregamentos da página.
const Model = {
  _CHAVE_TOKEN: "iceibank_token",
  _CHAVE_USUARIO: "iceibank_usuario",
  _CHAVE_AGENCIA: "iceibank_agencia",

  // Porta base das agências (4000 + id). Ajuste aqui se usar OFFSET no backend.
  portaBase: 4000,

  get token() {
    return localStorage.getItem(this._CHAVE_TOKEN);
  },
  set token(valor) {
    if (valor) localStorage.setItem(this._CHAVE_TOKEN, valor);
    else localStorage.removeItem(this._CHAVE_TOKEN);
  },

  get usuario() {
    return localStorage.getItem(this._CHAVE_USUARIO);
  },
  set usuario(valor) {
    if (valor) localStorage.setItem(this._CHAVE_USUARIO, valor);
    else localStorage.removeItem(this._CHAVE_USUARIO);
  },

  get agencia() {
    return parseInt(localStorage.getItem(this._CHAVE_AGENCIA) || "0", 10);
  },
  set agencia(valor) {
    localStorage.setItem(this._CHAVE_AGENCIA, String(valor));
  },

  // URL da agência escolhida como "porta de entrada" deste acesso.
  baseUrl() {
    return `http://localhost:${this.portaBase + this.agencia}`;
  },

  logado() {
    return Boolean(this.token);
  },

  encerrarSessao() {
    this.token = null;
    this.usuario = null;
  },
};
