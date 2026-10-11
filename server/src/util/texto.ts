export const somenteDigitos = (s: string | null | undefined) => (s ?? '').replace(/\D/g, '');

export function cnpjValido(entrada: string): boolean {
  const c = somenteDigitos(entrada);
  if (c.length !== 14 || /^(\d)\1+$/.test(c)) return false;
  const calc = (base: string, pesos: number[]) => {
    const soma = base.split('').reduce((acc, d, i) => acc + Number(d) * pesos[i], 0);
    const resto = soma % 11;
    return resto < 2 ? 0 : 11 - resto;
  };
  const d1 = calc(c.slice(0, 12), [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
  const d2 = calc(c.slice(0, 12) + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
  return c.endsWith(`${d1}${d2}`);
}

export const formatarCnpj = (c: string) =>
  somenteDigitos(c).replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');

/** Normaliza telefone brasileiro para o formato E.164 sem "+" (ex.: 5511987654321). */
export function normalizarTelefone(entrada: string | null | undefined): string | null {
  let d = somenteDigitos(entrada);
  if (!d) return null;
  if (d.startsWith('0')) d = d.replace(/^0+/, '');
  if (!d.startsWith('55')) d = '55' + d;
  if (d.length < 12 || d.length > 13) return null;
  return d;
}

/** Celular brasileiro (nono dígito) — único tipo que pode ter WhatsApp com segurança razoável. */
export const ehCelular = (e164: string) => e164.length === 13 && e164[4] === '9';

export function normalizarEmail(entrada: string | null | undefined): string | null {
  const e = (entrada ?? '').trim().toLowerCase();
  return /^[^\s@]+@[^\s@]+\.[a-z]{2,}$/.test(e) ? e : null;
}

const PROVEDORES_PESSOAIS = ['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'yahoo.com.br', 'bol.com.br', 'uol.com.br', 'terra.com.br', 'live.com', 'icloud.com', 'msn.com', 'ig.com.br'];
export const dominioCorporativo = (email: string) => {
  const dominio = email.split('@')[1] ?? '';
  return PROVEDORES_PESSOAIS.includes(dominio) ? null : dominio;
};

/** E-mails de cadastro na Receita muitas vezes são do contador que abriu a empresa. */
export const pareceEmailDeContador = (email: string) =>
  /contab|contador|contabil|escritorio|assessoria|cont[aá]bil|fiscal/.test(email.split('@').join(' '));

/** Remove o histórico citado de uma resposta de e-mail, mantendo só o texto novo. */
export function textoNovoDaResposta(corpo: string): string {
  const linhas = corpo.replace(/\r/g, '').split('\n');
  const corte = linhas.findIndex(
    (l) =>
      /^>/.test(l.trim()) ||
      /^(Em|On) .+(escreveu|wrote):?$/i.test(l.trim()) ||
      /^-{2,}\s*(Mensagem original|Original Message)/i.test(l.trim()) ||
      /^(De|From):\s/.test(l.trim()),
  );
  return (corte >= 0 ? linhas.slice(0, corte) : linhas).join('\n').trim();
}

export const primeiroNome = (nome: string | null | undefined) => {
  const p = (nome ?? '').trim().split(/\s+/)[0] ?? '';
  return p ? p[0].toUpperCase() + p.slice(1).toLowerCase() : '';
};

export const tituloProprio = (s: string | null | undefined) =>
  (s ?? '')
    .toLowerCase()
    .replace(/(^|\s)(\p{L})/gu, (_, esp, l) => esp + l.toUpperCase())
    .replace(/\b(De|Da|Do|Das|Dos|E)\b/g, (m) => m.toLowerCase());

export const esperar = (ms: number) => new Promise((r) => setTimeout(r, ms));

export const escaparHtml = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
