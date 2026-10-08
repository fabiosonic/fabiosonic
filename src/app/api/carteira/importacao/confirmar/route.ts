import { route } from "@/server/api";
import { confirmImport } from "@/server/services/portfolio";
import { readCsvUpload } from "../upload";

export const POST = route(async ({ req, ctx }) => {
  const { fileName, text } = await readCsvUpload(req);
  return confirmImport(ctx, fileName, text);
});
