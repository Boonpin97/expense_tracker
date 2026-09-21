import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { currency, currencyWhole, projectSummary } from "@/lib/dashboard-format";
import type { ProjectStatusKey } from "@/lib/dashboard-format";
import type { DashboardProject } from "@/lib/dashboard-api";

const STATUS_STYLES: Record<ProjectStatusKey, string> = {
  complete: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  "on-track": "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  behind: "border-destructive/30 bg-destructive/10 text-destructive",
  review: "border-border bg-secondary text-muted-foreground",
  new: "border-border bg-secondary text-muted-foreground",
};

function StatusPill({ status }: { status: { key: ProjectStatusKey; label: string } }) {
  return (
    <span
      className={cn(
        "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        STATUS_STYLES[status.key],
      )}
    >
      {status.label}
    </span>
  );
}

/**
 * One long-term project, rendered identically on desktop and mobile: identity
 * row, progress bar, current-vs-target line, and the two projection lines
 * (amount still needed, and the monthly rate that lands it on the deadline).
 *
 * `actions` is the desktop row of edit/reorder/delete buttons; mobile passes
 * none. Clicks inside it must not bubble into the card's own open handler, so
 * the wrapper stops propagation.
 */
export function ProjectCard({
  project,
  contributions,
  onOpen,
  actions,
  className,
}: {
  project: DashboardProject;
  contributions: { amount: number; timestamp: Date }[];
  onOpen: () => void;
  actions?: ReactNode;
  className?: string;
}) {
  const summary = projectSummary(project, contributions);

  return (
    <Card
      role="button"
      tabIndex={0}
      aria-label={`View ${project.name} contributions`}
      className={cn(
        "cursor-pointer transition-colors hover:bg-secondary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      onClick={onOpen}
      onKeyDown={(event) => {
        // Ignore keys bubbling up from the action buttons inside the card.
        if (event.target !== event.currentTarget) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      <CardContent className="space-y-3 p-4">
        <div className="flex items-start gap-2">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-secondary text-base leading-none">
            {project.emoji}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{project.name}</p>
            <p className="truncate text-[10px] uppercase tracking-wide text-muted-foreground">
              {summary.subtitle}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <StatusPill status={summary.status} />
            {actions ? (
              <div
                className="flex items-center gap-0.5"
                onClick={(event) => event.stopPropagation()}
              >
                {actions}
              </div>
            ) : null}
          </div>
        </div>

        <Progress
          value={Math.min(summary.pct, 100)}
          className={cn("h-1.5", summary.reached ? "[&>div]:bg-emerald-500" : "[&>div]:bg-accent")}
        />

        <div className="flex items-baseline justify-between gap-2">
          <p className="min-w-0 truncate text-sm">
            <span className="text-muted-foreground">Currently </span>
            <span className="font-semibold tabular-nums">
              {currency.format(project.accumulated)}
            </span>
            <span className="text-muted-foreground">
              {" "}
              of {currency.format(project.targetAmount)} target
            </span>
          </p>
          <span className="shrink-0 text-sm font-medium tabular-nums text-muted-foreground">
            {Math.round(summary.pct)}%
          </span>
        </div>

        <div className="space-y-1 text-xs text-muted-foreground">
          <div className="flex items-baseline justify-between gap-2">
            <span className="truncate tabular-nums">
              {summary.reached
                ? "Target reached"
                : `${currencyWhole.format(summary.remaining)} to reach target`}
            </span>
            {summary.monthlyNeeded !== null ? (
              <span className="shrink-0 tabular-nums">
                {currencyWhole.format(summary.monthlyNeeded)}/mo to hit target
              </span>
            ) : null}
          </div>
          {summary.targetText ? (
            <p className={cn("text-right", summary.overdue && "text-destructive")}>
              {summary.targetText}
            </p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
