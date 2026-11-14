"""As etapas do ciclo: nichos -> busca -> qualificação + decisor -> material."""
from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import requests

from . import base as B
from . import site as S
from .llm import TXT, lista, objeto, perguntar

CONHECIMENTO = Path(__file__).parent / "conhecimento" / "dores-por-setor.md"
EXCLUIDOS = ("contabil", "contador", "advoca", "advogad", "juridic")


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


# ------------------------------------------------------------------ 1. nichos
SCHEMA_NICHOS = objeto({
    "resumo_escritorio": TXT,
    "nichos": lista(objeto({
        "setor": TXT,
        "subsetor": TXT,
        "por_que": TXT,                      # trecho do site que sustenta o nicho
        "sinais_de_ticket": lista(TXT),
        "termos_de_busca": lista(TXT),       # como esse negócio aparece no Google Maps
        "tem_dores_na_base": {"type": "boolean"},
    })),
})


def nichos(cfg: dict, pasta: str = "dados", ler_site=S.ler_site, ia=perguntar) -> dict:
    """Lê o site do escritório e devolve os nichos que ele de fato atende."""
    leitura = ler_site(cfg["escritorio"]["site"])
    if not leitura["vivo"]:
        raise SystemExit(f"Não consegui abrir {cfg['escritorio']['site']}. Confira o endereço em config.json.")
    sistema = (
        "Você é consultor comercial de um escritório de contabilidade brasileiro. A partir do texto do site "
        "do escritório, identifique os nichos de cliente que ele atende ou declara atender. Use somente o que "
        "o site afirma: serviços, setores citados, casos e depoimentos. Não invente nicho. Quando o site for "
        "genérico, diga isso no resumo e proponha os nichos de maior honorário compatíveis com os serviços "
        "listados (quem tem folha, estoque, retenção na fonte ou obrigação setorial), marcando em 'por_que' "
        "que é sugestão. Fora: MEI, contabilidades, advocacia e redes nacionais. Em 'termos_de_busca', "
        "escreva como esse tipo de empresa se descreve no Google Maps (ex.: 'laboratório de análises "
        "clínicas'), sem cidade. 'tem_dores_na_base' é verdadeiro quando o setor aparece na base de dores abaixo."
    )
    usuario = f"BASE DE DORES POR SETOR:\n{CONHECIMENTO.read_text(encoding='utf-8')}\n\nSITE DO ESCRITÓRIO:\n{S.texto_para_ia(leitura)}"
    out = ia(sistema, usuario, SCHEMA_NICHOS, cfg.get("modelo", "claude-opus-5-5"))
    Path(pasta, "nichos.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


# ------------------------------------------------------------------ 2. busca
CAMPOS_PLACES = ("places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,"
                 "places.googleMapsUri,places.primaryTypeDisplayName,places.userRatingCount,places.businessStatus,"
                 "nextPageToken")


def buscar_places(termo: str, cidade: str, maximo: int = 40, post=requests.post) -> list[dict]:
    """Google Places API oficial (Text Search). O telefone vem do Perfil da Empresa,
    que é publicado pela própria empresa — por isso vale como contato."""
    chave = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not chave:
        raise SystemExit("Defina GOOGLE_MAPS_API_KEY (Places API) ou use o comando 'importar' com um CSV.")
    achados, token = [], None
    while len(achados) < maximo:
        corpo = {"textQuery": f"{termo} em {cidade}", "languageCode": "pt-BR", "regionCode": "BR"}
        if token:
            corpo["pageToken"] = token
        r = post("https://places.googleapis.com/v1/places:searchText", json=corpo, timeout=30,
                 headers={"X-Goog-Api-Key": chave, "X-Goog-FieldMask": CAMPOS_PLACES})
        r.raise_for_status()
        dados = r.json()
        for p in dados.get("places", []):
            if p.get("businessStatus", "OPERATIONAL") != "OPERATIONAL":
                continue
            fone = p.get("nationalPhoneNumber", "")
            achados.append({
                "empresa": p.get("displayName", {}).get("text", ""),
                "municipio": cidade,
                "subsetor": p.get("primaryTypeDisplayName", {}).get("text", "") or termo,
                "site": p.get("websiteUri", ""),
                "whatsapp": B.so_digitos(fone) if B.eh_celular(fone) else "",
                "fonte_whatsapp": p.get("googleMapsUri", "") if B.eh_celular(fone) else "",
                "fonte_lead": p.get("googleMapsUri", ""),
                "observacao": f"{p.get('userRatingCount', 0)} avaliações no Google; {p.get('formattedAddress', '')}",
            })
        token = dados.get("nextPageToken")
        if not token:
            break
    return achados[:maximo]


def buscar(cfg: dict, base: B.Base, setor: str | None = None, maximo: int = 40, buscar_fn=buscar_places) -> dict:
    arq = base.pasta / "nichos.json"
    if not arq.exists():
        raise SystemExit("Rode 'nichos' antes de 'buscar'.")
    conta = {"entraram": 0, "descartes": {}}
    for nicho in json.loads(arq.read_text(encoding="utf-8"))["nichos"]:
        if setor and _sem_acento(setor) not in _sem_acento(nicho["setor"] + " " + nicho["subsetor"]):
            continue
        for termo in nicho["termos_de_busca"][:2]:
            for cidade in cfg["regiao"]:
                for achado in buscar_fn(termo, cidade, maximo):
                    achado["setor"] = nicho["setor"]
                    _entrar(base, achado, conta)
    base.salvar()
    return conta


def _entrar(base: B.Base, dados: dict, conta: dict) -> None:
    if any(x in _sem_acento(dados.get("empresa", "") + " " + dados.get("subsetor", "")) for x in EXCLUIDOS):
        motivo = "concorrente"
    else:
        _, motivo = base.adicionar(dados)
    if motivo == "ok":
        conta["entraram"] += 1
    else:
        conta["descartes"][motivo] = conta["descartes"].get(motivo, 0) + 1


# apelidos de coluna: cobre a saída do gosom/google-maps-scraper e planilhas comuns
APELIDOS = {
    "empresa": ("empresa", "title", "name", "nome"),
    "site": ("site", "website", "web_site"),
    "telefone": ("whatsapp", "phone", "telefone", "celular"),
    "subsetor": ("subsetor", "category", "categoria"),
    "municipio": ("municipio", "cidade", "city"),
    "fonte_lead": ("fonte_lead", "link", "url", "google_maps_url"),
    "setor": ("setor",),
}


def importar(base: B.Base, caminho: str, setor: str = "", municipio: str = "") -> dict:
    """Importa um CSV de leads (ex.: saída do gosom/google-maps-scraper)."""
    conta = {"entraram": 0, "descartes": {}}
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f):
            linha = {k.lower().strip(): (v or "").strip() for k, v in linha.items() if k}
            pega = lambda campo: next((linha[a] for a in APELIDOS[campo] if linha.get(a)), "")
            fone, fonte = pega("telefone"), pega("fonte_lead")
            if not fonte:
                conta["descartes"]["sem fonte"] = conta["descartes"].get("sem fonte", 0) + 1
                continue
            _entrar(base, {
                "empresa": pega("empresa"), "site": pega("site"), "subsetor": pega("subsetor"),
                "setor": pega("setor") or setor, "municipio": pega("municipio") or municipio,
                "whatsapp": B.so_digitos(fone) if B.eh_celular(fone) else "",
                "fonte_whatsapp": fonte if B.eh_celular(fone) else "", "fonte_lead": fonte,
            }, conta)
    base.salvar()
    return conta


# ------------------------------------------------- 3 e 4. qualificação + decisor
NIVEL_A = ("ceo", "president", "fundador", "socio", "proprietari", "dono", "diretor", "cfo", "titular")
NIVEL_B = ("controller", "gerente administrativ", "gerente financeir", "gerente geral", "gestor financeir")
NIVEL_C = ("coordenador administrativ", "coordenador financeir", "coordenadora administrativ", "coordenadora financeir")
FORA = ("rh", "recursos humanos", "recrut", "comercial", "vendas", "marketing", "analista", "assistente",
        "estagi", "tecnic", "motorista", "atendente", "recepcion")


def nivel_decisor(cargo: str) -> str:
    """A = decide sozinho; B = influencia; C = porta de entrada; '' = não é decisor.
    Quem acumula cargo excluído e é sócio continua sendo decisor."""
    c = _sem_acento(cargo)
    tem = lambda termos: any(re.search(rf"\b{re.escape(t)}", c) for t in termos)
    if tem(("socio", "proprietari", "fundador", "dono")):
        return "A"
    if tem(FORA):
        return ""
    return "A" if tem(NIVEL_A) else "B" if tem(NIVEL_B) else "C" if tem(NIVEL_C) else ""


SCHEMA_QUALI = objeto({
    "ativa": {"type": "boolean"},
    "rede_nacional": {"type": "boolean"},
    "subsetor": TXT,
    "porte": TXT,
    "sinais": lista(objeto({"sinal": TXT, "evidencia": TXT, "url": TXT})),
    "ticket": {"type": "string", "enum": ["alto", "medio", "baixo"]},
    "pessoas": lista(objeto({"nome": TXT, "cargo": TXT, "url": TXT})),
    "motivo_descarte": TXT,
})

SISTEMA_QUALI = (
    "Você qualifica empresas como possíveis clientes de um escritório de contabilidade no Brasil, lendo "
    "apenas o texto do site da própria empresa. Regras:\n"
    "- 'sinais' são os sinais de honorário maior que o site comprova: folha relevante, estoque/revenda, "
    "retenção na fonte (atende convênio, PJ ou poder público), obrigação setorial (Anvisa, ANTT, MEC...), "
    "mais de uma unidade, operação interestadual. Cada sinal traz o trecho do site e a URL da página. Sem "
    "trecho que comprove, o sinal não entra.\n"
    "- 'ticket': alto = folha relevante + retenções ou obrigação setorial, ou mais de uma unidade; medio = "
    "tem folha ou estoque; baixo = serviço sem folha aparente.\n"
    "- 'rede_nacional' = marca com presença em vários estados ou franqueadora nacional.\n"
    "- 'pessoas': somente quem o site nomeia com cargo (página Equipe, Quem somos, Diretoria). Copie nome e "
    "cargo como estão, com a URL. Não deduza cargo, não complete sobrenome, não inclua dado pessoal.\n"
    "- 'motivo_descarte' fica vazio quando a empresa serve; senão um destes: 'rede nacional', 'MEI', "
    "'concorrente', 'site fora do ar', 'sem sinal de ticket'."
)


def qualificar(cfg: dict, base: B.Base, limite: int = 25, ler_site=S.ler_site, ia=perguntar) -> dict:
    conta = {"qualificados": 0, "descartados": 0}
    for lead in [l for l in base.leads if l["status"] == B.NOVO][:limite]:
        leitura = ler_site(lead["site"])
        # contato: o botão de WhatsApp do site vale mais que o telefone do Perfil do Google
        for campo in ("whatsapp", "email"):
            if leitura.get(campo):
                lead[campo], lead["fonte_" + campo] = leitura[campo], leitura["fonte_" + campo]
        for rede in ("instagram", "linkedin"):
            lead[rede] = lead[rede] or leitura.get(rede, "")
        if not leitura["vivo"]:
            motivo = "site fora do ar" if lead["site"] else "sem site para comprovar a operação"
        elif not B.eh_celular(lead["whatsapp"]):
            motivo = "sem WhatsApp publicado pela empresa"
        else:
            q = ia(SISTEMA_QUALI, f"EMPRESA: {lead['empresa']} ({lead['municipio']})\n\n{S.texto_para_ia(leitura)}",
                   SCHEMA_QUALI, cfg.get("modelo", "claude-opus-5-5"))
            motivo = q["motivo_descarte"] or ("rede nacional" if q["rede_nacional"] else "" if q["ativa"] else "site fora do ar")
            lead.update(subsetor=q["subsetor"] or lead["subsetor"], porte=q["porte"], ticket=q["ticket"],
                        sinais=json.dumps(q["sinais"], ensure_ascii=False))
            decisores = sorted(((nivel_decisor(p["cargo"]), p) for p in q["pessoas"] if nivel_decisor(p["cargo"])),
                               key=lambda t: t[0])
            if decisores:
                nivel, p = decisores[0]
                lead.update(decisor_nome=p["nome"], decisor_cargo=p["cargo"], decisor_nivel=nivel, decisor_fonte=p["url"])
            if lead["linkedin"]:  # consulta manual: a aba Pessoas filtra por cargo pela URL
                lead["decisor_linkedin"] = lead["linkedin"].rstrip("/") + "/people/?keywords=s%C3%B3cio%20OR%20diretor"
            canais = sum(bool(lead[c]) for c in ("whatsapp", "email", "instagram", "linkedin"))
            lead["prioridade"] = ("A" if lead["ticket"] == "alto" and canais >= 2 else
                                  "B" if lead["ticket"] == "alto" or (lead["ticket"] == "medio" and canais >= 2) else "C")
        if motivo:
            lead["status"], lead["observacao"] = B.DESCARTADO, f"descartado: {motivo}. {lead['observacao']}".strip()
            conta["descartados"] += 1
        else:
            lead["status"] = B.QUALIFICADO
            conta["qualificados"] += 1
        base.salvar()
    return conta


# ------------------------------------------------------------------ 5. material
SCHEMA_MATERIAL = objeto({
    "dores": lista(objeto({"dor": TXT, "por_que_nesta_empresa": TXT})),
    "gancho": TXT,
    "o_que_vimos": TXT,
    "a_conta": TXT,
    "evidencias": lista(objeto({"fato": TXT, "url": TXT})),
})

SISTEMA_MATERIAL = (
    "Você prepara o material de abordagem de um escritório de contabilidade para UMA empresa específica. "
    "A mensagem vai para o WhatsApp comercial que a empresa publicou e será lida por um dono de negócio.\n\n"
    "Entregue:\n"
    "- 'dores': 2 ou 3 dores tributárias/contábeis prováveis, cada uma ligada a um sinal comprovado da empresa.\n"
    "- 'gancho': a norma que sustenta a dor principal, copiada da BASE DE DORES. Só cite norma que esteja "
    "na base. Se nenhuma servir, deixe vazio.\n"
    "- 'o_que_vimos': uma frase começando por 'Vimos' com um detalhe verificável que só existe nessa "
    "empresa (unidades e bairros, serviço específico, convênios, frota). Se a frase servir para outra "
    "empresa do setor, está errada. Use apenas fatos presentes no texto do site, sem arredondar número.\n"
    "- 'a_conta': 2 a 3 frases com a dor principal em linguagem de dono ('o convênio retém 11% e isso "
    "some no meio do ano'), citando a norma do gancho quando houver, com a ressalva que a norma exige.\n"
    "- 'evidencias': cada fato usado em 'o_que_vimos', com a URL da página.\n\n"
    "Proibido em qualquer campo de texto: preço ou honorário; promessa de resultado ou de economia; "
    "recuperação, restituição ou ressarcimento de valores; oferta de análise, diagnóstico, conferência ou "
    "revisão dos dados da empresa; as palavras 'gratuito' e 'sem compromisso'; menção ao contador atual ou "
    "comparação com outro profissional (NBC PG 01); emoji, exclamação e gíria. O escritório fala no plural "
    "('vimos', 'conduzimos') e trata a empresa por 'vocês'. Não escreva saudação, apresentação, convite "
    "nem assinatura: o sistema acrescenta."
)

PROIBIDOS = {
    "trabalho gratuito": r"gratuit|gr[áa]tis|sem compromisso|diagn[óo]stic|15 minutos|sem custo|"
                         r"\b(conferimos|analisamos|revisamos|olhamos|levantamos)\b|a gente confere",
    "recuperação de crédito": r"recupera|restitui|ressarci|recolhido a maior",
    "preço ou promessa": r"R\$|honor[áa]rio|economiz|vai pagar menos|garant|reduzir (seus|os) impostos",
    "ataque ao colega": r"seu contador|contador atual|contabilidade atual|outro escrit[óo]rio",
    "tom de venda": r"!|\bOi\b|[\U0001F300-\U0001FAFF☀-➿]",
    "norma revogada": r"CPC\s*17|NBC\s*TG\s*17",
}
NORMA_RE = re.compile(r"(?:Lei(?: Complementar)?|LC|CPC|NBC TG|Resolução CGSN)\s*(?:n[ºo.]*\s*)?(\d[\d.]*)", re.I)


def normas_conhecidas() -> set[str]:
    return {n.replace(".", "") for n in NORMA_RE.findall(CONHECIMENTO.read_text(encoding="utf-8"))}


def revisar(lead: dict, outros: list[str] = ()) -> list[str]:
    """Checklist determinístico do texto. Lista vazia = pode ir para a fila."""
    texto = f"{lead['o_que_vimos']} {lead['a_conta']}"
    alertas = [nome for nome, padrao in PROIBIDOS.items() if re.search(padrao, texto, re.I)]
    desconhecidas = {n for n in NORMA_RE.findall(texto) if n.replace(".", "") not in normas_conhecidas()}
    if desconhecidas:
        alertas.append("norma fora da base conferida: " + ", ".join(sorted(desconhecidas)))
    if not lead["o_que_vimos"].strip().lower().startswith("vimos"):
        alertas.append("bloco 'o que vimos' não começa por 'Vimos'")
    if not json.loads(lead["evidencias"] or "[]"):
        alertas.append("sem evidência com URL para o que vimos")
    if len(texto) > 650:
        alertas.append("texto longo para WhatsApp")
    if any(SequenceMatcher(None, lead["o_que_vimos"], o).ratio() > 0.75 for o in outros):
        alertas.append("'o que vimos' parecido com o de outra empresa do lote")
    return alertas


def material(cfg: dict, base: B.Base, limite: int = 25, ler_site=S.ler_site, ia=perguntar) -> dict:
    conta = {"prontos": 0, "com_alerta": 0}
    conhecimento = CONHECIMENTO.read_text(encoding="utf-8")
    for lead in [l for l in base.leads if l["status"] == B.QUALIFICADO][:limite]:
        leitura = ler_site(lead["site"])
        usuario = (f"BASE DE DORES POR SETOR (normas já conferidas):\n{conhecimento}\n\n"
                   f"EMPRESA: {lead['empresa']} — {lead['subsetor']} — {lead['municipio']}\n"
                   f"SINAIS COMPROVADOS: {lead['sinais']}\n\nSITE DA EMPRESA:\n{S.texto_para_ia(leitura)}")
        m = ia(SISTEMA_MATERIAL, usuario, SCHEMA_MATERIAL, cfg.get("modelo", "claude-opus-5-5"))
        lead.update(dor=json.dumps(m["dores"], ensure_ascii=False), gancho=m["gancho"],
                    o_que_vimos=m["o_que_vimos"].strip(), a_conta=m["a_conta"].strip(),
                    evidencias=json.dumps(m["evidencias"], ensure_ascii=False), texto_versao="v1")
        outros = [l["o_que_vimos"] for l in base.leads if l is not lead and l["o_que_vimos"]]
        alertas = revisar(lead, outros)
        lead["alertas"] = "; ".join(alertas)
        if alertas:
            conta["com_alerta"] += 1          # fica em 'qualificado' até alguém corrigir e rodar 'revisar'
        else:
            lead["status"] = B.PRONTO
            conta["prontos"] += 1
        base.salvar()
    return conta
