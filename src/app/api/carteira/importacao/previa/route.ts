import { route } from "@/server/api";
import { previewImport } from "@/server/services/portfolio";
import { readCsvUpload } from "../upload";

export const POST = route(async ({ req, ctx }) => {
  const { fileName, text } = await readCsvUpload(req);
  return previewImport(ctx, fileName, text);
});
