/*
 * Dados institucionais do escritório.
 * Fonte: site atual moraeseoliveiracontabil.com.br (lido em out/2026).
 * Tudo que estiver vazio ("") ou null fica oculto no site — nada é inventado.
 * Preencha somente com informações reais e verificáveis (NBC PG 01, item 13).
 */
window.SITE_CONFIG = {
  nome: "Moraes & Oliveira Contabilidade",
  nomeCurto: "Moraes & Oliveira",
  fundacao: 2015,

  cidade: "Itaboraí – RJ",

  // Somente dígitos, com DDI e DDD.
  whatsapp: "5521998806423",
  telefone: "(21) 99880-6423",
  email: "moraes@moraeseoliveiracontabil.com.br",
  endereco: "Av. Vinte e Dois de Maio, 4845, Sala 908 – Rio Várzea, Itaboraí/RJ – CEP 24812-086",
  mapa: "https://www.google.com/maps/search/?api=1&query=Av.+Vinte+e+Dois+de+Maio,+4845,+Itabora%C3%AD+RJ",

  // Ex.: { dias: [1,2,3,4,5], abre: "08:00", fecha: "18:00" } (0 = domingo). null = oculta o status "online agora".
  horario: null,

  razaoSocial: "",
  cnpj: "24.875.410/0001-44",
  crcEscritorio: "CRC-RJ 007873/O",
  responsavelTecnico: "",
  crcResponsavel: "",

  // Avaliações públicas no Google (widget Trustindex do site atual).
  google: { nota: "5,0", total: 31, link: "" },

  areaDoCliente: "", // URL do app/portal do cliente, se houver

  redes: {
    instagram: "https://www.instagram.com/moraeseoliveira.contabilidade",
    linkedin: "https://www.linkedin.com/company/moraes-e-oliveira-contabilidade/",
    facebook: "https://www.facebook.com/moraeseoliveira.cont/"
  },

  /*
   * Envio de leads. Se vazio, o formulário abre o WhatsApp com a mensagem pronta.
   * Para também gravar os leads, aponte para um endpoint que aceite POST JSON
   * (ex.: webhook do n8n, Formspree, API própria). Nunca coloque chaves secretas aqui.
   */
  leadEndpoint: "",

  // Tag de conversão do Google Ads já usada no site atual. Só carrega após o consentimento.
  googleAdsId: "AW-17474728938"
};
