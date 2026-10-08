import {
  Archive,
  CheckCircle2,
  CircleDashed,
  CircleDot,
  Clock,
  FileEdit,
  FlaskConical,
  Loader2,
  MessageSquareReply,
  PlugZap,
  Unplug,
  XCircle,
  Lock,
  Radio,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "./cn";
import {
  CONNECTION_STATUS_LABEL,
  CONTENT_STATUS_LABEL,
  DATA_SOURCE_LABEL,
  REQUEST_STATUS_LABEL,
  SYNC_STATUS_LABEL,
} from "@/lib/labels";

type Tone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

const tones: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-200",
  brand: "bg-brand-50 text-brand-800 ring-brand-100",
  success: "bg-gain-50 text-gain-700 ring-emerald-200",
  warning: "bg-amber-50 text-amber-900 ring-amber-200",
  danger: "bg-loss-50 text-loss-700 ring-red-200",
  info: "bg-sky-50 text-sky-900 ring-sky-200",
};

/** Selo com ícone + texto (o significado nunca depende apenas da cor). */
export function Badge({ tone = "neutral", icon: Icon, children, className, title }: { tone?: Tone; icon?: LucideIcon; children: ReactNode; className?: string; title?: string }) {
  return (
    <span title={title} className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap", tones[tone], className)}>
      {Icon && <Icon className="size-3.5" aria-hidden="true" />}
      {children}
    </span>
  );
}

export function ContentStatusBadge({ status }: { status: keyof typeof CONTENT_STATUS_LABEL }) {
  const map = { DRAFT: ["warning", FileEdit], PUBLISHED: ["success", CheckCircle2], ARCHIVED: ["neutral", Archive] } as const;
  const [tone, icon] = map[status];
  return <Badge tone={tone} icon={icon}>{CONTENT_STATUS_LABEL[status]}</Badge>;
}

export function RequestStatusBadge({ status }: { status: keyof typeof REQUEST_STATUS_LABEL }) {
  const map = { OPEN: ["info", CircleDot], IN_ANALYSIS: ["warning", Clock], ANSWERED: ["success", MessageSquareReply], CLOSED: ["neutral", Lock] } as const;
  const [tone, icon] = map[status];
  return <Badge tone={tone} icon={icon}>{REQUEST_STATUS_LABEL[status]}</Badge>;
}

export function ConnectionBadge({ status }: { status: keyof typeof CONNECTION_STATUS_LABEL }) {
  const map = { DISCONNECTED: ["neutral", Unplug], CONNECTED: ["success", PlugZap], SYNCING: ["info", Loader2], ERROR: ["danger", XCircle] } as const;
  const [tone, icon] = map[status];
  return <Badge tone={tone} icon={icon}>{CONNECTION_STATUS_LABEL[status]}</Badge>;
}

export function SyncBadge({ status }: { status: keyof typeof SYNC_STATUS_LABEL }) {
  const map = { RUNNING: ["info", Loader2], SUCCESS: ["success", CheckCircle2], ERROR: ["danger", XCircle] } as const;
  const [tone, icon] = map[status];
  return <Badge tone={tone} icon={icon}>{SYNC_STATUS_LABEL[status]}</Badge>;
}

/** Identifica a natureza do dado: demonstrativo, atrasado ou em tempo real. */
export function DataSourceBadge({ source }: { source: keyof typeof DATA_SOURCE_LABEL }) {
  const map = { DEMO: ["warning", FlaskConical], DELAYED: ["info", Clock], REALTIME: ["success", Radio] } as const;
  const [tone, icon] = map[source];
  return (
    <Badge tone={tone} icon={icon} title={source === "DEMO" ? "Dados fictícios para demonstração; não use para decisões reais." : undefined}>
      {DATA_SOURCE_LABEL[source]}
    </Badge>
  );
}

export function PendingBadge({ children }: { children: ReactNode }) {
  return <Badge tone="neutral" icon={CircleDashed}>{children}</Badge>;
}
