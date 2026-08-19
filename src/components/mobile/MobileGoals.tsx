import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { currency } from "@/lib/dashboard-format";
import type { DashboardGoal } from "@/lib/dashboard-api";
import { MobileEmpty } from "./MobileList";

/**
 * Stacked goal card.
 *
 * The desktop row keeps the amount text and four icon buttons on one
 * `shrink-0` line, which needs ~314px inside ~295px of card width and pushes
 * the whole document sideways. Here the name gets its own line and the figures
 * sit below it, so nothing is forced to a minimum width.
 */
export function MobileGoals({
  goals,
  loading,
}: {
  goals: DashboardGoal[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <Card>
        <CardContent className="p-0">
          <MobileEmpty label="Loading goals..." />
        </CardContent>
      </Card>
    );
  }

  if (goals.length === 0) {
    return (
      <Card>
        <CardContent className="p-0">
          <MobileEmpty label="No goals yet. Create one from the bot with /new_goal." />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <p className="px-1 text-xs text-muted-foreground">
        Monthly savings targets — progress resets each month.
      </p>
      {goals.map((goal) => {
        const pct = goal.targetAmount > 0 ? (goal.accumulated / goal.targetAmount) * 100 : 0;
        const reached = goal.targetAmount > 0 && goal.accumulated >= goal.targetAmount;
        return (
          <Card key={goal.id}>
            <CardContent className="space-y-2 p-4">
              <div className="flex items-center gap-2">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-secondary text-base leading-none">
                  {goal.emoji}
                </span>
                <p className="min-w-0 flex-1 truncate text-sm font-medium">{goal.name}</p>
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
                  {currency.format(goal.accumulated)}
                </span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  of {currency.format(goal.targetAmount)}
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
    </div>
  );
}
