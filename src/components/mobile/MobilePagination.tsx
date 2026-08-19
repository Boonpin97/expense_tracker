import { ChevronLeft, ChevronRight } from "lucide-react";

/**
 * Numbered pager showing a sliding window of five pages centred on the current
 * one (current ±2), clamped so the window stays full at either end:
 *
 *   page 1  of 12 -> 1 2 3 4 5      (1 underlined)
 *   page 5  of 12 -> 3 4 5 6 7      (5 underlined)
 *   page 12 of 12 -> 8 9 10 11 12   (12 underlined)
 */
export function pageWindow(current: number, totalPages: number, size = 5) {
  if (totalPages <= 0) return [];
  const span = Math.min(size, totalPages);
  // Clamp the start so the window never runs past the last page.
  const start = Math.min(Math.max(current - Math.floor(span / 2), 1), totalPages - span + 1);
  return Array.from({ length: span }, (_, i) => start + i);
}

export function MobilePagination({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (next: number) => void;
}) {
  if (totalPages <= 1) return null;
  const pages = pageWindow(page, totalPages);

  return (
    <nav
      aria-label="Pagination"
      className="flex items-center justify-center gap-1 pt-1"
    >
      <button
        type="button"
        aria-label="Previous page"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
        className="flex h-10 w-10 items-center justify-center rounded-md text-muted-foreground disabled:opacity-30"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>

      {pages.map((n) => {
        const current = n === page;
        return (
          <button
            key={n}
            type="button"
            aria-label={`Page ${n}`}
            aria-current={current ? "page" : undefined}
            onClick={() => onChange(n)}
            className={`h-10 min-w-10 rounded-md px-2 text-sm tabular-nums ${
              current
                ? "font-semibold text-foreground underline underline-offset-4"
                : "text-muted-foreground"
            }`}
          >
            {n}
          </button>
        );
      })}

      <button
        type="button"
        aria-label="Next page"
        disabled={page >= totalPages}
        onClick={() => onChange(page + 1)}
        className="flex h-10 w-10 items-center justify-center rounded-md text-muted-foreground disabled:opacity-30"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </nav>
  );
}
