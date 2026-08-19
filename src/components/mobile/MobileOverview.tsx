import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { currency } from "@/lib/dashboard-format";
import type { DashboardInflow, DashboardTransaction } from "@/lib/dashboard-api";
import { MobileEmpty, MobileListCard, MobileRow, MobileSectionHeading } from "./MobileList";

function startOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

/**
 * Single-column month summary. The desktop stat grid is `grid-cols-2` down to
 * the lg breakpoint, which leaves roughly 75px of text width for values like
 * "$12,345.67" on a 375px screen.
 */
export function MobileOverview({
  transactions,
  inflows,
  loading,
  onSeeAll,
}: {
  transactions: DashboardTransaction[];
  inflows: DashboardInflow[];
  loading: boolean;
  onSeeAll: () => void;
}) {
  const { spent, earned, net, recent } = useMemo(() => {
    const from = startOfMonth(new Date());
    const monthTx = transactions.filter((t) => t.timestamp >= from);
    const monthIn = inflows.filter((i) => i.timestamp >= from);
    const spentTotal = monthTx.reduce((sum, t) => sum + t.amount, 0);
    const earnedTotal = monthIn.reduce((sum, i) => sum + i.amount, 0);
    return {
      spent: spentTotal,
      earned: earnedTotal,
      net: earnedTotal - spentTotal,
      recent: [...transactions]
        .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
        .slice(0, 8),
    };
  }, [transactions, inflows]);

  const monthLabel = new Date().toLocaleDateString(undefined, { month: "long", year: "numeric" });

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-5">
          <p className="text-xs text-muted-foreground">{monthLabel}</p>
          <p
            className={`mt-1 text-3xl font-semibold tabular-nums ${
              net < 0 ? "text-destructive" : "text-emerald-500"
            }`}
          >
            {currency.format(net)}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">Net this month</p>

          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-secondary/60 p-3">
              <p className="text-xs text-muted-foreground">Spent</p>
              <p className="mt-0.5 truncate text-base font-semibold tabular-nums">
                {currency.format(spent)}
              </p>
            </div>
            <div className="rounded-lg bg-secondary/60 p-3">
              <p className="text-xs text-muted-foreground">Income</p>
              <p className="mt-0.5 truncate text-base font-semibold tabular-nums text-emerald-500">
                {currency.format(earned)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <MobileSectionHeading
        title="Recent expenses"
        action={
          <button
            type="button"
            onClick={onSeeAll}
            className="min-h-11 text-sm font-medium text-primary"
          >
            See all
          </button>
        }
      />

      <MobileListCard>
        {loading ? (
          <MobileEmpty label="Loading..." />
        ) : recent.length === 0 ? (
          <MobileEmpty label="No expenses recorded yet." />
        ) : (
          recent.map((tx) => (
            <MobileRow
              key={tx.id}
              title={tx.item}
              subtitle={`${tx.category} · ${tx.timestamp.toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              })}`}
              amount={currency.format(tx.amount)}
            />
          ))
        )}
      </MobileListCard>
    </div>
  );
}
