import { useState } from 'react';
import { Lock } from 'lucide-react';
import { api } from '../api';
import { Botao, classeEntrada } from '../componentes/ui';

export function Entrar({ requerSenha, aoEntrar }: { requerSenha: boolean; aoEntrar: () => void }) {
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <img src="/icone.svg" alt="" className="mb-4 size-12 rounded-2xl" />
          <h1 className="text-xl font-semibold tracking-tight">Central Comercial</h1>
          <p className="mt-1 text-sm text-tinta-3">Moraes & Oliveira Contabilidade</p>
        </div>
        {requerSenha ? (
          <form
            className="cartao space-y-4 p-6"
            onSubmit={async (e) => {
              e.preventDefault();
              setEnviando(true);
              setErro(null);
              try {
                await api('/api/entrar', { corpo: { senha } });
                aoEntrar();
              } catch (x) {
                setErro((x as Error).message);
              } finally {
                setEnviando(false);
              }
            }}
          >
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-tinta-2">Senha de acesso</span>
              <input type="password" autoFocus autoComplete="current-password" value={senha} onChange={(e) => setSenha(e.target.value)} className={classeEntrada} />
            </label>
            {erro && <p className="text-[13px] text-critico-tinta">{erro}</p>}
            <Botao variante="primario" className="w-full" carregando={enviando} type="submit">
              <Lock className="size-4" /> Entrar
            </Botao>
          </form>
        ) : (
          <div className="cartao p-6 text-sm text-tinta-2">
            <p className="font-medium text-tinta">Acesso restrito</p>
            <p className="mt-2">
              Defina <code className="rounded bg-superficie-2 px-1">SENHA_ADMIN</code> no arquivo <code className="rounded bg-superficie-2 px-1">.env</code> do servidor para acessar o painel
              por outro computador. Sem senha, o painel só abre no próprio servidor.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
