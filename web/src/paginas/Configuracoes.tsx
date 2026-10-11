import { useEffect, useState, type ReactNode } from 'react';
import { AlertTriangle, ArrowDown, ArrowUp, CheckCircle2, CircleDashed, Plus, Save, Trash2 } from 'lucide-react';
import { api } from '../api';
import { Cabecalho } from '../componentes/Estrutura';
import { Abas, Botao, Campo, Cartao, Carregando, Selo, avisar, classeEntrada, cx, tempoRelativo, useDados } from '../componentes/ui';

type Aba = 'escritorio' | 'perfil' | 'cadencia' | 'autonomia' | 'ia' | 'integracoes' | 'bloqueios';
const linhas = (v: string) => v.split(/\n|,/).map((s) => s.trim()).filter(Boolean);

function Secao({ titulo, descricao, children }: { titulo: string; descricao?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid gap-4 border-b border-borda py-6 first:pt-2 last:border-0 lg:grid-cols-[280px_1fr]">
      <div>
        <h3 className="text-[14px] font-semibold">{titulo}</h3>
        {descricao && <p className="mt-1 text-[13px] text-tinta-3">{descricao}</p>}
      </div>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function ListaTexto({ valor, aoMudar, placeholder }: { valor: string[]; aoMudar: (v: string[]) => void; placeholder?: string }) {
  const [texto, setTexto] = useState(valor.join('\n'));
  useEffect(() => setTexto(valor.join('\n')), [valor.join('|')]);
  return <textarea className={classeEntrada + ' min-h-24'} value={texto} placeholder={placeholder} onChange={(e) => setTexto(e.target.value)} onBlur={() => aoMudar(linhas(texto))} />;
}

export function Configuracoes() {
  const { dados, carregando, recarregar } = useDados<any>('/api/configuracoes');
  const [aba, setAba] = useState<Aba>('escritorio');
  const [c, setC] = useState<any>(null);
  const [salvando, setSalvando] = useState(false);
  useEffect(() => {
    if (dados) setC(structuredClone(dados.configuracoes));
  }, [dados]);
  if ((carregando && !dados) || !c) return <Carregando />;

  const alterar = (caminho: string, valor: unknown) => {
    const novo = structuredClone(c);
    const partes = caminho.split('.');
    let alvo = novo;
    for (const p of partes.slice(0, -1)) alvo = alvo[p];
    alvo[partes.at(-1)!] = valor;
    setC(novo);
  };
  const alterado = JSON.stringify(c) !== JSON.stringify(dados.configuracoes);
  const salvar = async () => {
    setSalvando(true);
    try {
      await api('/api/configuracoes', { metodo: 'PUT', corpo: c });
      avisar('Configurações salvas');
      await recarregar();
    } catch (e) {
      avisar((e as Error).message, 'critico');
    } finally {
      setSalvando(false);
    }
  };
  const texto = (caminho: string, props: Record<string, unknown> = {}) => {
    const v = caminho.split('.').reduce((o: any, k) => o?.[k], c);
    return <input className={classeEntrada} value={v ?? ''} onChange={(e) => alterar(caminho, e.target.value)} {...props} />;
  };
  const numero = (caminho: string) => {
    const v = caminho.split('.').reduce((o: any, k) => o?.[k], c);
    return <input className={classeEntrada + ' numeros'} type="number" min={0} value={v ?? 0} onChange={(e) => alterar(caminho, Number(e.target.value))} />;
  };

  return (
    <div>
      <Cabecalho
        titulo="Configurações"
        descricao="Regras de negócio que os agentes seguem. Credenciais (SMTP, WhatsApp, chaves de IA) ficam no arquivo .env do servidor."
        acoes={
          <Botao variante="primario" disabled={!alterado} carregando={salvando} onClick={salvar}>
            <Save className="size-4" /> Salvar alterações
          </Botao>
        }
      />
      {dados.pendencias.length > 0 && (
        <div className="cartao mb-4 flex items-start gap-3 border-alerta/40 bg-alerta-suave/40 p-4 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-alerta-tinta" />
          <p>
            <span className="font-medium">Pendências antes de prospectar:</span> {dados.pendencias.join(', ')}. Sem identificação completa, os envios de prospecção ficam suspensos (NBC PG 01, item 4(r)).
          </p>
        </div>
      )}
      <div className="mb-4">
        <Abas
          abas={[
            { id: 'escritorio', rotulo: 'Escritório' },
            { id: 'perfil', rotulo: 'Cliente ideal' },
            { id: 'cadencia', rotulo: 'Cadência e limites' },
            { id: 'autonomia', rotulo: 'Autonomia' },
            { id: 'ia', rotulo: 'IA' },
            { id: 'integracoes', rotulo: 'Integrações' },
            { id: 'bloqueios', rotulo: 'Bloqueios' },
          ]}
          ativa={aba}
          aoMudar={setAba}
        />
      </div>
      <Cartao className="px-5">
        {aba === 'escritorio' && (
          <>
            <Secao titulo="Identificação" descricao="Aparece na assinatura de todas as mensagens. Não preencha com dados que você não possa comprovar.">
              <div className="grid gap-4 sm:grid-cols-2">
                <Campo rotulo="Nome do escritório">{texto('escritorio.nome')}</Campo>
                <Campo rotulo="Razão social">{texto('escritorio.razao_social')}</Campo>
                <Campo rotulo="CNPJ">{texto('escritorio.cnpj')}</Campo>
                <Campo rotulo="Registro CRC da organização">{texto('escritorio.crc_organizacao', { placeholder: 'Ex.: SP-000000/O-0' })}</Campo>
                <Campo rotulo="Responsável técnico">{texto('escritorio.responsavel_tecnico.nome')}</Campo>
                <Campo rotulo="CRC do responsável">{texto('escritorio.responsavel_tecnico.crc')}</Campo>
                <Campo rotulo="Categoria">{texto('escritorio.responsavel_tecnico.categoria')}</Campo>
                <Campo rotulo="Cidade">{texto('escritorio.cidade')}</Campo>
                <Campo rotulo="Telefone">{texto('escritorio.telefone')}</Campo>
                <Campo rotulo="Site">{texto('escritorio.site')}</Campo>
                <Campo rotulo="Linha da assinatura" ajuda="Ex.: Equipe comercial">{texto('escritorio.cargo_assinatura')}</Campo>
              </div>
            </Secao>
            <Secao titulo="Oferta" descricao="A IA só menciona o que estiver aqui. Diferenciais precisam ser comprováveis.">
              <Campo rotulo="Serviços comercializáveis (um por linha)">
                <ListaTexto valor={c.servicos} aoMudar={(v) => alterar('servicos', v)} placeholder={'Contabilidade para empresas do Simples Nacional\nAbertura de empresas\nDepartamento pessoal'} />
              </Campo>
              <Campo rotulo="Diferenciais comprovados (um por linha)">
                <ListaTexto valor={c.diferenciais_comprovados} aoMudar={(v) => alterar('diferenciais_comprovados', v)} placeholder="Ex.: atendimento por WhatsApp em horário comercial" />
              </Campo>
            </Secao>
          </>
        )}

        {aba === 'perfil' && (
          <>
            <Secao titulo="Onde buscar" descricao="Usado pela busca ativa nos Dados Abertos do CNPJ e na pontuação.">
              <div className="grid gap-4 sm:grid-cols-2">
                <Campo rotulo="UFs atendidas (uma por linha)" ajuda="Vazio = todo o Brasil">
                  <ListaTexto valor={c.perfil_cliente_ideal.ufs} aoMudar={(v) => alterar('perfil_cliente_ideal.ufs', v.map((u) => u.toUpperCase()))} placeholder="SP" />
                </Campo>
                <Campo rotulo="Municípios (um por linha)" ajuda="Vazio = todos das UFs">
                  <ListaTexto valor={c.perfil_cliente_ideal.municipios} aoMudar={(v) => alterar('perfil_cliente_ideal.municipios', v)} placeholder="Campinas" />
                </Campo>
                <Campo rotulo="CNAEs (prefixos, um por linha)" ajuda="Ex.: 47 (varejo), 6201 (software). Vazio = todos">
                  <ListaTexto valor={c.perfil_cliente_ideal.cnaes_prefixos} aoMudar={(v) => alterar('perfil_cliente_ideal.cnaes_prefixos', v)} />
                </Campo>
                <Campo rotulo="Empresas abertas há no máximo (dias)">{numero('perfil_cliente_ideal.abertura_max_dias')}</Campo>
              </div>
              <label className="flex items-center gap-2.5 text-sm">
                <input type="checkbox" checked={c.descoberta.receita_dados_abertos} onChange={(e) => alterar('descoberta.receita_dados_abertos', e.target.checked)} />
                Ativar busca ativa nos Dados Abertos do CNPJ (Receita Federal) a cada 12 horas
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <Campo rotulo="Máximo de empresas novas por busca">{numero('descoberta.max_novas_por_execucao')}</Campo>
                <Campo rotulo="Competência (AAAA-MM)" ajuda="Vazio = mais recente publicada">{texto('descoberta.competencia_rf', { placeholder: '2026-09' })}</Campo>
              </div>
            </Secao>
            <Secao titulo="Quem é cliente ideal" descricao="Leads abaixo da pontuação mínima são descartados com o motivo registrado.">
              <Campo rotulo="Segmentos prioritários">
                <div className="flex flex-wrap gap-2">
                  {dados.segmentos.map((s: string) => {
                    const ativo = c.perfil_cliente_ideal.segmentos.includes(s);
                    return (
                      <button
                        key={s}
                        type="button"
                        onClick={() => alterar('perfil_cliente_ideal.segmentos', ativo ? c.perfil_cliente_ideal.segmentos.filter((x: string) => x !== s) : [...c.perfil_cliente_ideal.segmentos, s])}
                        className={cx('rounded-full border px-3 py-1 text-[13px] transition', ativo ? 'border-acento bg-acento-suave text-acento-tinta' : 'border-borda-forte text-tinta-2 hover:bg-superficie-2')}
                      >
                        {s}
                      </button>
                    );
                  })}
                </div>
              </Campo>
              <div className="grid gap-4 sm:grid-cols-2">
                <Campo rotulo="Pontuação mínima para contato (0–100)">{numero('pontuacao_minima')}</Campo>
                <Campo rotulo="Capital social mínimo (R$)">{numero('perfil_cliente_ideal.capital_minimo')}</Campo>
              </div>
              <label className="flex items-center gap-2.5 text-sm">
                <input type="checkbox" checked={c.perfil_cliente_ideal.excluir_mei} onChange={(e) => alterar('perfil_cliente_ideal.excluir_mei', e.target.checked)} /> Excluir MEI
              </label>
            </Secao>
          </>
        )}

        {aba === 'cadencia' && (
          <>
            <Secao titulo="Cadência" descricao="Sequência de contatos até o lead responder. Para na primeira resposta ou pedido para parar.">
              <div className="space-y-2">
                {c.cadencia.map((p: any, i: number) => (
                  <div key={i} className="grid grid-cols-[auto_1fr_1fr_1fr_auto] items-center gap-2">
                    <span className="numeros w-6 text-[13px] text-tinta-3">{i + 1}</span>
                    <label className="flex items-center gap-1.5 text-[13px]">
                      Dia
                      <input type="number" min={0} className={classeEntrada + ' numeros'} value={p.dia} onChange={(e) => alterar(`cadencia.${i}.dia`, Number(e.target.value))} />
                    </label>
                    <select className={classeEntrada} value={p.canal} onChange={(e) => alterar(`cadencia.${i}.canal`, e.target.value)}>
                      <option value="email">E-mail</option>
                      <option value="whatsapp">WhatsApp</option>
                    </select>
                    <select className={classeEntrada} value={p.tipo} onChange={(e) => alterar(`cadencia.${i}.tipo`, e.target.value)}>
                      <option value="primeiro_contato">Primeiro contato</option>
                      <option value="lembrete">Lembrete</option>
                      <option value="acompanhamento">Acompanhamento</option>
                      <option value="ultimo_contato">Último contato</option>
                    </select>
                    <button
                      className="rounded-lg p-2 text-tinta-3 hover:bg-superficie-2"
                      aria-label="Remover passo"
                      onClick={() => alterar('cadencia', c.cadencia.filter((_: any, k: number) => k !== i).map((x: any, k: number) => ({ ...x, passo: k + 1 })))}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                ))}
                <Botao tamanho="sm" onClick={() => alterar('cadencia', [...c.cadencia, { passo: c.cadencia.length + 1, dia: (c.cadencia.at(-1)?.dia ?? 0) + 4, canal: 'email', tipo: 'acompanhamento' }])}>
                  <Plus className="size-3.5" /> Adicionar passo
                </Botao>
              </div>
            </Secao>
            <Secao titulo="Limites de envio" descricao="Protegem a reputação do domínio e do número. Comece baixo e aumente aos poucos.">
              <div className="grid gap-4 sm:grid-cols-2">
                <Campo rotulo="E-mails por dia">{numero('limites.emails_dia')}</Campo>
                <Campo rotulo="E-mails por hora">{numero('limites.emails_hora')}</Campo>
                <Campo rotulo="WhatsApp por dia">{numero('limites.whatsapp_dia')}</Campo>
                <Campo rotulo="Intervalo mínimo entre envios (segundos)">{numero('limites.intervalo_min_segundos')}</Campo>
              </div>
            </Secao>
            <Secao titulo="Horário de envio" descricao="Prospecção só sai nesse horário (fuso de Brasília). Respostas a quem escreveu saem entre 7h e 21h.">
              <div className="flex flex-wrap gap-2">
                {['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'].map((dia, i) => {
                  const ativo = c.horario_envio.dias_semana.includes(i);
                  return (
                    <button
                      key={dia}
                      type="button"
                      onClick={() => alterar('horario_envio.dias_semana', ativo ? c.horario_envio.dias_semana.filter((x: number) => x !== i) : [...c.horario_envio.dias_semana, i].sort())}
                      className={cx('h-9 w-12 rounded-lg border text-[13px]', ativo ? 'border-acento bg-acento-suave text-acento-tinta' : 'border-borda-forte text-tinta-2')}
                    >
                      {dia}
                    </button>
                  );
                })}
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Campo rotulo="Início">{texto('horario_envio.inicio', { type: 'time' })}</Campo>
                <Campo rotulo="Fim">{texto('horario_envio.fim', { type: 'time' })}</Campo>
              </div>
            </Secao>
          </>
        )}

        {aba === 'autonomia' && (
          <>
            <Secao titulo="Modo de operação" descricao="Recomendado: comece em aprovação, revise as primeiras dezenas de mensagens e só depois passe para automático.">
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  { id: 'aprovacao', titulo: 'Aprovação', texto: 'Os agentes escrevem e revisam; você aprova cada mensagem antes do envio.' },
                  { id: 'automatico', titulo: 'Automático', texto: 'Mensagens aprovadas pelo Revisor de Ética saem sozinhas. As reprovadas continuam vindo para você.' },
                ].map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => alterar('autonomia.modo', m.id)}
                    className={cx('rounded-2xl border p-4 text-left transition', c.autonomia.modo === m.id ? 'border-acento bg-acento-suave/60 ring-1 ring-acento' : 'border-borda-forte hover:bg-superficie-2')}
                  >
                    <p className="font-semibold">{m.titulo}</p>
                    <p className="mt-1 text-[13px] text-tinta-2">{m.texto}</p>
                  </button>
                ))}
              </div>
              <Campo rotulo="Respostas automáticas por conversa antes de chamar você" ajuda="Depois disso, o Atendente passa a conversa para você.">
                {numero('autonomia.max_turnos_automaticos')}
              </Campo>
              <label className="flex items-start gap-2.5 text-sm">
                <input type="checkbox" className="mt-1" checked={c.whatsapp.primeiro_contato_somente_optin} onChange={(e) => alterar('whatsapp.primeiro_contato_somente_optin', e.target.checked)} />
                <span>
                  Só iniciar conversa no WhatsApp com quem autorizou ou já conversou com o escritório
                  <span className="block text-[12px] text-tinta-3">Recomendado: reduz o risco de denúncia e banimento do número e atende melhor à LGPD. Os demais recebem e-mail.</span>
                </span>
              </label>
            </Secao>
            <Secao titulo="Quando o sistema chama você">
              <ul className="space-y-1.5 text-sm text-tinta-2">
                <li>• O lead pede para falar com uma pessoa ou pede ligação</li>
                <li>• O lead pergunta preço, valores ou orçamento</li>
                <li>• O lead traz dúvida técnica (tributária, fiscal, trabalhista)</li>
                <li>• O lead aceita reunião ou conversa</li>
                <li>• A conversa passa do limite de respostas automáticas ou a IA não entende</li>
              </ul>
            </Secao>
          </>
        )}

        {aba === 'ia' && (
          <>
            <Secao titulo="Ordem do rodízio" descricao="O primeiro disponível atende. Ao esgotar o crédito ou falhar, o próximo assume automaticamente.">
              <ol className="space-y-1.5">
                {c.ia.ordem_provedores.map((p: string, i: number) => (
                  <li key={p} className="flex items-center gap-2 rounded-xl border border-borda px-3 py-2">
                    <span className="numeros w-5 text-[13px] text-tinta-3">{i + 1}</span>
                    <span className="flex-1 text-sm font-medium">{p}</span>
                    <label className="flex items-center gap-1.5 text-[12px] text-tinta-3">
                      limite/dia
                      <input
                        type="number"
                        min={0}
                        className={classeEntrada + ' numeros h-8 w-20 py-1'}
                        value={c.ia.limites_diarios[p] ?? ''}
                        onChange={(e) => alterar(`ia.limites_diarios.${p}`, e.target.value ? Number(e.target.value) : undefined)}
                      />
                    </label>
                    <button disabled={i === 0} className="rounded p-1 text-tinta-3 hover:bg-superficie-2 disabled:opacity-30" aria-label="Subir" onClick={() => alterar('ia.ordem_provedores', trocar(c.ia.ordem_provedores, i, i - 1))}>
                      <ArrowUp className="size-4" />
                    </button>
                    <button disabled={i === c.ia.ordem_provedores.length - 1} className="rounded p-1 text-tinta-3 hover:bg-superficie-2 disabled:opacity-30" aria-label="Descer" onClick={() => alterar('ia.ordem_provedores', trocar(c.ia.ordem_provedores, i, i + 1))}>
                      <ArrowDown className="size-4" />
                    </button>
                  </li>
                ))}
              </ol>
            </Secao>
            <Secao titulo="Privacidade">
              <label className="flex items-start gap-2.5 text-sm">
                <input type="checkbox" className="mt-1" checked={c.ia.privacidade_estrita} onChange={(e) => alterar('ia.privacidade_estrita', e.target.checked)} />
                <span>
                  Privacidade estrita
                  <span className="block text-[12px] text-tinta-3">Tarefas com nomes de sócios e conversas só vão para provedores que não treinam com os dados (ou para o Ollama local). Recomendado pela LGPD.</span>
                </span>
              </label>
            </Secao>
          </>
        )}

        {aba === 'integracoes' && <Integracoes canais={dados.canais} urlPublica={dados.urlPublica} />}
        {aba === 'bloqueios' && <Bloqueios />}
      </Cartao>
    </div>
  );
}

const trocar = (lista: string[], a: number, b: number) => {
  const nova = [...lista];
  [nova[a], nova[b]] = [nova[b], nova[a]];
  return nova;
};

function Status({ ok, texto }: { ok: boolean; texto: string }) {
  return ok ? <Selo tom="bom" icone={<CheckCircle2 className="size-3.5" />}>{texto}</Selo> : <Selo icone={<CircleDashed className="size-3.5" />}>Não configurado</Selo>;
}

function Integracoes({ canais, urlPublica }: { canais: any; urlPublica: string }) {
  return (
    <>
      <Secao titulo="E-mail" descricao="SMTP para enviar e IMAP para ler respostas. Use um domínio com SPF, DKIM e DMARC configurados.">
        <div className="flex flex-wrap gap-2">
          <Status ok={canais.email} texto="SMTP ativo" />
          <Status ok={canais.imap} texto="IMAP ativo" />
        </div>
        <p className="text-[13px] text-tinta-2">
          Variáveis: <code>SMTP_HOST, SMTP_PORTA, SMTP_USUARIO, SMTP_SENHA, SMTP_REMETENTE, IMAP_HOST</code>
        </p>
      </Secao>
      <Secao titulo="WhatsApp" descricao="Recomendado: API oficial (WhatsApp Business Cloud). A Evolution API funciona com número comum, mas pode levar ao banimento.">
        <Status ok={canais.whatsapp} texto={`Ativo (${canais.whatsappProvedor === 'cloud' ? 'API oficial' : 'Evolution'})`} />
        <div className="space-y-1 text-[13px] text-tinta-2">
          <p>
            Webhook da API oficial: <code className="rounded bg-superficie-2 px-1">{urlPublica}/webhooks/whatsapp</code>
          </p>
          <p>
            Webhook da Evolution: <code className="rounded bg-superficie-2 px-1">{urlPublica}/webhooks/evolution?token=SEU_TOKEN</code>
          </p>
        </div>
      </Secao>
      <Secao titulo="Avisos para você" descricao="Para onde o sistema manda o aviso quando um lead quer falar com você.">
        <div className="flex flex-wrap gap-2">
          <Status ok={canais.avisoResponsavel.email} texto="E-mail do responsável" />
          <Status ok={canais.avisoResponsavel.whatsapp} texto="WhatsApp do responsável" />
        </div>
        <p className="text-[13px] text-tinta-2">
          Variáveis: <code>RESPONSAVEL_NOME, RESPONSAVEL_EMAIL, RESPONSAVEL_WHATSAPP</code>
        </p>
      </Secao>
      <Secao titulo="Formulário do site" descricao="Leads que chegam pelo site entram direto no funil, com consentimento registrado.">
        <pre className="overflow-x-auto rounded-xl bg-superficie-2 p-3 text-[12px] leading-relaxed">{`<form action="${urlPublica}/publico/lead" method="post">
  <input name="nome" required> <input name="email" type="email">
  <input name="whatsapp"> <input name="cnpj"> <textarea name="mensagem"></textarea>
  <input name="website" style="display:none"> <!-- isca anti-robô -->
  <label><input type="checkbox" name="consentimento" required>
    Aceito ser contatado pela Moraes & Oliveira</label>
  <button>Enviar</button>
</form>`}</pre>
      </Secao>
    </>
  );
}

function Bloqueios() {
  const { dados, recarregar } = useDados<any[]>('/api/bloqueios');
  const [valor, setValor] = useState('');
  return (
    <Secao titulo="Lista de bloqueio" descricao="Quem pediu para parar nunca mais recebe contato comercial. Os descadastros entram aqui automaticamente.">
      <form
        className="flex gap-2"
        onSubmit={async (e) => {
          e.preventDefault();
          await api('/api/bloqueios', { corpo: { valor } });
          setValor('');
          avisar('Contato bloqueado');
          void recarregar();
        }}
      >
        <input className={classeEntrada} placeholder="E-mail ou WhatsApp (5511999990000)" value={valor} onChange={(e) => setValor(e.target.value)} />
        <Botao type="submit" disabled={!valor.trim()}>
          Bloquear
        </Botao>
      </form>
      <ul className="max-h-96 divide-y divide-borda overflow-y-auto rounded-xl border border-borda rolagem-fina">
        {(dados ?? []).map((b) => (
          <li key={b.valor} className="flex items-center justify-between gap-3 px-3 py-2 text-[13px]">
            <span className="truncate font-medium">{b.valor}</span>
            <span className="shrink-0 text-tinta-3">
              {b.motivo} · {tempoRelativo(b.criado_em)}
            </span>
          </li>
        ))}
        {!dados?.length && <li className="px-3 py-6 text-center text-[13px] text-tinta-3">Nenhum bloqueio.</li>}
      </ul>
    </Secao>
  );
}
