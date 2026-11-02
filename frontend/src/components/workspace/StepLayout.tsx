import type { ReactNode } from "react";

/** Two-pane step layout: a large stage on the left, a scrolling side panel on the right (stacked on mobile). */
export function StepLayout({ toolbar, stage, panel }: { toolbar?: ReactNode; stage: ReactNode; panel: ReactNode }) {
  return (
    <div className="flex h-full flex-col lg:flex-row">
      <section className="flex min-w-0 flex-1 flex-col gap-2 p-2 sm:p-3 lg:min-h-0">
        {toolbar && <div className="flex flex-wrap items-center gap-2">{toolbar}</div>}
        <div className="h-[min(62vh,80vw)] min-h-[260px] lg:h-auto lg:min-h-0 lg:flex-1">{stage}</div>
      </section>
      <aside className="scroll-thin w-full shrink-0 space-y-3 border-t border-line bg-surface p-3 sm:p-4 lg:w-[380px] lg:overflow-y-auto lg:border-l lg:border-t-0">
        {panel}
      </aside>
    </div>
  );
}

export function PanelHeading({ title, subtitle }: { title: string; subtitle?: ReactNode }) {
  return (
    <div className="pb-1">
      <h2 className="text-base font-bold">{title}</h2>
      {subtitle && <p className="mt-0.5 text-[13px] leading-relaxed text-muted">{subtitle}</p>}
    </div>
  );
}
