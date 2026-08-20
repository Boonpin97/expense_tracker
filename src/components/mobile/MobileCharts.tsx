import { useMemo, useState } from "react";
import { endOfDay, format, startOfDay, subDays } from "date-fns";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { colorForCategory, currency } from "@/lib/dashboard-format";
import type { DashboardCategory, DashboardTransaction } from "@/lib/dashboard-api";
import {
  MobileCategoryFilter,
  MobileRangeSelect,
  mobileRange,
  useCategorySelection,
  type MobileRangeKey,
} from "./MobileFilters";

/** Compact currency for axis ticks — "$1,234.00" eats ~62px of a ~295px plot. */
function shortCurrency(value: number) {
  const abs = Math.abs(value);
  if (abs >= 1000) return `$${(value / 1000).toFixed(abs >= 10000 ? 0 : 1)}k`;
  return `$${Math.round(value)}`;
}

const AXIS = "oklch(0.55 0.04 257)";
const GRID = "oklch(0.92 0.01 256)";
const TOOLTIP_STYLE = {
  borderRadius: 8,
  border: `1px solid ${GRID}`,
  fontSize: 12,
} as const;

export function MobileCharts({
  transactions,
  categories,
  loading,
}: {
  transactions: DashboardTransaction[];
  categories: DashboardCategory[];
  loading: boolean;
}) {
  // Each card owns its own range, exactly as the desktop TrendCard and
  // CategoryPieCard each carry a separate RangeSelector.
  const [trendRange, setTrendRange] = useState<MobileRangeKey>("current-month");
  const [pieRange, setPieRange] = useState<MobileRangeKey>("current-month");
  const trendCats = useCategorySelection(categories);

  const trend = useMemo(() => {
    const { from, to } = mobileRange(trendRange);
    const allowed = new Set(trendCats.selected);
    const perDay = new Map<string, number>();
    transactions.forEach((t) => {
      if (t.timestamp < from || t.timestamp > to) return;
      if (!allowed.has(t.category)) return;
      const key = startOfDay(t.timestamp).toISOString();
      perDay.set(key, (perDay.get(key) ?? 0) + t.amount);
    });
    const series: { date: string; amount: number }[] = [];
    for (
      let cursor = startOfDay(from);
      cursor <= to;
      cursor = startOfDay(new Date(cursor.getTime() + 86400000))
    ) {
      series.push({
        date: format(cursor, "MMM d"),
        amount: Number((perDay.get(cursor.toISOString()) ?? 0).toFixed(2)),
      });
    }
    return series;
  }, [transactions, trendRange, trendCats.selected]);

  const weekly = useMemo(() => {
    const now = new Date();
    return Array.from({ length: 7 }, (_, index) => {
      const day = subDays(now, 6 - index);
      const from = startOfDay(day);
      const to = endOfDay(day);
      const amount = transactions
        .filter((t) => t.timestamp >= from && t.timestamp <= to)
        .reduce((sum, t) => sum + t.amount, 0);
      return { day: format(day, "EEE"), amount: Number(amount.toFixed(2)) };
    });
  }, [transactions]);

  const byCategory = useMemo(() => {
    const { from, to } = mobileRange(pieRange);
    const totals = new Map<string, number>();
    transactions.forEach((t) => {
      if (t.timestamp < from || t.timestamp > to) return;
      totals.set(t.category, (totals.get(t.category) ?? 0) + t.amount);
    });
    const emojiFor = new Map(categories.map((c) => [c.name, c.emoji]));
    return [...totals.entries()]
      .map(([name, amount], index) => ({
        name,
        amount: Number(amount.toFixed(2)),
        emoji: emojiFor.get(name) ?? "📦",
        color: colorForCategory(index),
      }))
      .sort((a, b) => b.amount - a.amount);
  }, [transactions, categories, pieRange]);

  const pieTotal = byCategory.reduce((sum, row) => sum + row.amount, 0);
  const trendTotal = trend.reduce((sum, row) => sum + row.amount, 0);

  if (loading) {
    return (
      <Card>
        <CardContent className="p-10">
          <p className="text-center text-sm text-muted-foreground">Loading charts...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="gap-3 pb-2">
          <div className="flex items-baseline justify-between gap-2">
            <CardTitle className="text-base">Spending Trend</CardTitle>
            <span className="shrink-0 text-sm font-semibold tabular-nums">
              {currency.format(trendTotal)}
            </span>
          </div>
          <div className="flex gap-2">
            <MobileRangeSelect value={trendRange} onChange={setTrendRange} />
            <MobileCategoryFilter
              categories={categories}
              selected={trendCats.selected}
              isAllMode={trendCats.isAllMode}
              onToggleAll={trendCats.toggleAll}
              onToggleOne={trendCats.toggleOne}
            />
          </div>
        </CardHeader>
        <CardContent className="pl-0 pr-3">
          <div className="h-56 w-full">
            <ResponsiveContainer>
              <LineChart data={trend} margin={{ top: 5, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="date" stroke={AXIS} fontSize={11} minTickGap={28} />
                <YAxis stroke={AXIS} fontSize={11} width={46} tickFormatter={shortCurrency} />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  formatter={(value: number) => currency.format(value)}
                />
                <Line
                  type="monotone"
                  dataKey="amount"
                  stroke="oklch(0.65 0.18 254)"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Daily Spending (this week)</CardTitle>
        </CardHeader>
        <CardContent className="pl-0 pr-3">
          <div className="h-56 w-full">
            <ResponsiveContainer>
              <BarChart data={weekly} margin={{ top: 5, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="day" stroke={AXIS} fontSize={11} />
                <YAxis stroke={AXIS} fontSize={11} width={46} tickFormatter={shortCurrency} />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  formatter={(value: number) => currency.format(value)}
                />
                <Bar dataKey="amount" fill="oklch(0.65 0.18 254)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="gap-3 pb-2">
          <div className="flex items-baseline justify-between gap-2">
            <CardTitle className="text-base">By Category</CardTitle>
            <span className="shrink-0 text-sm font-semibold tabular-nums">
              {currency.format(pieTotal)}
            </span>
          </div>
          <MobileRangeSelect value={pieRange} onChange={setPieRange} />
        </CardHeader>
        <CardContent>
          {byCategory.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No spending in this range.
            </p>
          ) : (
            <>
              <div className="h-52 w-full">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie
                      data={byCategory}
                      dataKey="amount"
                      nameKey="name"
                      innerRadius={48}
                      outerRadius={80}
                      paddingAngle={1}
                      // No slice labels: at this width the label ring alone needs
                      // more room than the chart box has. The legend carries them.
                      label={false}
                      labelLine={false}
                    >
                      {byCategory.map((row) => (
                        <Cell key={row.name} fill={row.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={TOOLTIP_STYLE}
                      formatter={(value: number) => currency.format(value)}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="mt-3 space-y-1.5">
                {byCategory.map((row) => {
                  const pct = pieTotal > 0 ? (row.amount / pieTotal) * 100 : 0;
                  return (
                    <div key={row.name} className="flex items-center gap-2 text-xs">
                      <span
                        className="h-2.5 w-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: row.color }}
                      />
                      <span className="shrink-0">{row.emoji}</span>
                      <span className="min-w-0 flex-1 truncate">{row.name}</span>
                      <span className="shrink-0 tabular-nums text-muted-foreground">
                        {Math.round(pct)}%
                      </span>
                      <span className="shrink-0 font-medium tabular-nums">
                        {currency.format(row.amount)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
