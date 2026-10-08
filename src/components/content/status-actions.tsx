import { ActionButton } from "@/components/ui/action-button";

/** Ações de publicação/arquivamento conforme a situação atual. */
export function StatusActions({ base, status, noun }: { base: string; status: "DRAFT" | "PUBLISHED" | "ARCHIVED"; noun: string }) {
  return (
    <>
      {status === "DRAFT" && (
        <ActionButton
          url={`${base}/situacao`}
          body={{ action: "publish" }}
          variant="primary"
          size="md"
          confirm={{ title: `Publicar ${noun}?`, description: "O conteúdo ficará visível para todos os usuários e eles serão notificados." }}
          confirmLabel="Publicar"
        >
          Publicar
        </ActionButton>
      )}
      {status !== "ARCHIVED" && (
        <ActionButton
          url={`${base}/situacao`}
          body={{ action: "archive" }}
          variant="secondary"
          size="md"
          confirm={{ title: `Arquivar ${noun}?`, description: "O conteúdo deixará de ser exibido aos usuários." }}
          confirmLabel="Arquivar"
        >
          Arquivar
        </ActionButton>
      )}
      {status === "ARCHIVED" && (
        <ActionButton url={`${base}/situacao`} body={{ action: "unarchive" }} variant="secondary" size="md">
          Reativar como rascunho
        </ActionButton>
      )}
    </>
  );
}
