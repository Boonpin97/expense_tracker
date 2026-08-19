import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Card-list primitives that replace the desktop <Table> on mobile.
 *
 * The four desktop tables each need roughly 420px of width but only get ~295px
 * inside a card at 375px, so they fall back to a nested horizontal scroll with
 * no affordance. A stacked row avoids horizontal scrolling entirely.
 */

export function MobileListCard({ children }: { children: ReactNode }) {
  return (
    <Card>
      <CardContent className="divide-y p-0">{children}</CardContent>
    </Card>
  );
}

export function MobileRow({
  title,
  subtitle,
  amount,
  amountTone = "default",
  badges,
  actions,
  onClick,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  amount?: ReactNode;
  amountTone?: "default" | "positive" | "negative";
  badges?: ReactNode;
  actions?: ReactNode;
  onClick?: () => void;
}) {
  const tone =
    amountTone === "positive"
      ? "text-emerald-500"
      : amountTone === "negative"
        ? "text-destructive"
        : "text-foreground";

  const interactive = typeof onClick === "function";

  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 ${interactive ? "cursor-pointer active:bg-secondary/50" : ""}`}
      {...(interactive
        ? {
            role: "button",
            tabIndex: 0,
            onClick,
            onKeyDown: (event: React.KeyboardEvent<HTMLDivElement>) => {
              if (event.target !== event.currentTarget) return;
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onClick?.();
              }
            },
          }
        : {})}
    >
      {/* min-w-0 is what lets the long text truncate instead of pushing the
          row wider than the viewport. */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{title}</p>
        {subtitle ? <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p> : null}
        {badges ? <div className="mt-1 flex flex-wrap gap-1">{badges}</div> : null}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        {amount ? <p className={`text-sm font-semibold tabular-nums ${tone}`}>{amount}</p> : null}
        {actions ? <div className="flex items-center gap-1">{actions}</div> : null}
      </div>
    </div>
  );
}

export function MobileBadge({ children }: { children: ReactNode }) {
  return (
    <span className="rounded bg-secondary px-1.5 py-0.5 text-xs text-muted-foreground">
      {children}
    </span>
  );
}

export function MobileEmpty({ label }: { label: string }) {
  return <p className="px-4 py-10 text-center text-sm text-muted-foreground">{label}</p>;
}

export function MobileSectionHeading({
  title,
  action,
}: {
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-base font-semibold">{title}</h2>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
