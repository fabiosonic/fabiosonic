"use client";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="space-y-4">
      <Alert tone="error" title="Não foi possível carregar esta página.">
        Tente novamente. Se o problema persistir, informe o código {error.digest ?? "—"} ao suporte.
      </Alert>
      <Button onClick={reset}>Tentar novamente</Button>
    </div>
  );
}
