import { useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { currency, deadlineLabel } from "@/lib/dashboard-format";
import type { DashboardInflow, DashboardProject } from "@/lib/dashboard-api";
import { MobileEmpty, MobileListCard, MobileRow } from "./MobileList";

/**
 * Stacked project cards. Tapping one opens its contribution history, mirroring
 * the desktop detail dialog but with the stat strip in one column instead of
 * three (three ~93px columns wrap their labels onto two lines at 375px).
 */
export function MobileProjects({
  projects,
  inflows,
  loading,
}: {
  projects: DashboardProject[];
  inflows: DashboardInflow[];
  loading: boolean;
}) {
  // Track the id rather than the object so the dialog reflects live edits and
  // closes itself if the project disappears from a refresh.
  const [detailId, setDetailId] = useState<string | null>(null);

  const detailProject = useMemo(
    () => projects.find((p) => p.id === detailId) ?? null,
    [projects, detailId],
  );
  const detailInflows = useMemo(
    () =>
      detailId
        ? inflows
            .filter((i) => i.projectId === detailId)
            .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
        : [],
    [inflows, detailId],
  );
  const detailContributed = detailInflows.reduce((sum, i) => sum + i.amount, 0);

  if (loading) {
    return (
      <Card>
        <CardContent className="p-0">
          <MobileEmpty label="Loading projects..." />
        </CardContent>
      </Card>
    );
  }

  if (projects.length === 0) {
    return (
      <Card>
        <CardContent className="p-0">
          <MobileEmpty label="No long-term projects yet. Create one with /new_projects." />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <p className="px-1 text-xs text-muted-foreground">
        Cumulative savings toward a deadline — progress never resets. Tap for history.
      </p>

      {projects.map((project) => {
        const pct = project.targetAmount > 0 ? (project.accumulated / project.targetAmount) * 100 : 0;
        const reached = project.targetAmount > 0 && project.accumulated >= project.targetAmount;
        const due = deadlineLabel(project.deadline);
        return (
          <Card
            key={project.id}
            role="button"
            tabIndex={0}
            aria-label={`View ${project.name} contributions`}
            className="cursor-pointer active:bg-secondary/40"
            onClick={() => setDetailId(project.id)}
            onKeyDown={(event) => {
              if (event.target !== event.currentTarget) return;
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                setDetailId(project.id);
              }
            }}
          >
            <CardContent className="space-y-2 p-4">
              <div className="flex items-center gap-2">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-secondary text-base leading-none">
                  {project.emoji}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{project.name}</p>
                  {due.text ? (
                    <p
                      className={`text-xs ${due.overdue ? "text-destructive" : "text-muted-foreground"}`}
                    >
                      {due.text}
                    </p>
                  ) : null}
                </div>
                <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                  {Math.round(pct)}%
                </span>
              </div>
              <div className="flex items-baseline justify-between gap-2">
                <span
                  className={`text-lg font-semibold tabular-nums ${
                    reached ? "text-emerald-500" : "text-foreground"
                  }`}
                >
                  {currency.format(project.accumulated)}
                </span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  of {currency.format(project.targetAmount)}
                </span>
              </div>
              <Progress
                value={Math.min(pct, 100)}
                className={reached ? "[&>div]:bg-emerald-500" : "[&>div]:bg-accent"}
              />
            </CardContent>
          </Card>
        );
      })}

      <Dialog
        open={detailProject !== null}
        onOpenChange={(open) => {
          if (!open) setDetailId(null);
        }}
      >
        <DialogContent>
          {detailProject ? (
            <>
              <DialogHeader>
                <DialogTitle>
                  {detailProject.emoji} {detailProject.name}
                </DialogTitle>
                <DialogDescription>
                  {currency.format(detailProject.accumulated)} of{" "}
                  {currency.format(detailProject.targetAmount)} saved
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Starting amount</span>
                  <span className="font-semibold tabular-nums">
                    {currency.format(detailProject.initialAmount)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Income assigned</span>
                  <span className="font-semibold tabular-nums text-emerald-500">
                    +{currency.format(detailContributed)}
                  </span>
                </div>
                <div className="flex justify-between border-t pt-2 text-sm">
                  <span className="text-muted-foreground">Total saved</span>
                  <span className="font-semibold tabular-nums">
                    {currency.format(detailProject.accumulated)}
                  </span>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Contribution history</p>
                {detailInflows.length === 0 ? (
                  <MobileListCard>
                    <MobileEmpty label="No income assigned to this project yet." />
                  </MobileListCard>
                ) : (
                  <MobileListCard>
                    {detailInflows.map((inflow) => (
                      <MobileRow
                        key={inflow.id}
                        title={inflow.item}
                        subtitle={inflow.timestamp.toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                        amount={`+${currency.format(inflow.amount)}`}
                        amountTone="positive"
                      />
                    ))}
                  </MobileListCard>
                )}
                <p className="text-xs text-muted-foreground">
                  The starting amount is seed capital entered on the project itself, so it has no
                  income entry and is not listed above.
                </p>
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
