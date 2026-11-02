import Link from "next/link";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2 font-extrabold tracking-tight text-ink">
      <span className="grid size-8 place-items-center rounded-lg bg-accent text-white shadow-sm">
        <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <path d="M3 11.5 12 4l9 7.5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M5.5 10v9.5h13V10" strokeLinejoin="round" />
          <path d="M9.5 19.5v-5h5v5" strokeLinejoin="round" />
        </svg>
      </span>
      {!compact && (
        <span className="text-lg">
          Facade<span className="text-accent">AI</span>
        </span>
      )}
    </Link>
  );
}
