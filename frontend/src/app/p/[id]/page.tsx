import { Suspense } from "react";

import { WorkspaceLoader } from "@/components/workspace/WorkspaceLoader";
import { WorkspaceSkeleton } from "@/components/workspace/WorkspaceSkeleton";

// With Cache Components, a dynamic param is request-time data, so it is read inside Suspense.
export default function ProjectPage({ params }: PageProps<"/p/[id]">) {
  return (
    <Suspense fallback={<WorkspaceSkeleton />}>
      {params.then(({ id }) => (
        <WorkspaceLoader key={id} projectId={id} />
      ))}
    </Suspense>
  );
}
