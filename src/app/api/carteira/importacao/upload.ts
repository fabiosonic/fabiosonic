import "server-only";
import { AppError } from "@/server/errors";
import { CSV_MAX_BYTES } from "@/lib/csv-positions";

/** Lê o arquivo CSV enviado (multipart), com limite de tamanho e verificação de tipo. */
export async function readCsvUpload(req: Request) {
  const len = Number(req.headers.get("content-length") ?? 0);
  if (len > CSV_MAX_BYTES + 64 * 1024) throw new AppError("VALIDATION", "Arquivo acima do limite de 512 KB.", { file: ["Arquivo muito grande."] });
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    throw new AppError("BAD_REQUEST", "Envio inválido.");
  }
  const file = form.get("file");
  if (!(file instanceof File)) throw new AppError("VALIDATION", "Selecione um arquivo CSV.", { file: ["Arquivo obrigatório."] });
  if (file.size > CSV_MAX_BYTES) throw new AppError("VALIDATION", "Arquivo acima do limite de 512 KB.", { file: ["Arquivo muito grande."] });
  const allowed = ["text/csv", "application/vnd.ms-excel", "text/plain", ""];
  if (!allowed.includes(file.type)) throw new AppError("VALIDATION", "Tipo de arquivo não suportado.", { file: ["Envie um .csv."] });
  return { fileName: file.name, text: await file.text() };
}
