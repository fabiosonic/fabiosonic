"""Chamadas ao Claude: conteúdo, nota explicável e marca a partir do site."""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import List

from pydantic import BaseModel, Field

from avatar_contabil import config

from .db import Pauta, Perfil

MODELO = "claude-opus-5-5"

ESTILOS = {
    "problema_solucao": "Problema → Solução: apresente a dor do empresário e mostre o caminho.",
    "mito_verdade": "Mito × Verdade: desfaça crenças comuns, uma por slide.",
    "passo_a_passo": "Passo a passo: o que fazer, em ordem, de forma prática.",
    "checklist": "Checklist: itens que o empresário deve conferir.",
    "antes_depois": "Antes × Depois: como era a regra e como fica.",
    "noticia": "Notícia explicada: o que mudou, quem é afetado, o que fazer.",
}

SISTEMA = """Você cria conteúdo para redes sociais de escritórios de contabilidade brasileiros.
Todo conteúdo passa por revisão de um contador com CRC antes de ser publicado.

Regras que não podem ser quebradas:
- Afirme apenas o que está na pauta. Se faltar dado (data, alíquota, número da norma), não invente:
  escreva de forma genérica e registre a dúvida em pontos_a_verificar.
- Publicidade sóbria e informativa (Código de Ética do contador, NBC PG 01): sem promessa de
  resultado, economia garantida, sensacionalismo, comparação com concorrentes, preço ou incentivo
  a evasão fiscal.
- Português do Brasil, linguagem simples, falando com o empresário ("você").
- Não dê consultoria individual; reforce que cada caso precisa de análise."""


class Slide(BaseModel):
    titulo: str = Field(description="Até 8 palavras")
    texto: str = Field(description="Até 30 palavras")


class ConteudoGerado(BaseModel):
    titulo: str = Field(description="Título interno, até 70 caracteres")
    gancho: str = Field(description="Primeira frase, prende a atenção em até 3 segundos")
    legenda: str = Field(description="Texto da legenda do post, sem hashtags")
    cta: str = Field(description="Chamada para ação sóbria")
    hashtags: List[str]
    slides: List[Slide] = Field(description="Carrossel: 5 a 8 slides. Post: 1 slide. Vídeo: lista vazia")
    texto_narrado: str = Field(description="Vídeo: texto falado completo (gancho + explicação + pergunta). Outros: vazio")
    base_legal: List[str] = Field(description="Normas citadas na pauta; vazio se a pauta não informar")
    pontos_a_verificar: List[str] = Field(description="O que o contador revisor precisa conferir")


class Eixo(BaseModel):
    nome: str
    nota: int = Field(description="0 a 20")
    comentario: str


class Nota(BaseModel):
    eixos: List[Eixo] = Field(description="Exatamente: Gancho, Clareza, Valor prático, Urgência, Conformidade")
    sugestoes: List[str] = Field(description="Até 3 melhorias concretas")


class MarcaSugerida(BaseModel):
    nome: str
    tom: str = Field(description="Tom de voz em uma frase")
    publico: str = Field(description="Público-alvo em uma frase")
    servicos: List[str]
    nunca_dizer: List[str] = Field(description="Expressões que essa marca deve evitar")


def _chamar(prompt: str, formato, esforco: str):
    import anthropic

    resp = anthropic.Anthropic().beta.messages.parse(
        model=MODELO,
        max_tokens=16000,
        system=SISTEMA,
        messages=[{"role": "user", "content": prompt}],
        output_format=formato,
        output_config={"effort": esforco},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("O modelo recusou a solicitação; revise a pauta.")
    return resp.parsed_output


def _perfil_txt(p: Perfil) -> str:
    return (
        f"Marca: {p.nome} ({'o próprio escritório contábil' if p.tipo == 'escritorio' else 'cliente PME do escritório'})\n"
        f"Tom de voz: {p.tom}\nPúblico: {p.publico}\nServiços: {p.servicos or '-'}\n"
        f"Nunca dizer: {', '.join(p.termos_proibidos()) or '-'}"
    )


def gerar(perfil: Perfil, pauta: Pauta, formato: str, estilo: str, instrucao: str = "", base: dict | None = None) -> ConteudoGerado:
    if config.dry_run():
        return _exemplo(perfil, pauta, formato)
    pedido = {
        "post": "um post de imagem única (1 slide com a mensagem principal) e legenda",
        "carrossel": "um carrossel de 5 a 8 slides: o 1º é a capa com o gancho, o último fecha com a chamada para ação",
        "video": "o roteiro de um vídeo vertical de 35 a 50 segundos (no máximo 120 palavras em texto_narrado), "
                 "falado pelo avatar do contador; termine com uma pergunta para gerar comentários",
    }[formato]
    prompt = (
        f"{_perfil_txt(perfil)}\n\nCrie {pedido}.\nEstilo narrativo: {ESTILOS.get(estilo, ESTILOS['noticia'])}\n"
        f"{('Instrução extra do redator: ' + instrucao) if instrucao else ''}\n\n"
        f"Pauta:\n{json.dumps(pauta.model_dump(include={'origem', 'titulo', 'resumo', 'link', 'data_ref'}), ensure_ascii=False)}"
    )
    if base:
        prompt += (
            "\n\nAdapte este conteúdo já aprovado para a marca acima, mantendo os fatos e mudando "
            f"tom, exemplos e chamada:\n{json.dumps(base, ensure_ascii=False)}"
        )
    return _chamar(prompt, ConteudoGerado, "high")


def avaliar(perfil: Perfil, formato: str, dados: dict) -> dict:
    """Nota explicável de 0 a 100 em 5 eixos de 0 a 20."""
    if config.dry_run():
        nota = Nota(
            eixos=[Eixo(nome=n, nota=15, comentario="Avaliação de exemplo (modo de teste).")
                   for n in ("Gancho", "Clareza", "Valor prático", "Urgência", "Conformidade")],
            sugestoes=["Conecte o gancho a um prazo concreto, se houver na fonte."],
        )
    else:
        prompt = (
            f"{_perfil_txt(perfil)}\n\nAvalie este conteúdo ({formato}) para o público da marca. "
            "Dê de 0 a 20 em cada eixo:\n"
            "- Gancho: a primeira frase faz parar de rolar a tela?\n"
            "- Clareza: um empresário sem formação contábil entende?\n"
            "- Valor prático: diz o que fazer?\n"
            "- Urgência: há prazo, mudança de regra ou risco real (sem alarmismo)?\n"
            "- Conformidade: respeita a NBC PG 01, não promete resultado, não afirma o que não está na fonte?\n"
            "Seja exigente: 20 só para excelente.\n\n"
            f"Conteúdo:\n{json.dumps(dados, ensure_ascii=False)}"
        )
        nota = _chamar(prompt, Nota, "low")
    eixos = [e.model_dump() | {"nota": max(0, min(20, e.nota))} for e in nota.eixos]
    return {"total": sum(e["nota"] for e in eixos), "eixos": eixos, "sugestoes": nota.sugestoes}


def marca_do_site(url: str) -> tuple[MarcaSugerida, list[str]]:
    """Lê a página pública e sugere tom, público, serviços e cores."""
    import requests

    if not re.match(r"^https?://", url):
        url = "https://" + url
    html = requests.get(url, timeout=20, headers={"User-Agent": "StudioContabil/1.0"}).text
    cores = cores_do_html(html)
    texto = re.sub(r"\s+", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", " ", html, flags=re.S | re.I))[:12000]
    if config.dry_run():
        titulo = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        return MarcaSugerida(
            nome=(titulo.group(1).strip() if titulo else url)[:80],
            tom="Profissional, próximo e didático.", publico="Donos de pequenas e médias empresas.",
            servicos=[], nunca_dizer=[],
        ), cores
    prompt = (
        "Com base no texto do site abaixo, descreva a marca para orientar a criação de posts. "
        "Não invente serviços que não aparecem no texto.\n\n" + texto
    )
    return _chamar(prompt, MarcaSugerida, "low"), cores


def cores_do_html(html: str, limite: int = 3) -> list[str]:
    """Cores mais frequentes no HTML/CSS, ignorando branco, preto e cinzas."""
    tema = re.findall(r'name=["\']theme-color["\']\s+content=["\'](#[0-9a-fA-F]{6})', html)
    achadas = [c.upper() for c in re.findall(r"#[0-9a-fA-F]{6}\b", html)]

    def colorida(c: str) -> bool:
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        return max(r, g, b) - min(r, g, b) > 40

    ordem = [c.upper() for c in tema] + [c for c, _ in Counter(achadas).most_common() if colorida(c)]
    return list(dict.fromkeys(ordem))[:limite]


def _exemplo(perfil: Perfil, pauta: Pauta, formato: str) -> ConteudoGerado:
    gancho = f"Atenção, {perfil.publico.split(',')[0].lower().rstrip('.')}: isso pode afetar você."
    slides = []
    if formato == "carrossel":
        slides = [Slide(titulo=pauta.titulo[:60], texto=gancho)] + [
            Slide(titulo=f"Ponto {i} (exemplo)", texto=pauta.resumo or pauta.titulo) for i in range(1, 4)
        ] + [Slide(titulo="Fale com a gente", texto=f"Dúvidas? A equipe {perfil.nome} ajuda você a analisar o seu caso.")]
    elif formato == "post":
        slides = [Slide(titulo=pauta.titulo[:60], texto=gancho)]
    narrado = f"{gancho} {pauta.titulo}. {pauta.resumo} Você já sabia disso? Conta aqui nos comentários." if formato == "video" else ""
    return ConteudoGerado(
        titulo=pauta.titulo[:70].strip(), gancho=gancho,
        legenda=f"{pauta.titulo}\n\n{pauta.resumo}".strip(),
        cta=f"Fale com a equipe {perfil.nome} para analisar o seu caso.",
        hashtags=["contabilidade", "empresas", "impostos"],
        slides=slides, texto_narrado=narrado, base_legal=[],
        pontos_a_verificar=["Conteúdo de exemplo gerado em modo de teste (DRY_RUN=1)."],
    )
