import { useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { ProjectCard } from "@/components/ProjectCard";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { currency } from "@/lib/dashboard-format";
import type { DashboardInflow, DashboardProject } from "@/lib/dashboard-api";
import { MobileEmpty, MobileListCard, MobileRow } from "./MobileList";
import { MobilePagination } from "./MobilePagination";

const HISTORY_PAGE_SIZE = 8;

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
  const [historyPage, setHistoryPage] = useState(1);

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

  // Group once: every card needs its own contributions to judge pace.
  const contributionsByProject = useMemo(() => {
    const map = new Map<string, DashboardInflow[]>();
    inflows.forEach((inflow) => {
      if (!inflow.projectId) return;
      const existing = map.get(inflow.projectId);
      if (existing) existing.push(inflow);
      else map.set(inflow.projectId, [inflow]);
    });
    return map;
  }, [inflows]);

  const historyPages = Math.max(1, Math.ceil(detailInflows.length / HISTORY_PAGE_SIZE));
  const safeHistoryPage = Math.min(historyPage, historyPages);
  const historyShown = detailInflows.slice(
    (safeHistoryPage - 1) * HISTORY_PAGE_SIZE,
    safeHistoryPage * HISTORY_PAGE_SIZE,
  );

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

      {projects.map((project) => (
        <ProjectCard
          key={project.id}
          project={project}
          contributions={contributionsByProject.get(project.id) ?? []}
          className="active:bg-secondary/40"
          onOpen={() => {
            setDetailId(project.id);
            setHistoryPage(1);
          }}
        />
      ))}

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
                    {historyShown.map((inflow) => (
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
                <MobilePagination
                  page={safeHistoryPage}
                  totalPages={historyPages}
                  onChange={setHistoryPage}
                />
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
