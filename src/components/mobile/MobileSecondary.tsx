import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { colorForCategory, currency } from "@/lib/dashboard-format";
import type { DashboardPlan, DashboardTransaction } from "@/lib/dashboard-api";
import { MobileEmpty, MobileListCard, MobileRow } from "./MobileList";

function startOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

/** Month-to-date spend per category, descending. */
function useMonthByCategory(transactions: DashboardTransaction[]) {
  return useMemo(() => {
    const from = startOfMonth(new Date());
    const totals = new Map<string, number>();
    transactions
      .filter((t) => t.timestamp >= from)
      .forEach((t) => totals.set(t.category, (totals.get(t.category) ?? 0) + t.amount));
    return [...totals.entries()]
      .map(([category, amount]) => ({ category, amount }))
      .sort((a, b) => b.amount - a.amount);
  }, [transactions]);
}

/**
 * Category breakdown as a proportional bar list rather than a pie. At 375px the
 * desktop donut spends ~214px of a 224px box on the chart and its label ring,
 * so slice labels clip; a list stays readable and shows exact figures.
 */
export function MobileCharts({ transactions }: { transactions: DashboardTransaction[] }) {
  const rows = useMonthByCategory(transactions);
  const total = rows.reduce((sum, r) => sum + r.amount, 0);

  if (rows.length === 0) {
    return (
      <Card>
        <CardContent className="p-0">
          <MobileEmpty label="No spending this month yet." />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <div className="flex items-baseline justify-between">
          <p className="text-sm font-medium">Spending by category</p>
          <p className="text-sm font-semibold tabular-nums">{currency.format(total)}</p>
        </div>
        {rows.map((row, index) => {
          const pct = total > 0 ? (row.amount / total) * 100 : 0;
          return (
            <div key={row.category} className="space-y-1">
              <div className="flex items-baseline justify-between gap-2">
                <span className="min-w-0 truncate text-sm">{row.category}</span>
                <span className="shrink-0 text-sm tabular-nums">
                  {currency.format(row.amount)}
                  <span className="ml-1 text-xs text-muted-foreground">
                    {Math.round(pct)}%
                  </span>
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${pct}%`, backgroundColor: colorForCategory(index) }}
                />
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export function MobileBudget({
  budgets,
  transactions,
}: {
  budgets: Record<string, number>;
  transactions: DashboardTransaction[];
}) {
  const spentByCategory = useMemo(() => {
    const from = startOfMonth(new Date());
    const totals = new Map<string, number>();
    transactions
      .filter((t) => t.timestamp >= from)
      .forEach((t) => totals.set(t.category, (totals.get(t.category) ?? 0) + t.amount));
    return totals;
  }, [transactions]);

  const entries = Object.entries(budgets).sort(([a], [b]) => a.localeCompare(b));
  const budgetTotal = entries.reduce((sum, [, amount]) => sum + amount, 0);
  const spentTotal = entries.reduce(
    (sum, [category]) => sum + (spentByCategory.get(category) ?? 0),
    0,
  );

  if (entries.length === 0) {
    return (
      <Card>
        <CardContent className="p-0">
          <MobileEmpty label="No budgets set. Use /set_budget in the bot." />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <Card>
        <CardContent className="p-4">
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-muted-foreground">Spent this month</span>
            <span className="text-xs text-muted-foreground tabular-nums">
              of {currency.format(budgetTotal)}
            </span>
          </div>
          <p
            className={`mt-1 text-2xl font-semibold tabular-nums ${
              spentTotal > budgetTotal ? "text-destructive" : "text-foreground"
            }`}
          >
            {currency.format(spentTotal)}
          </p>
          <Progress
            className="mt-3"
            value={budgetTotal > 0 ? Math.min((spentTotal / budgetTotal) * 100, 100) : 0}
          />
        </CardContent>
      </Card>

      {entries.map(([category, limit]) => {
        const spent = spentByCategory.get(category) ?? 0;
        const pct = limit > 0 ? (spent / limit) * 100 : 0;
        const over = spent > limit;
        return (
          <Card key={category}>
            <CardContent className="space-y-2 p-4">
              <div className="flex items-baseline justify-between gap-2">
                <span className="min-w-0 truncate text-sm font-medium">{category}</span>
                <span
                  className={`shrink-0 text-sm font-semibold tabular-nums ${
                    over ? "text-destructive" : "text-foreground"
                  }`}
                >
                  {currency.format(spent)}
                  <span className="ml-1 text-xs font-normal text-muted-foreground">
                    / {currency.format(limit)}
                  </span>
                </span>
              </div>
              <Progress
                value={Math.min(pct, 100)}
                className={over ? "[&>div]:bg-destructive" : "[&>div]:bg-accent"}
              />
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

export function MobilePlans({ plans, loading }: { plans: DashboardPlan[]; loading: boolean }) {
  const active = plans.filter((p) => p.status === "active");

  if (loading) {
    return (
      <MobileListCard>
        <MobileEmpty label="Loading subscriptions..." />
      </MobileListCard>
    );
  }

  if (active.length === 0) {
    return (
      <MobileListCard>
        <MobileEmpty label="No active recurring or split payments." />
      </MobileListCard>
    );
  }

  return (
    <MobileListCard>
      {active.map((plan) => {
        const isSplit = plan.planType === "split_payment";
        const amount = isSplit
          ? plan.installmentCount > 0
            ? plan.totalAmount / plan.installmentCount
            : plan.totalAmount
          : plan.amount;
        const due = plan.nextDueDate
          ? new Date(plan.nextDueDate).toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
            })
          : `Day ${plan.dayOfMonth}`;
        return (
          <MobileRow
            key={plan.id}
            title={plan.item}
            subtitle={`${plan.category} · ${isSplit ? "Split" : "Monthly"} · next ${due}`}
            amount={currency.format(amount)}
          />
        );
      })}
    </MobileListCard>
  );
}
