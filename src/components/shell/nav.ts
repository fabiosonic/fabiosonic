import {
  Bell,
  Calculator,
  CalendarClock,
  CalendarDays,
  CandlestickChart,
  FileText,
  GraduationCap,
  LayoutDashboard,
  ListChecks,
  MessageSquare,
  ScrollText,
  Settings2,
  Users,
  Wallet,
  BarChart3,
  type LucideIcon,
} from "lucide-react";

export type RoleKey = "ADMIN" | "ANALYST" | "USER";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  roles?: RoleKey[];
}

export const NAV_SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "Visão geral",
    items: [
      { href: "/painel", label: "Painel", icon: LayoutDashboard },
      { href: "/carteira", label: "Carteira", icon: Wallet },
    ],
  },
  {
    title: "Mercado e simulação",
    items: [
      { href: "/mercado", label: "Mercado", icon: CandlestickChart },
      { href: "/opcoes-diarias", label: "Opções diárias", icon: CalendarClock },
      { href: "/simulador", label: "Simulador (boletas)", icon: Calculator },
    ],
  },
  {
    title: "Conteúdo",
    items: [
      { href: "/operacoes", label: "Operações prontas", icon: ListChecks },
      { href: "/analises", label: "Análises", icon: FileText },
      { href: "/cursos", label: "Cursos", icon: GraduationCap },
      { href: "/agenda", label: "Lives e aulas", icon: CalendarDays },
      { href: "/solicitacoes", label: "Pedidos de análise", icon: MessageSquare },
      { href: "/notificacoes", label: "Notificações", icon: Bell },
    ],
  },
  {
    title: "Administração",
    items: [
      { href: "/admin", label: "Indicadores", icon: BarChart3, roles: ["ADMIN"] },
      { href: "/admin/usuarios", label: "Usuários", icon: Users, roles: ["ADMIN"] },
      { href: "/admin/cursos", label: "Gestão de cursos", icon: Settings2, roles: ["ADMIN"] },
      { href: "/admin/agenda", label: "Gestão da agenda", icon: CalendarDays, roles: ["ADMIN"] },
      { href: "/admin/auditoria", label: "Auditoria", icon: ScrollText, roles: ["ADMIN"] },
    ],
  },
];
