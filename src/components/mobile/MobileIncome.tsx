import { useMemo, useState } from "react";
import { Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { currency } from "@/lib/dashboard-format";
import type { DashboardGoal, DashboardInflow, DashboardProject } from "@/lib/dashboard-api";
import { MobileBadge, MobileEmpty, MobileListCard, MobileRow } from "./MobileList";

export function MobileIncome({
  inflows,
  goals,
  projects,
  loading,
  onDeleteInflow,
}: {
  inflows: DashboardInflow[];
  goals: DashboardGoal[];
  projects: DashboardProject[];
  loading: boolean;
  onDeleteInflow: (inflowId: string) => Promise<void>;
}) {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const targetLabels = useMemo(() => {
    const map: Record<string, string> = {};
    goals.forEach((g) => {
      map[`goal:${g.id}`] = `${g.emoji} ${g.name}`;
    });
    projects.forEach((p) => {
      map[`project:${p.id}`] = `${p.emoji} ${p.name}`;
    });
    return map;
  }, [goals, projects]);

  const sorted = useMemo(
    () => [...inflows].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime()),
    [inflows],
  );
  const total = sorted.reduce((sum, i) => sum + i.amount, 0);

  // An inflow can be tagged to a goal AND a project, so collect both labels.
  function labelsFor(inflow: DashboardInflow) {
    const labels: string[] = [];
    if (inflow.goalId) {
      const label = targetLabels[`goal:${inflow.goalId}`];
      if (label) labels.push(label);
    }
    if (inflow.projectId) {
      const label = targetLabels[`project:${inflow.projectId}`];
      if (label) labels.push(label);
    }
    return labels;
  }

  async function handleDelete(inflow: DashboardInflow) {
    if (!window.confirm(`Delete "${inflow.item}"?`)) return;
    setDeletingId(inflow.id);
    try {
      await onDeleteInflow(inflow.id);
    } catch {
      // Row stays; the next refresh reconciles.
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1 text-xs text-muted-foreground">
        <span>
          {sorted.length} {sorted.length === 1 ? "entry" : "entries"}
        </span>
        <span className="font-semibold tabular-nums text-emerald-500">
          {currency.format(total)}
        </span>
      </div>

      <MobileListCard>
        {loading ? (
          <MobileEmpty label="Loading income..." />
        ) : sorted.length === 0 ? (
          <MobileEmpty label="No income recorded yet." />
        ) : (
          sorted.map((inflow) => (
            <MobileRow
              key={inflow.id}
              title={inflow.item}
              subtitle={inflow.timestamp.toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
              badges={labelsFor(inflow).map((label) => (
                <MobileBadge key={label}>{label}</MobileBadge>
              ))}
              amount={`+${currency.format(inflow.amount)}`}
              amountTone="positive"
              actions={
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-9 w-9 text-destructive hover:text-destructive"
                  aria-label={`Delete ${inflow.item}`}
                  disabled={deletingId === inflow.id}
                  onClick={() => void handleDelete(inflow)}
                >
                  {deletingId === inflow.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </Button>
              }
            />
          ))
        )}
      </MobileListCard>
    </div>
  );
}
