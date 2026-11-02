import { Logo } from "@/components/Logo";

export function WorkspaceSkeleton({ message = "Loading project…" }: { message?: string }) {
  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-14 items-center border-b border-line bg-surface px-4">
        <Logo />
      </header>
      <div className="grid flex-1 place-items-center">
        <div className="flex flex-col items-center gap-3 text-sm text-muted">
          <span className="size-8 animate-spin rounded-full border-2 border-accent/20 border-t-accent" />
          {message}
        </div>
      </div>
    </div>
  );
}
