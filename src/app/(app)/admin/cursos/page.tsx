import Link from "next/link";
import { requirePageCtx } from "@/server/session";
import { listCourses } from "@/server/services/courses";
import { PageHeader, Panel } from "@/components/ui/panel";
import { ContentStatusBadge } from "@/components/ui/badge";
import { Table, Td, Th } from "@/components/ui/table";
import { CourseForm } from "./course-forms";

export const metadata = { title: "Gestão de cursos" };

export default async function AdminCoursesPage() {
  const ctx = await requirePageCtx(["ADMIN"]);
  const courses = await listCourses(ctx);
  return (
    <>
      <PageHeader title="Gestão de cursos" description="Cursos, módulos e aulas. Use apenas conteúdo original ou links autorizados." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2" title="Cursos">
          <Table caption="Cursos">
            <thead>
              <tr>
                <Th>Título</Th>
                <Th>Situação</Th>
                <Th className="text-right">Módulos</Th>
                <Th className="text-right">Aulas</Th>
              </tr>
            </thead>
            <tbody>
              {courses.map((c) => (
                <tr key={c.id}>
                  <Td>
                    <Link href={`/admin/cursos/${c.id}`} className="font-medium text-brand-700 underline">
                      {c.title}
                    </Link>
                  </Td>
                  <Td>
                    <ContentStatusBadge status={c.status} />
                  </Td>
                  <Td className="text-right">{c.modules}</Td>
                  <Td className="text-right">{c.lessons}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Panel>
        <CourseForm />
      </div>
    </>
  );
}
