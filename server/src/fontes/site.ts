// Leitura do site institucional da empresa (dado público publicado pela própria
// empresa). Respeita robots.txt, lê no máximo 3 páginas e só guarda e-mails
// corporativos do próprio domínio.
let fetchImpl: typeof fetch = (...a) => fetch(...a);
export const definirFetchSite = (f: typeof fetch) => (fetchImpl = f);

const AGENTE = 'CentralComercialBot/1.0 (+contato comercial)';

export function htmlParaTexto(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<noscript[\s\S]*?<\/noscript>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/\s+/g, ' ')
    .trim();
}

export function extrairEmails(html: string, dominio: string): string[] {
  const achados = html.match(/[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/gi) ?? [];
  const base = dominio.replace(/^www\./, '');
  return [...new Set(achados.map((e) => e.toLowerCase()))].filter((e) => e.endsWith('@' + base) || e.endsWith('.' + base)).slice(0, 5);
}

export function extrairRedes(html: string) {
  const redes: Record<string, string> = {};
  for (const [rede, padrao] of [
    ['instagram', /https?:\/\/(www\.)?instagram\.com\/[a-z0-9_.]+/i],
    ['linkedin', /https?:\/\/(www\.)?linkedin\.com\/company\/[a-z0-9-_%]+/i],
    ['facebook', /https?:\/\/(www\.)?facebook\.com\/[a-z0-9.]+/i],
  ] as const) {
    const m = html.match(padrao);
    if (m) redes[rede] = m[0];
  }
  return redes;
}

async function permitidoPeloRobots(origem: string): Promise<boolean> {
  try {
    const r = await fetchImpl(`${origem}/robots.txt`, { headers: { 'user-agent': AGENTE }, signal: AbortSignal.timeout(8000) });
    if (!r.ok) return true;
    const texto = await r.text();
    let aplica = false;
    for (const linha of texto.split('\n').map((l) => l.trim().toLowerCase())) {
      if (linha.startsWith('user-agent:')) aplica = linha.includes('*') || linha.includes('centralcomercial');
      else if (aplica && linha === 'disallow: /') return false;
    }
    return true;
  } catch {
    return true;
  }
}

export type LeituraSite = { url: string; titulo: string; descricao: string; texto: string; emails: string[]; redes: Record<string, string> };

export async function lerSite(endereco: string): Promise<LeituraSite | null> {
  const url = endereco.startsWith('http') ? endereco : `https://${endereco}`;
  let origem: string;
  try {
    origem = new URL(url).origin;
  } catch {
    return null;
  }
  if (!(await permitidoPeloRobots(origem))) return null;

  const paginas = [origem, `${origem}/sobre`, `${origem}/contato`];
  let htmlTotal = '';
  let titulo = '';
  let descricao = '';
  for (const pagina of paginas) {
    try {
      const r = await fetchImpl(pagina, { headers: { 'user-agent': AGENTE, accept: 'text/html' }, redirect: 'follow', signal: AbortSignal.timeout(12000) });
      if (!r.ok || !(r.headers.get('content-type') ?? '').includes('html')) continue;
      const html = (await r.text()).slice(0, 400_000);
      if (!titulo) titulo = htmlParaTexto(html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1] ?? '');
      if (!descricao) descricao = html.match(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)/i)?.[1] ?? '';
      htmlTotal += '\n' + html;
    } catch {
      /* página indisponível: segue para a próxima */
    }
  }
  if (!htmlTotal) return null;
  const dominio = new URL(origem).hostname;
  return {
    url: origem,
    titulo,
    descricao,
    texto: htmlParaTexto(htmlTotal).slice(0, 6000),
    emails: extrairEmails(htmlTotal, dominio),
    redes: extrairRedes(htmlTotal),
  };
}
