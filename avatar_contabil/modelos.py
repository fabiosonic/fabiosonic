"""Estruturas de dados do pipeline."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Pauta(BaseModel):
    id: str
    titulo: str
    resumo: str = ""
    link: str
    fonte: str
    publicado_em: Optional[str] = None


class AvaliacaoPauta(BaseModel):
    indice: int = Field(description="Índice da pauta na lista recebida")
    nota: int = Field(description="Relevância de 0 a 10 para o público do escritório")
    motivo: str


class Triagem(BaseModel):
    avaliacoes: List[AvaliacaoPauta]


class Roteiro(BaseModel):
    titulo: str = Field(description="Título curto do vídeo, até 70 caracteres")
    gancho: str = Field(description="Primeira frase, prende a atenção em até 3 segundos")
    corpo: str = Field(description="Explicação em linguagem simples")
    pergunta_final: str = Field(description="Pergunta que convida a comentar")
    cta: str = Field(description="Chamada para ação usada só na versão do Instagram")
    texto_narrado: str = Field(description="Texto completo que o avatar fala: gancho + corpo + pergunta_final")
    base_legal: List[str] = Field(description="Normas citadas (lei, IN, resolução). Vazio se a fonte não informar")
    pontos_a_verificar: List[str] = Field(description="O que o contador revisor precisa conferir antes de aprovar")
    legenda_post: str = Field(description="Texto da descrição do post")
    hashtags: List[str]
