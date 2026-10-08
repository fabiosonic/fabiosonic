import { requirePageCtx } from "@/server/session";

/** Toda a área /admin exige perfil de administrador (verificado também em cada serviço/rota). */
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  await requirePageCtx(["ADMIN"]);
  return children;
}
