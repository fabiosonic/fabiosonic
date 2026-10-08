import { requirePageCtx } from "@/server/session";
import { unreadCount } from "@/server/services/notifications";
import { isDemoEnv } from "@/server/env";
import { AppShell } from "@/components/shell/app-shell";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const ctx = await requirePageCtx();
  const unread = await unreadCount(ctx);
  return (
    <AppShell user={{ name: ctx.actor.name, email: ctx.actor.email, role: ctx.actor.role }} unread={unread} demo={isDemoEnv()}>
      {children}
    </AppShell>
  );
}
