import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { currency } from "@/lib/dashboard-format";
import type { DashboardCategory, DashboardTransaction } from "@/lib/dashboard-api";
import { MobileEmpty } from "./MobileList";

function startOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

/**
 * Mirrors the desktop Budget tab's data, but folds its three StatCards into one
 * combined line — "spent / total" with remaining underneath — since three
 * currency values side by side leave ~75px each at 375px.
 */
export function MobileBudget({
  budgets,
  categories,
  transactions,
  loading,
}: {
  budgets: Record<string, number>;
  categories: DashboardCategory[];
  transactions: DashboardTransaction[];
  loading: boolean;
}) {
  const rows = useMemo(() => {
    const from = startOfMonth(new Date());
    const spentByCategory = new Map<string, number>();
    transactions
      .filter((t) => t.timestamp >= from)
      .forEach((t) => spentByCategory.set(t.category, (spentByCategory.get(t.category) ?? 0) + t.amount));

    return categories
      .map((category) => ({
        category,
        spent: spentByCategory.get(category.name) ?? 0,
        budget: budgets[category.name] ?? 0,
      }))
      .sort((left, right) => {
        // Budgeted categories first, then the most over-budget, matching desktop.
        const leftHas = left.budget > 0;
        const rightHas = right.budget > 0;
        if (leftHas !== rightHas) return leftHas ? -1 : 1;
        if (leftHas && rightHas) {
          const leftRatio = left.spent / left.budget;
          const rightRatio = right.spent / right.budget;
          if (leftRatio !== rightRatio) return rightRatio - leftRatio;
        }
        return left.category.order - right.category.order;
      });
  }, [categories, budgets, transactions]);

  const budgetTotal = rows.reduce((sum, row) => sum + row.budget, 0);
  const spentTotal = rows.reduce((sum, row) => sum + (row.budget > 0 ? row.spent : 0), 0);
  const remaining = Math.max(budgetTotal - spentTotal, 0);
  const usedPct = budgetTotal > 0 ? Math.round((spentTotal / budgetTotal) * 100) : 0;
  const leftPct = Math.round((remaining / Math.max(budgetTotal, 1)) * 100);
  const overall = spentTotal > budgetTotal;

  if (loading) {
    return (
      <Card>
        <CardContent className="p-0">
          <MobileEmpty label="Loading budget data..." />
        </CardContent>
      </Card>
    );
  }

  if (categories.length === 0) {
    return (
      <Card>
        <CardContent className="p-0">
          <MobileEmpty label="No categories found." />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <Card>
        <CardContent className="p-4">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-sm text-muted-foreground">Spent this month</span>
            <span className="text-xs text-muted-foreground tabular-nums">{usedPct}% used</span>
          </div>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            <span className={overall ? "text-destructive" : "text-foreground"}>
              {currency.format(spentTotal)}
            </span>
            <span className="text-base font-normal text-muted-foreground">
              {" / "}
              {currency.format(budgetTotal)}
            </span>
          </p>
          <Progress
            value={budgetTotal > 0 ? Math.min((spentTotal / budgetTotal) * 100, 100) : 0}
            className={overall ? "mt-3 [&>div]:bg-destructive" : "mt-3 [&>div]:bg-accent"}
          />
          <p className="mt-2 text-sm">
            {overall ? (
              <span className="font-medium text-destructive">
                {currency.format(spentTotal - budgetTotal)} over budget
              </span>
            ) : (
              <>
                <span className="font-medium text-emerald-600">
                  {currency.format(remaining)}
                </span>
                <span className="text-muted-foreground"> remaining · {leftPct}% left</span>
              </>
            )}
          </p>
        </CardContent>
      </Card>

      <p className="px-1 pt-2 text-sm font-medium">Budget by Category</p>

      {rows.map(({ category, spent, budget }) => {
        const pct = budget > 0 ? Math.min((spent / budget) * 100, 100) : 0;
        const over = budget > 0 && spent > budget;
        return (
          <Card key={category.name}>
            <CardContent className="space-y-2 p-4">
              <div className="flex items-center gap-2">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-secondary text-base leading-none">
                  {category.emoji}
                </span>
                <p className="min-w-0 flex-1 truncate text-sm font-medium">{category.name}</p>
              </div>
              <div className="flex items-baseline justify-between gap-2">
                <span
                  className={`text-base font-semibold tabular-nums ${
                    over ? "text-destructive" : "text-foreground"
                  }`}
                >
                  {currency.format(spent)}
                </span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {budget > 0 ? (
                    <>
                      of {currency.format(budget)} ·{" "}
                      <span className={over ? "text-destructive" : undefined}>
                        {over
                          ? `${currency.format(spent - budget)} over`
                          : `${currency.format(budget - spent)} left`}
                      </span>
                    </>
                  ) : (
                    "No budget set"
                  )}
                </span>
              </div>
              {budget > 0 ? (
                <Progress
                  value={pct}
                  className={over ? "[&>div]:bg-destructive" : "[&>div]:bg-accent"}
                />
              ) : null}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
