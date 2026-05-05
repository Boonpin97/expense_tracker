import { createFileRoute } from "@tanstack/react-router";
import { endOfDay, format, startOfDay } from "date-fns";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import type { DateRange } from "react-day-picker";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  CalendarIcon,
  Filter,
  Loader2,
  LogOut,
  Plus,
  Tags,
  Target,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DashboardApiError,
  fetchDashboardBudgets,
  fetchDashboardCategories,
  fetchDashboardSession,
  fetchDashboardTransactions,
  loginToDashboard,
  logoutFromDashboard,
  type DashboardCategory,
  type DashboardSession,
  type DashboardTransaction,
} from "@/lib/dashboard-api";
import {
  analyticsCategorySelectionLabel,
  analyticsRangeForPreset,
  analyticsRangePresetLabel,
  buildCategorySummaries,
  buildTrendSeries,
  endExclusive,
  filterTransactionsBySelectedCategories,
  type AnalyticsRangePreset,
} from "@/lib/dashboard-analytics";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Expense Monitor" },
      {
        name: "description",
        content: "Expense Bot dashboard for analytics, transactions, categories, and budgets.",
      },
    ],
  }),
  component: DashboardRoute,
});

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

type SessionState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; session: DashboardSession };

function DashboardRoute() {
  const [sessionState, setSessionState] = useState<SessionState>({ status: "loading" });

  useEffect(() => {
    let active = true;

    void fetchDashboardSession()
      .then((session) => {
        if (!active) {
          return;
        }
        setSessionState(session ? { status: "authenticated", session } : { status: "anonymous" });
      })
      .catch(() => {
        if (!active) {
          return;
        }
        setSessionState({ status: "anonymous" });
      });

    return () => {
      active = false;
    };
  }, []);

  if (sessionState.status === "loading") {
    return <CenteredState title="Checking session" detail="Connecting to the dashboard backend." />;
  }

  if (sessionState.status === "anonymous") {
    return <SignInScreen onSignedIn={(session) => setSessionState({ status: "authenticated", session })} />;
  }

  return <DashboardShell onSignedOut={() => setSessionState({ status: "anonymous" })} session={sessionState.session} />;
}

function SignInScreen({
  onSignedIn,
}: {
  onSignedIn: (session: DashboardSession) => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const session = await loginToDashboard(username, password);
      onSignedIn(session);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-secondary/40 px-4 py-10">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-md items-center">
        <Card className="w-full border-border/60 bg-background shadow-sm">
          <CardContent className="p-8 sm:p-10">
            <div className="flex flex-col items-center text-center">
              <img
                alt="BudgetFlow"
                className="h-14 w-14 rounded-2xl"
                src="/logo.png"
              />
              <h1 className="mt-5 text-xl font-semibold tracking-tight text-primary">BudgetFlow</h1>
              <p className="mt-1 text-sm text-muted-foreground">Sign in to continue</p>
            </div>
            <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  autoComplete="username"
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="Enter your username"
                  required
                  value={username}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  autoComplete="current-password"
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter your password"
                  required
                  type="password"
                  value={password}
                />
              </div>
              {error ? (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              ) : null}
              <Button className="h-11 w-full" disabled={submitting} type="submit">
                {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Continue
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function DashboardShell({
  session,
  onSignedOut,
}: {
  session: DashboardSession;
  onSignedOut: () => void;
}) {
  const [rangePreset, setRangePreset] = useState<AnalyticsRangePreset>("current-month");
  const [customRange, setCustomRange] = useState<DateRange | undefined>();
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
  const knownCategoriesRef = useRef<Set<string>>(new Set());
  const [dashboardState, setDashboardState] = useState<{
    loading: boolean;
    error: string | null;
    categories: DashboardCategory[];
    budgets: Record<string, number>;
    transactions: DashboardTransaction[];
  }>({
    loading: true,
    error: null,
    categories: [],
    budgets: {},
    transactions: [],
  });

  const activeRange = useMemo(() => {
    if (rangePreset === "custom" && customRange?.from && customRange?.to) {
      return { from: startOfDay(customRange.from), to: endOfDay(customRange.to) };
    }
    return analyticsRangeForPreset(rangePreset);
  }, [customRange, rangePreset]);

  useEffect(() => {
    let active = true;

    setDashboardState((current) => ({ ...current, loading: true, error: null }));

    void Promise.all([
      fetchDashboardCategories(),
      fetchDashboardBudgets(),
      fetchDashboardTransactions({
        start: activeRange.from,
        end: endExclusive(activeRange.to),
      }),
    ])
      .then(([categories, budgets, transactions]) => {
        if (!active) {
          return;
        }
        setDashboardState({ loading: false, error: null, categories, budgets, transactions });
      })
      .catch((caught) => {
        if (!active) {
          return;
        }
        const message =
          caught instanceof DashboardApiError && caught.status === 401
            ? "The browser did not keep the dashboard session cookie after login. This is a session/cookie issue, not a credential issue."
            : caught instanceof Error
              ? caught.message
              : "Unable to load dashboard data.";
        setDashboardState((current) => ({ ...current, loading: false, error: message }));
      });

    return () => {
      active = false;
    };
  }, [activeRange.from, activeRange.to, session.chatId]);

  useEffect(() => {
    const currentNames = new Set(dashboardState.categories.map((category) => category.name));
    const knownCategories = knownCategoriesRef.current;

    setSelectedCategories((current) => {
      if (knownCategories.size === 0 && current.size === 0) {
        knownCategoriesRef.current = currentNames;
        return currentNames;
      }

      const hadAllSelected =
        knownCategories.size > 0 &&
        current.size === knownCategories.size &&
        [...knownCategories].every((name) => current.has(name));
      const nextSelected = new Set([...current].filter((name) => currentNames.has(name)));

      knownCategoriesRef.current = currentNames;
      return hadAllSelected || nextSelected.size === 0 ? currentNames : nextSelected;
    });
  }, [dashboardState.categories]);

  const filteredTransactions = useMemo(
    () => filterTransactionsBySelectedCategories(dashboardState.transactions, selectedCategories),
    [dashboardState.transactions, selectedCategories],
  );
  const trend = useMemo(
    () =>
      buildTrendSeries(filteredTransactions).map((point) => ({
        date: format(point.date, "MMM d"),
        total: Number(point.total.toFixed(2)),
      })),
    [filteredTransactions],
  );
  const categorySummaries = useMemo(
    () => buildCategorySummaries(filteredTransactions, dashboardState.categories),
    [dashboardState.categories, filteredTransactions],
  );
  const newestTransactions = useMemo(
    () =>
      [...filteredTransactions].sort((left, right) => right.timestamp.getTime() - left.timestamp.getTime()),
    [filteredTransactions],
  );
  const totalSpent = filteredTransactions.reduce((sum, transaction) => sum + transaction.amount, 0);
  const averageSpend = filteredTransactions.length === 0 ? 0 : totalSpent / filteredTransactions.length;
  const overBudgetCount = categorySummaries.filter((summary) => {
    const budget = dashboardState.budgets[summary.name];
    return typeof budget === "number" && budget > 0 && summary.total > budget;
  }).length;
  const budgetTotal = Object.values(dashboardState.budgets).reduce((sum, value) => sum + value, 0);
  const budgetRemaining = Math.max(budgetTotal - totalSpent, 0);

  async function handleLogout() {
    await logoutFromDashboard();
    onSignedOut();
  }

  function toggleCategory(name: string) {
    setSelectedCategories((current) => {
      const next = new Set(current);
      if (next.has(name) && next.size > 1) {
        next.delete(name);
      } else if (!next.has(name)) {
        next.add(name);
      }
      return next;
    });
  }

  function resetFilters() {
    setRangePreset("current-month");
    setCustomRange(undefined);
    setSelectedCategories(new Set(dashboardState.categories.map((category) => category.name)));
  }

  return (
    <div className="min-h-screen bg-secondary/40">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-5 sm:px-6">
          <div>
            <h1 className="text-2xl font-bold text-primary">BudgetFlow</h1>
            <p className="text-xs text-muted-foreground sm:text-sm">Your financial command center</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-sm text-muted-foreground lg:block">
              Signed in as <span className="font-medium text-foreground">{session.username}</span>
            </div>
            <Button size="sm" variant="outline">
              <Plus className="mr-2 h-4 w-4" />
              <span className="hidden sm:inline">Add Expense</span>
            </Button>
            <Button onClick={() => void handleLogout()} size="sm" variant="outline">
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {dashboardState.error ? (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {dashboardState.error}
          </div>
        ) : null}

        <Tabs className="space-y-6" defaultValue="overview">
          <TabsList className="grid w-full grid-cols-3 sm:inline-grid sm:w-auto">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="charts">Charts</TabsTrigger>
            <TabsTrigger value="budget">Budget</TabsTrigger>
          </TabsList>

          <TabsContent className="space-y-6" value="overview">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <StatCard
                icon={<Wallet className="h-5 w-5" />}
                label="This Month"
                sub={`${filteredTransactions.length} transactions`}
                trend="up"
                value={currency.format(totalSpent)}
              />
              <StatCard
                icon={<TrendingDown className="h-5 w-5" />}
                label="Average Spend"
                sub={analyticsCategorySelectionLabel(selectedCategories, dashboardState.categories)}
                trend="down"
                value={currency.format(averageSpend)}
              />
              <StatCard
                icon={<Target className="h-5 w-5" />}
                label="Budget Left"
                sub={`${overBudgetCount} over budget`}
                trend="down"
                value={currency.format(budgetRemaining)}
              />
              <StatCard
                icon={<Tags className="h-5 w-5" />}
                label="Categories"
                sub="Available filters"
                trend="down"
                value={`${dashboardState.categories.length}`}
              />
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Recent Transactions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                {dashboardState.loading ? (
                  <CenteredListMessage label="Loading transactions" />
                ) : newestTransactions.length === 0 ? (
                  <CenteredListMessage label="No transactions in this range" />
                ) : (
                  newestTransactions.slice(0, 8).map((transaction) => (
                    <div className="flex items-center justify-between border-b border-border py-3 last:border-0" key={transaction.id}>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{transaction.item}</p>
                        <p className="text-xs text-muted-foreground">
                          {transaction.category} · {format(transaction.timestamp, "MMM d")}
                        </p>
                      </div>
                      <p className="shrink-0 text-sm font-semibold">{currency.format(transaction.amount)}</p>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent className="space-y-6" value="charts">
            <AnalyticsFilters
              categories={dashboardState.categories}
              customRange={customRange}
              onCustomRangeChange={setCustomRange}
              onRangePresetChange={setRangePreset}
              onReset={resetFilters}
              onToggleCategory={toggleCategory}
              rangePreset={rangePreset}
              selectedCategories={selectedCategories}
            />

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Spending Trend</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-96 w-full">
                  {dashboardState.loading ? (
                    <CenteredChartMessage label="Loading analytics" />
                  ) : trend.length === 0 ? (
                    <CenteredChartMessage label="No transactions in this range" />
                  ) : (
                    <ResponsiveContainer>
                      <LineChart data={trend}>
                        <CartesianGrid stroke="oklch(0.92 0.01 95)" strokeDasharray="3 3" />
                        <XAxis dataKey="date" minTickGap={24} stroke="oklch(0.55 0.04 257)" />
                        <YAxis
                          stroke="oklch(0.55 0.04 257)"
                          tickFormatter={(value) => currency.format(Number(value))}
                          width={92}
                        />
                        <Tooltip
                          formatter={(value: number) => currency.format(value)}
                          contentStyle={{
                            borderRadius: 8,
                            border: "1px solid oklch(0.92 0.01 95)",
                          }}
                        />
                        <Line
                          activeDot={{ r: 5 }}
                          dataKey="total"
                          dot={{ r: 3, fill: "oklch(0.32 0.13 265)" }}
                          stroke="oklch(0.32 0.13 265)"
                          strokeWidth={2.5}
                          type="linear"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Top Categories</CardTitle>
                </CardHeader>
                <CardContent>
                  {categorySummaries.length === 0 ? (
                    <CenteredListMessage label="No category data available." />
                  ) : (
                    <div className="h-72 w-full">
                      <ResponsiveContainer>
                        <BarChart
                          data={categorySummaries.slice(0, 5).map((summary) => ({
                            name: summary.label,
                            total: Number(summary.total.toFixed(2)),
                          }))}
                          layout="vertical"
                          margin={{ left: 16, right: 20 }}
                        >
                          <CartesianGrid horizontal={false} stroke="oklch(0.92 0.01 95)" />
                          <XAxis
                            stroke="oklch(0.55 0.04 257)"
                            tickFormatter={(value) => currency.format(Number(value))}
                            type="number"
                          />
                          <YAxis dataKey="name" stroke="oklch(0.55 0.04 257)" type="category" width={120} />
                          <Tooltip
                            formatter={(value: number) => currency.format(value)}
                            contentStyle={{
                              borderRadius: 8,
                              border: "1px solid oklch(0.92 0.01 95)",
                            }}
                          />
                          <Bar dataKey="total" fill="oklch(0.65 0.18 254)" radius={[6, 6, 6, 6]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Budget Watch</CardTitle>
                </CardHeader>
                <CardContent className="space-y-5">
                  {dashboardState.categories.map((category) => {
                    const spent = categorySummaries.find((summary) => summary.name === category.name)?.total ?? 0;
                    const budget = dashboardState.budgets[category.name] ?? 0;
                    const progress = budget > 0 ? Math.min((spent / budget) * 100, 100) : 0;
                    const over = budget > 0 && spent > budget;

                    return (
                      <div className="space-y-2" key={category.name}>
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-medium">
                            {category.emoji} {category.name}
                          </p>
                          <p className={cn("shrink-0 text-sm font-semibold", over && "text-destructive")}>
                            {currency.format(spent)}
                            <span className="font-normal text-muted-foreground">
                              {budget > 0 ? ` / ${currency.format(budget)}` : ""}
                            </span>
                          </p>
                        </div>
                        <Progress className={over ? "[&>div]:bg-destructive" : "[&>div]:bg-accent"} value={progress} />
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent className="space-y-6" value="budget">
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard
                icon={<Target className="h-5 w-5" />}
                label="Total Budget"
                sub="Monthly limit"
                trend="down"
                value={currency.format(budgetTotal)}
              />
              <StatCard
                icon={<TrendingUp className="h-5 w-5" />}
                label="Spent"
                sub={`${budgetTotal > 0 ? Math.round((totalSpent / budgetTotal) * 100) : 0}% used`}
                trend="up"
                value={currency.format(totalSpent)}
              />
              <StatCard
                icon={<TrendingDown className="h-5 w-5" />}
                label="Remaining"
                sub={`${Math.max(dashboardState.categories.length - overBudgetCount, 0)} on track`}
                trend="down"
                value={currency.format(budgetRemaining)}
              />
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Budget by Category</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {dashboardState.categories.map((category) => {
                  const spent = categorySummaries.find((summary) => summary.name === category.name)?.total ?? 0;
                  const budget = dashboardState.budgets[category.name] ?? 0;
                  const progress = budget > 0 ? Math.min((spent / budget) * 100, 100) : 0;
                  const over = budget > 0 && spent > budget;

                  return (
                    <div className="space-y-2" key={category.name}>
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium">
                          {category.emoji} {category.name}
                        </p>
                        <p className={cn("shrink-0 text-sm font-semibold", over && "text-destructive")}>
                          {currency.format(spent)}
                          <span className="font-normal text-muted-foreground">
                            {budget > 0 ? ` / ${currency.format(budget)}` : ""}
                          </span>
                        </p>
                      </div>
                      <Progress className={over ? "[&>div]:bg-destructive" : "[&>div]:bg-accent"} value={progress} />
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

function AnalyticsFilters({
  categories,
  rangePreset,
  customRange,
  selectedCategories,
  onRangePresetChange,
  onCustomRangeChange,
  onToggleCategory,
  onReset,
}: {
  categories: DashboardCategory[];
  rangePreset: AnalyticsRangePreset;
  customRange: DateRange | undefined;
  selectedCategories: Set<string>;
  onRangePresetChange: (value: AnalyticsRangePreset) => void;
  onCustomRangeChange: (value: DateRange | undefined) => void;
  onToggleCategory: (name: string) => void;
  onReset: () => void;
}) {
  const customLabel =
    customRange?.from && customRange?.to
      ? `${format(customRange.from, "MMM d")} - ${format(customRange.to, "MMM d")}`
      : "Pick dates";

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 space-y-0 sm:flex-row sm:items-center sm:justify-between">
        <CardTitle className="text-lg">Spending Trend</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <Select onValueChange={(value) => onRangePresetChange(value as AnalyticsRangePreset)} value={rangePreset}>
            <SelectTrigger className="h-9 w-[170px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="current-month">Current Month</SelectItem>
              <SelectItem value="last-30-days">Last 30 Days</SelectItem>
              <SelectItem value="last-90-days">Last 90 Days</SelectItem>
              <SelectItem value="year-to-date">Year to Date</SelectItem>
              <SelectItem value="custom">Custom Range</SelectItem>
            </SelectContent>
          </Select>

          {rangePreset === "custom" ? (
            <Popover>
              <PopoverTrigger asChild>
                <Button className="h-9 justify-start text-left font-normal" size="sm" variant="outline">
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {customLabel}
                </Button>
              </PopoverTrigger>
              <PopoverContent align="start" className="w-auto p-0">
                <Calendar className="pointer-events-auto p-3" mode="range" numberOfMonths={2} onSelect={onCustomRangeChange} selected={customRange} />
              </PopoverContent>
            </Popover>
          ) : null}

          <Popover>
            <PopoverTrigger asChild>
              <Button className="h-9" size="sm" variant="outline">
                <Filter className="mr-2 h-4 w-4" />
                Categories ({selectedCategories.size}/{categories.length})
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-56">
              <div className="space-y-2">
                {categories.map((category) => (
                  <label className="flex cursor-pointer items-center gap-2 text-sm" key={category.name}>
                    <Checkbox
                      checked={selectedCategories.has(category.name)}
                      onCheckedChange={() => onToggleCategory(category.name)}
                    />
                    <span>{category.emoji} {category.name}</span>
                  </label>
                ))}
              </div>
            </PopoverContent>
          </Popover>

          <Button onClick={onReset} size="sm" variant="ghost">
            Reset
          </Button>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <p className="text-sm text-muted-foreground">
          {analyticsCategorySelectionLabel(selectedCategories, categories)} · {analyticsRangePresetLabel(rangePreset)}
        </p>
      </CardContent>
    </Card>
  );
}

function StatCard({
  icon,
  label,
  value,
  sub,
  trend,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  sub: string;
  trend?: "up" | "down";
}) {
  return (
    <Card className="border-border/60">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="mt-1 text-2xl font-bold text-foreground">{value}</p>
            <p className={cn("mt-1 text-xs", trend === "up" ? "text-destructive" : "text-accent")}>{sub}</p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10 text-accent">
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function CenteredState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-secondary/30 px-4">
      <Card className="w-full max-w-md border-border/70 bg-background/95">
        <CardContent className="flex flex-col items-center gap-4 p-10 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-foreground" />
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-foreground">{title}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{detail}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CenteredChartMessage({ label }: { label: string }) {
  return <div className="flex h-full items-center justify-center text-sm text-muted-foreground">{label}</div>;
}

function CenteredListMessage({ label }: { label: string }) {
  return <div className="py-16 text-center text-sm text-muted-foreground">{label}</div>;
}
