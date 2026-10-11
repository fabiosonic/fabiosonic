// Classificação de segmento pela divisão CNAE (2 primeiros dígitos), alinhada ao
// roteiro "segmentos.md" da equipe comercial.
const FAIXAS: [number, number, string][] = [
  [1, 3, 'Agronegócio'],
  [5, 9, 'Financeiro regulado, energia e mineração'],
  [10, 33, 'Indústria'],
  [35, 35, 'Financeiro regulado, energia e mineração'],
  [36, 39, 'Serviços profissionais e tecnologia'],
  [41, 43, 'Construção e imobiliário'],
  [45, 45, 'Alimentação, hospedagem e automotivo'],
  [46, 47, 'Comércio e e-commerce'],
  [49, 53, 'Transporte e logística'],
  [55, 56, 'Alimentação, hospedagem e automotivo'],
  [58, 63, 'Serviços profissionais e tecnologia'],
  [64, 66, 'Financeiro regulado, energia e mineração'],
  [68, 68, 'Construção e imobiliário'],
  [69, 82, 'Serviços profissionais e tecnologia'],
  [85, 85, 'Educação e terceiro setor'],
  [86, 88, 'Saúde'],
  [90, 93, 'Serviços profissionais e tecnologia'],
  [94, 94, 'Educação e terceiro setor'],
  [95, 96, 'Serviços profissionais e tecnologia'],
];

export function segmentoPorCnae(cnae: string | null | undefined): string {
  const d = (cnae ?? '').replace(/\D/g, '');
  if (d.length < 2) return 'Ramo ainda não mapeado';
  const divisao = Number(d.slice(0, 2));
  if (d.startsWith('4791') || d.startsWith('47913')) return 'Comércio e e-commerce';
  return FAIXAS.find(([a, b]) => divisao >= a && divisao <= b)?.[2] ?? 'Ramo ainda não mapeado';
}

export const SEGMENTOS = [
  'Comércio e e-commerce',
  'Indústria',
  'Serviços profissionais e tecnologia',
  'Saúde',
  'Construção e imobiliário',
  'Agronegócio',
  'Transporte e logística',
  'Alimentação, hospedagem e automotivo',
  'Educação e terceiro setor',
  'Financeiro regulado, energia e mineração',
  'Ramo ainda não mapeado',
];
