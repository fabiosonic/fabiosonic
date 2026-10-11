/*
 * Dados institucionais do escritório.
 * Tudo que estiver vazio ("") ou null fica oculto no site — nada é inventado.
 * Preencha somente com informações reais e verificáveis (NBC PG 01, item 13).
 */
window.SITE_CONFIG = {
  nome: "Moraes & Oliveira Contabilidade",
  nomeCurto: "Moraes & Oliveira",

  // Confirmar cidade/endereço com o escritório.
  cidade: "",
  atendimentoOnline: false, // true exibe "atendimento online em todo o Brasil"
  parceiroContaAzul: false,

  // Somente dígitos, com DDI e DDD. Ex.: "5521999999999". Vazio = botões levam ao formulário.
  whatsapp: "",
  telefone: "",
  email: "",
  endereco: "",

  // Ex.: { dias: [1,2,3,4,5], abre: "08:00", fecha: "18:00" } (0 = domingo). null = oculta o status "online agora".
  horario: null,
  horarioTexto: "",

  razaoSocial: "",
  cnpj: "",
  crcEscritorio: "",
  responsavelTecnico: "",
  crcResponsavel: "",

  areaDoCliente: "", // URL do portal real, se existir

  redes: {
    instagram: "",
    linkedin: "",
    facebook: ""
  },

  /*
   * Envio de leads. Se vazio, o formulário abre o WhatsApp com a mensagem pronta
   * (ou o e-mail, se não houver WhatsApp). Para gravar os leads, aponte para um
   * endpoint que aceite POST JSON (ex.: Formspree, n8n webhook, API própria).
   * Nunca coloque chaves secretas aqui: este arquivo é público.
   */
  leadEndpoint: ""
};
