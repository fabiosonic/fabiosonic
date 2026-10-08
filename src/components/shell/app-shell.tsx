"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { FlaskConical, LogOut, Menu, X } from "lucide-react";
import { authClient } from "@/lib/auth-client";
import { ROLE_LABEL } from "@/lib/labels";
import { cn } from "@/components/ui/cn";
import { NAV_SECTIONS, type RoleKey } from "./nav";

interface ShellUser {
  name: string;
  email: string;
  role: RoleKey;
}

function NavLinks({ role, unread, onNavigate }: { role: RoleKey; unread: number; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Navegação principal" className="space-y-5">
      {NAV_SECTIONS.map((section) => {
        const items = section.items.filter((i) => !i.roles || i.roles.includes(role));
        if (!items.length) return null;
        return (
          <div key={section.title}>
            <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{section.title}</p>
            <ul className="space-y-0.5">
              {items.map((item) => {
                const active = item.href === "/admin" ? pathname === "/admin" : pathname === item.href || pathname.startsWith(`${item.href}/`);
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm",
                        active ? "bg-brand-50 font-semibold text-brand-800" : "text-slate-700 hover:bg-slate-100",
                      )}
                    >
                      <Icon className="size-4 shrink-0" aria-hidden="true" />
                      <span className="flex-1">{item.label}</span>
                      {item.href === "/notificacoes" && unread > 0 && (
                        <span className="rounded-full bg-brand-700 px-1.5 text-[11px] font-semibold text-white" aria-label={`${unread} não lidas`}>
                          {unread > 99 ? "99+" : unread}
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

function UserBox({ user }: { user: ShellUser }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  async function logout() {
    setBusy(true);
    await authClient.signOut();
    router.push("/login");
    router.refresh();
  }
  return (
    <div className="border-t border-slate-200 p-3">
      <p className="truncate text-sm font-medium text-slate-900">{user.name}</p>
      <p className="truncate text-xs text-slate-500">
        {user.email} · {ROLE_LABEL[user.role]}
      </p>
      <button
        type="button"
        onClick={logout}
        disabled={busy}
        className="mt-2 inline-flex w-full items-center justify-center gap-2 rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-60"
      >
        <LogOut className="size-4" aria-hidden="true" /> {busy ? "Saindo…" : "Sair"}
      </button>
    </div>
  );
}

function Brand() {
  return (
    <Link href="/painel" className="flex items-center gap-2 px-3 py-4 font-semibold text-slate-900">
      <svg viewBox="0 0 32 32" className="size-7" aria-hidden="true">
        <rect width="32" height="32" rx="7" fill="#0b5763" />
        <path d="M7 21l6-6 4 4 8-9" stroke="#fff" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      Opções Lab
    </Link>
  );
}

export function AppShell({ user, unread, demo, children }: { user: ShellUser; unread: number; demo: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[16rem_1fr]">
      <a href="#conteudo" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Pular para o conteúdo
      </a>

      {/* Barra lateral (desktop) */}
      <aside className="sticky top-0 hidden h-dvh flex-col border-r border-slate-200 bg-white lg:flex">
        <Brand />
        <div className="flex-1 overflow-y-auto px-2 pb-4">
          <NavLinks role={user.role} unread={unread} />
        </div>
        <UserBox user={user} />
      </aside>

      {/* Cabeçalho (celular/tablet) */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white px-2 lg:hidden">
        <Brand />
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="inline-flex size-10 items-center justify-center rounded-md text-slate-700 hover:bg-slate-100"
          aria-label="Abrir menu"
          aria-expanded={open}
          aria-controls="menu-movel"
        >
          <Menu className="size-5" aria-hidden="true" />
          {unread > 0 && <span className="sr-only">{unread} notificações não lidas</span>}
        </button>
      </header>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu" id="menu-movel">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setOpen(false)} aria-hidden="true" />
          <div className="absolute inset-y-0 left-0 flex w-[min(18rem,85vw)] flex-col bg-white shadow-xl">
            <div className="flex items-center justify-between pr-2">
              <Brand />
              <button ref={closeRef} type="button" onClick={() => setOpen(false)} className="inline-flex size-10 items-center justify-center rounded-md hover:bg-slate-100" aria-label="Fechar menu">
                <X className="size-5" aria-hidden="true" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-2 pb-4">
              <NavLinks role={user.role} unread={unread} onNavigate={() => setOpen(false)} />
            </div>
            <UserBox user={user} />
          </div>
        </div>
      )}

      <div className="min-w-0">
        {demo && (
          <div className="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-xs text-amber-900" role="note">
            <FlaskConical className="size-3.5 shrink-0" aria-hidden="true" />
            <span>
              <strong>Ambiente demonstrativo:</strong> dados fictícios, conexão B3 simulada e nenhuma ordem real é enviada. Conteúdo educacional, não é recomendação de investimento.
            </span>
          </div>
        )}
        <main id="conteudo" className="mx-auto w-full max-w-7xl px-4 py-5 sm:px-6 lg:py-7">
          {children}
        </main>
      </div>
    </div>
  );
}
