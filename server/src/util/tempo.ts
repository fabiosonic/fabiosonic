// Datas são gravadas em UTC no formato do SQLite ("YYYY-MM-DD HH:MM:SS").
// A janela de envio é avaliada no fuso de Brasília.
const FUSO = 'America/Sao_Paulo';

export const agoraSql = (d = new Date()) => d.toISOString().slice(0, 19).replace('T', ' ');
export const daquiSql = (ms: number) => agoraSql(new Date(Date.now() + ms));
export const DIA_MS = 86_400_000;

export function horaLocal(d = new Date()) {
  const partes = new Intl.DateTimeFormat('pt-BR', {
    timeZone: FUSO,
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(d);
  const pegar = (t: string) => partes.find((p) => p.type === t)?.value ?? '';
  const dias: Record<string, number> = { dom: 0, seg: 1, ter: 2, qua: 3, qui: 4, sex: 5, sáb: 6 };
  const semana = dias[pegar('weekday').replace('.', '').toLowerCase()] ?? 1;
  return { semana, minutos: Number(pegar('hour')) * 60 + Number(pegar('minute')) };
}

const paraMinutos = (hhmm: string) => {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + (m || 0);
};

export function dentroDaJanela(janela: { dias_semana: number[]; inicio: string; fim: string }, d = new Date()) {
  const { semana, minutos } = horaLocal(d);
  return janela.dias_semana.includes(semana) && minutos >= paraMinutos(janela.inicio) && minutos < paraMinutos(janela.fim);
}

export const dataLocalIso = (d = new Date()) =>
  new Intl.DateTimeFormat('en-CA', { timeZone: FUSO, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d);
