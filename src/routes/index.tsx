import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  Target,
  LogOut,
  Loader2,
  CalendarIcon,
  Filter,
  ListFilter,
  Pencil,
  Plus,
  Repeat2,
  Trash2,
} from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Calendar } from "@/components/ui/calendar";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { endOfDay, format, startOfDay, startOfMonth, startOfYear, subDays } from "date-fns";
import { cn } from "@/lib/utils";
import type { DateRange } from "react-day-picker";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  DashboardApiError,
  createDashboardTransaction,
  deleteDashboardBudget,
  deleteDashboardPlan,
  deleteDashboardTransaction,
  fetchDashboardBudgets,
  fetchDashboardCategories,
  fetchDashboardPlans,
  fetchDashboardPreferences,
  fetchDashboardSession,
  fetchDashboardTransactions,
  loginToDashboard,
  logoutFromDashboard,
  updateDashboardBudget,
  updateDashboardPreferences,
  updateDashboardPlan,
  updateDashboardTransaction,
  type DashboardCategory,
  type DashboardPaymentType,
  type DashboardPreferences,
  type DashboardPlan,
  type DashboardSession,
  type DashboardTransaction,
} from "@/lib/dashboard-api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "BudgetFlow - Expense Tracking & Budgeting Dashboard" },
      {
        name: "description",
        content:
          "Track daily, weekly, and monthly expenses, visualize spending trends, and stay on top of your budget.",
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
const HISTORY_START = new Date("1970-01-01T00:00:00+08:00");
const TRANSACTIONS_PAGE_SIZE = 25;

type DashboardTab = "overview" | "charts" | "budget" | "transactions" | "plans";
type RangeKey = "today" | "yesterday" | "weekly" | "current-month" | "30d" | "ytd" | "custom";
type TransactionSortKey =
  | "date-desc"
  | "date-asc"
  | "category-asc"
  | "category-desc"
  | "amount-desc"
  | "amount-asc";

function colorForCategory(index: number) {
  const hue = (index * 137.508) % 360;
  const lightness = [0.6, 0.68, 0.74][index % 3];
  const chroma = [0.2, 0.16, 0.13][index % 3];
  return `oklch(${lightness} ${chroma} ${hue})`;
}

function formatDateTimeInputValue(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hours = String(value.getHours()).padStart(2, "0");
  const minutes = String(value.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function getRange(key: RangeKey, custom?: DateRange): { from: Date; to: Date } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (key === "today") {
    return { from: startOfDay(today), to: endOfDay(today) };
  }
  if (key === "yesterday") {
    const yesterday = subDays(today, 1);
    return { from: startOfDay(yesterday), to: endOfDay(yesterday) };
  }
  if (key === "weekly") {
    return { from: startOfDay(subDays(today, 6)), to: endOfDay(today) };
  }
  if (key === "current-month") {
    return { from: startOfMonth(today), to: endOfDay(today) };
  }
  if (key === "30d") {
    return { from: startOfDay(subDays(today, 29)), to: endOfDay(today) };
  }
  if (key === "ytd") {
    return { from: startOfYear(today), to: endOfDay(today) };
  }
  const customFrom = custom?.from ? startOfDay(custom.from) : today;
  const customTo = custom?.to ? endOfDay(custom.to) : endOfDay(custom?.from ?? today);
  return { from: customFrom, to: customTo };
}

function buildFilledDailySeries(
  transactions: DashboardTransaction[],
  from: Date,
  to: Date,
  selectedCategories: string[],
) {
  const allowedCategories = new Set(selectedCategories);
  const perDay = new Map<string, number>();

  for (const transaction of transactions) {
    if (transaction.timestamp < from || transaction.timestamp > to) {
      continue;
    }
    if (!allowedCategories.has(transaction.category)) {
      continue;
    }
    const key = startOfDay(transaction.timestamp).toISOString();
    perDay.set(key, (perDay.get(key) ?? 0) + transaction.amount);
  }

  const series: { date: string; amount: number }[] = [];
  for (
    let cursor = startOfDay(from);
    cursor <= to;
    cursor = startOfDay(new Date(cursor.getTime() + 86400000))
  ) {
    const key = cursor.toISOString();
    series.push({
      date: format(cursor, "MMM d"),
      amount: Number((perDay.get(key) ?? 0).toFixed(2)),
    });
  }
  return series;
}

function sortTransactions(transactions: DashboardTransaction[], sortKey: TransactionSortKey) {
  return [...transactions].sort((left, right) => {
    switch (sortKey) {
      case "date-desc":
        return right.timestamp.getTime() - left.timestamp.getTime();
      case "date-asc":
        return left.timestamp.getTime() - right.timestamp.getTime();
      case "category-asc":
        return (
          left.category.localeCompare(right.category) ||
          right.timestamp.getTime() - left.timestamp.getTime()
        );
      case "category-desc":
        return (
          right.category.localeCompare(left.category) ||
          right.timestamp.getTime() - left.timestamp.getTime()
        );
      case "amount-desc":
        return right.amount - left.amount || right.timestamp.getTime() - left.timestamp.getTime();
      case "amount-asc":
        return left.amount - right.amount || right.timestamp.getTime() - left.timestamp.getTime();
    }
  });
}

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
        if (!active) return;
        setSessionState(session ? { status: "authenticated", session } : { status: "anonymous" });
      })
      .catch(() => {
        if (!active) return;
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
    return (
      <SignInScreen
        onSignedIn={(session) => setSessionState({ status: "authenticated", session })}
      />
    );
  }
  return (
    <DashboardShell
      session={sessionState.session}
      onSignedOut={() => setSessionState({ status: "anonymous" })}
    />
  );
}

function SignInScreen({ onSignedIn }: { onSignedIn: (session: DashboardSession) => void }) {
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
              <img alt="BudgetFlow" className="h-14 w-14 rounded-2xl" src="/logo.png" />
              <h1 className="mt-5 text-xl font-semibold tracking-tight text-primary">BudgetFlow</h1>
              <p className="mt-1 text-sm text-muted-foreground">Sign in to continue</p>
            </div>
            <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  autoComplete="username"
                  onChange={(e) => setUsername(e.target.value)}
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
                  onChange={(e) => setPassword(e.target.value)}
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [categories, setCategories] = useState<DashboardCategory[]>([]);
  const [budgets, setBudgets] = useState<Record<string, number>>({});
  const [transactions, setTransactions] = useState<DashboardTransaction[]>([]);
  const [plans, setPlans] = useState<DashboardPlan[]>([]);
  const [preferences, setPreferences] = useState<DashboardPreferences>({
    overviewVisibleCards: [],
  });

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    const now = new Date();
    void Promise.all([
      fetchDashboardCategories(),
      fetchDashboardBudgets(),
      fetchDashboardTransactions({ start: HISTORY_START, end: endOfDay(now) }),
      fetchDashboardPlans(),
      fetchDashboardPreferences(),
    ])
      .then(([cats, buds, txns, pls, prefs]) => {
        if (!active) return;
        setCategories(cats);
        setBudgets(buds);
        setTransactions(txns);
        setPlans(pls);
        setPreferences(prefs);
        setLoading(false);
      })
      .catch((caught) => {
        if (!active) return;
        const message =
          caught instanceof DashboardApiError && caught.status === 401
            ? "Session expired. Please sign in again."
            : caught instanceof Error
              ? caught.message
              : "Unable to load dashboard data.";
        setError(message);
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [session.chatId]);

  async function handleLogout() {
    await logoutFromDashboard();
    onSignedOut();
  }

  async function handleUpdateTransaction(
    transactionId: string,
    payload: {
      item: string;
      amount: number;
      category: string;
      timestamp: Date;
    },
  ) {
    await updateDashboardTransaction(transactionId, payload);
    setTransactions((current) =>
      current.map((transaction) =>
        transaction.id === transactionId ? { ...transaction, ...payload } : transaction,
      ),
    );
  }

  async function handleDeleteTransaction(transactionId: string) {
    await deleteDashboardTransaction(transactionId);
    setTransactions((current) => current.filter((transaction) => transaction.id !== transactionId));
  }

  async function handleCreateTransaction(payload: {
    item: string;
    amount: number;
    category: string;
    timestamp: Date;
    paymentType: DashboardPaymentType;
    dayOfMonth?: number;
    installmentCount?: number;
    createFirstTransactionNow?: boolean;
  }) {
    await createDashboardTransaction(payload);
    const end = endOfDay(new Date(Math.max(Date.now(), payload.timestamp.getTime())));
    const [txns, pls] = await Promise.all([
      fetchDashboardTransactions({ start: HISTORY_START, end }),
      fetchDashboardPlans(),
    ]);
    setTransactions(txns);
    setPlans(pls);
  }

  const refreshBudgets = useCallback(async () => {
    try {
      const buds = await fetchDashboardBudgets();
      setBudgets(buds);
    } catch {
      // silent — stale data remains visible
    }
  }, []);

  async function handleUpdatePlan(
    planId: string,
    payload: {
      item?: string;
      category?: string;
      dayOfMonth?: number;
      amount?: number;
      totalAmount?: number;
      installmentCount?: number;
    },
  ) {
    await updateDashboardPlan(planId, payload);
    setPlans(await fetchDashboardPlans());
  }

  async function handleDeletePlan(planId: string, mode: "future" | "all") {
    await deleteDashboardPlan(planId, mode);
    setPlans((current) => current.filter((plan) => plan.id !== planId));
  }

  async function handleUpdatePreferences(next: DashboardPreferences) {
    setPreferences(next);
    await updateDashboardPreferences({
      overviewVisibleCards: next.overviewVisibleCards,
    });
  }

  return (
    <DashboardLayout
      session={session}
      loading={loading}
      error={error}
      categories={categories}
      budgets={budgets}
      transactions={transactions}
      plans={plans}
      preferences={preferences}
      onDeleteTransaction={handleDeleteTransaction}
      onLogout={() => void handleLogout()}
      onUpdateTransaction={handleUpdateTransaction}
      onCreateTransaction={handleCreateTransaction}
      onRefreshBudgets={refreshBudgets}
      onUpdatePlan={handleUpdatePlan}
      onDeletePlan={handleDeletePlan}
      onUpdatePreferences={handleUpdatePreferences}
    />
  );
}

function DashboardLayout({
  session,
  loading,
  error,
  categories,
  budgets,
  transactions,
  plans,
  preferences,
  onDeleteTransaction,
  onLogout,
  onUpdateTransaction,
  onCreateTransaction,
  onRefreshBudgets,
  onUpdatePlan,
  onDeletePlan,
  onUpdatePreferences,
}: {
  session: DashboardSession;
  loading: boolean;
  error: string | null;
  categories: DashboardCategory[];
  budgets: Record<string, number>;
  transactions: DashboardTransaction[];
  plans: DashboardPlan[];
  preferences: DashboardPreferences;
  onDeleteTransaction: (transactionId: string) => Promise<void>;
  onLogout: () => void;
  onUpdateTransaction: (
    transactionId: string,
    payload: {
      item: string;
      amount: number;
      category: string;
      timestamp: Date;
    },
  ) => Promise<void>;
  onCreateTransaction: (payload: {
    item: string;
    amount: number;
    category: string;
    timestamp: Date;
    paymentType: DashboardPaymentType;
    dayOfMonth?: number;
    installmentCount?: number;
    createFirstTransactionNow?: boolean;
  }) => Promise<void>;
  onRefreshBudgets: () => Promise<void>;
  onUpdatePlan: (
    planId: string,
    payload: {
      item?: string;
      category?: string;
      dayOfMonth?: number;
      amount?: number;
      totalAmount?: number;
      installmentCount?: number;
    },
  ) => Promise<void>;
  onDeletePlan: (planId: string, mode: "future" | "all") => Promise<void>;
  onUpdatePreferences: (next: DashboardPreferences) => Promise<void>;
}) {
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const [visibleOverviewCards, setVisibleOverviewCards] = useState<string[]>([]);
  const [txnJump, setTxnJump] = useState<{ category: string; version: number } | null>(null);
  const [editingBudgetCategory, setEditingBudgetCategory] = useState<string | null>(null);
  const [editingBudgetAmount, setEditingBudgetAmount] = useState("");
  const [savingBudget, setSavingBudget] = useState(false);
  const [deletingBudgetCategory, setDeletingBudgetCategory] = useState<string | null>(null);
  const [budgetActionError, setBudgetActionError] = useState<string | null>(null);
  const [addTransactionOpen, setAddTransactionOpen] = useState(false);
  const [newItem, setNewItem] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [newAmount, setNewAmount] = useState("");
  const [newTimestamp, setNewTimestamp] = useState(formatDateTimeInputValue(new Date()));
  const [newPaymentType, setNewPaymentType] = useState<DashboardPaymentType>("one_time");
  const [newDayOfMonth, setNewDayOfMonth] = useState("");
  const [newInstallmentCount, setNewInstallmentCount] = useState("");
  const [createFirstTransactionNow, setCreateFirstTransactionNow] = useState(true);
  const [creatingTransaction, setCreatingTransaction] = useState(false);
  const [createTransactionError, setCreateTransactionError] = useState<string | null>(null);
  const [editingPlanId, setEditingPlanId] = useState<string | null>(null);
  const [planEditItem, setPlanEditItem] = useState("");
  const [planEditCategory, setPlanEditCategory] = useState("");
  const [planEditDay, setPlanEditDay] = useState("");
  const [planEditAmount, setPlanEditAmount] = useState("");
  const [planEditMonths, setPlanEditMonths] = useState("");
  const [savingPlanEdit, setSavingPlanEdit] = useState(false);
  const [planEditError, setPlanEditError] = useState<string | null>(null);

  const catColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    categories.forEach((category, index) => {
      map[category.name] = colorForCategory(index);
    });
    return map;
  }, [categories]);

  const monthSummaries = useMemo(() => {
    const now = new Date();
    const from = startOfMonth(now);
    const to = endOfDay(now);
    const summaries: Record<string, number> = {};
    transactions
      .filter((transaction) => transaction.timestamp >= from && transaction.timestamp <= to)
      .forEach((transaction) => {
        summaries[transaction.category] =
          (summaries[transaction.category] ?? 0) + transaction.amount;
      });
    return summaries;
  }, [transactions]);

  const monthTotal = Object.values(monthSummaries).reduce((sum, value) => sum + value, 0);
  const budgetTotal = Object.values(budgets).reduce((sum, value) => sum + value, 0);
  const budgetRemaining = Math.max(budgetTotal - monthTotal, 0);

  const recentTransactions = useMemo(
    () =>
      [...transactions]
        .sort((left, right) => right.timestamp.getTime() - left.timestamp.getTime())
        .slice(0, 5),
    [transactions],
  );

  const budgetRows = useMemo(
    () =>
      categories
        .map((category, index) => {
          const spent = monthSummaries[category.name] ?? 0;
          const budget = budgets[category.name] ?? 0;
          return {
            category,
            spent,
            budget,
            ratio: budget > 0 ? spent / budget : Number.NEGATIVE_INFINITY,
            index,
          };
        })
        .sort((left, right) => {
          const leftHasBudget = left.budget > 0;
          const rightHasBudget = right.budget > 0;
          if (leftHasBudget !== rightHasBudget) {
            return leftHasBudget ? -1 : 1;
          }
          if (leftHasBudget && rightHasBudget && left.ratio !== right.ratio) {
            return right.ratio - left.ratio;
          }
          return left.index - right.index;
        }),
    [categories, monthSummaries, budgets],
  );

  const pieData = useMemo(
    () =>
      categories
        .map((category) => ({
          name: `${category.emoji} ${category.name}`,
          value: Number((monthSummaries[category.name] ?? 0).toFixed(2)),
          color: catColorMap[category.name],
        }))
        .filter((entry) => entry.value > 0),
    [categories, monthSummaries, catColorMap],
  );

  const dailyData = useMemo(() => {
    const now = new Date();
    return Array.from({ length: 7 }, (_, index) => {
      const day = subDays(now, 6 - index);
      const from = startOfDay(day);
      const to = endOfDay(day);
      const amount = transactions
        .filter((transaction) => transaction.timestamp >= from && transaction.timestamp <= to)
        .reduce((sum, transaction) => sum + transaction.amount, 0);
      return { day: format(day, "EEE"), amount: Number(amount.toFixed(2)) };
    });
  }, [transactions]);

  useEffect(() => {
    setVisibleOverviewCards(preferences.overviewVisibleCards);
  }, [preferences]);

  const editingPlan = useMemo(
    () => plans.find((plan) => plan.id === editingPlanId) ?? null,
    [plans, editingPlanId],
  );

  function resetAddTransactionForm() {
    setNewItem("");
    setNewCategory(categories[0]?.name ?? "");
    setNewAmount("");
    setNewTimestamp(formatDateTimeInputValue(new Date()));
    setNewPaymentType("one_time");
    setNewDayOfMonth("");
    setNewInstallmentCount("");
    setCreateFirstTransactionNow(true);
    setCreateTransactionError(null);
  }

  function openAddTransactionDialog() {
    resetAddTransactionForm();
    setAddTransactionOpen(true);
  }

  function closeAddTransactionDialog() {
    if (creatingTransaction) return;
    setAddTransactionOpen(false);
    setCreateTransactionError(null);
  }

  async function handleOverviewVisibleCardsChange(next: string[]) {
    setVisibleOverviewCards(next);
    try {
      await onUpdatePreferences({ overviewVisibleCards: next });
    } catch {
      // keep optimistic state visible; next reload will reconcile if needed
    }
  }

  function openPlanEditDialog(plan: DashboardPlan) {
    setPlanEditError(null);
    setEditingPlanId(plan.id);
    setPlanEditItem(plan.item);
    setPlanEditCategory(plan.category);
    setPlanEditDay(String(plan.dayOfMonth));
    setPlanEditAmount(plan.planType === "recurring" ? String(plan.amount) : String(plan.totalAmount));
    setPlanEditMonths(plan.planType === "split_payment" ? String(plan.installmentCount) : "");
  }

  function openPlanEditById(planId: string) {
    const plan = plans.find((entry) => entry.id === planId);
    if (!plan || plan.status !== "active") {
      return false;
    }
    openPlanEditDialog(plan);
    return true;
  }

  function closePlanEditDialog() {
    if (savingPlanEdit) return;
    setEditingPlanId(null);
    setPlanEditError(null);
  }

  async function handleSavePlanEdit() {
    if (!editingPlan) return;
    const day = parseInt(planEditDay, 10);
    if (Number.isNaN(day) || day < 1 || day > 31) {
      setPlanEditError("Day must be between 1 and 31.");
      return;
    }
    if (!planEditItem.trim()) {
      setPlanEditError("Name cannot be empty.");
      return;
    }

    let amount: number | undefined;
    let totalAmount: number | undefined;
    let installmentCount: number | undefined;

    if (editingPlan.planType === "recurring") {
      amount = parseFloat(planEditAmount);
      if (Number.isNaN(amount) || amount <= 0) {
        setPlanEditError("Amount must be a positive number.");
        return;
      }
    } else {
      totalAmount = parseFloat(planEditAmount);
      installmentCount = parseInt(planEditMonths, 10);
      if (Number.isNaN(totalAmount) || totalAmount <= 0) {
        setPlanEditError("Total amount must be a positive number.");
        return;
      }
      if (Number.isNaN(installmentCount) || installmentCount < 1) {
        setPlanEditError("Months must be at least 1.");
        return;
      }
      if (installmentCount < editingPlan.currentInstallmentNumber) {
        setPlanEditError(
          `Months cannot be less than already posted installments (${editingPlan.currentInstallmentNumber}).`,
        );
        return;
      }
    }

    setSavingPlanEdit(true);
    setPlanEditError(null);
    try {
      await onUpdatePlan(editingPlan.id, {
        item: planEditItem.trim(),
        category: planEditCategory,
        dayOfMonth: day,
        ...(amount !== undefined ? { amount } : {}),
        ...(totalAmount !== undefined ? { totalAmount } : {}),
        ...(installmentCount !== undefined ? { installmentCount } : {}),
      });
      closePlanEditDialog();
    } catch (err) {
      setPlanEditError(err instanceof Error ? err.message : "Failed to update plan.");
    } finally {
      setSavingPlanEdit(false);
    }
  }

  function openEditBudget(categoryName: string, currentAmount: number) {
    setBudgetActionError(null);
    setEditingBudgetCategory(categoryName);
    setEditingBudgetAmount(currentAmount > 0 ? String(currentAmount) : "");
  }

  async function handleSaveBudgetEdit() {
    if (!editingBudgetCategory) return;
    const parsed = parseFloat(editingBudgetAmount);
    if (isNaN(parsed) || parsed <= 0) {
      setBudgetActionError("Enter a valid amount greater than 0.");
      return;
    }
    setSavingBudget(true);
    setBudgetActionError(null);
    try {
      await updateDashboardBudget(editingBudgetCategory, parsed);
      await onRefreshBudgets();
      setEditingBudgetCategory(null);
    } catch (err) {
      setBudgetActionError(err instanceof DashboardApiError ? err.message : "Failed to update budget.");
    } finally {
      setSavingBudget(false);
    }
  }

  async function handleCreateTransactionSubmit() {
    const item = newItem.trim();
    const category = newCategory.trim();
    const amount = Number(newAmount);
    const timestamp = new Date(newTimestamp);
    const needsPlanFields = newPaymentType !== "one_time";
    const dayOfMonth = needsPlanFields ? parseInt(newDayOfMonth, 10) : undefined;
    const installmentCount =
      newPaymentType === "split_payment" ? parseInt(newInstallmentCount, 10) : undefined;

    if (!item) {
      setCreateTransactionError("Item is required.");
      return;
    }
    if (!category) {
      setCreateTransactionError("Category is required.");
      return;
    }
    if (Number.isNaN(amount) || amount <= 0) {
      setCreateTransactionError(
        newPaymentType === "split_payment"
          ? "Total amount must be a positive number."
          : "Amount must be a positive number.",
      );
      return;
    }
    if (Number.isNaN(timestamp.getTime())) {
      setCreateTransactionError("Date is invalid.");
      return;
    }
    if (needsPlanFields && (dayOfMonth === undefined || Number.isNaN(dayOfMonth) || dayOfMonth < 1 || dayOfMonth > 31)) {
      setCreateTransactionError("Day of month must be between 1 and 31.");
      return;
    }
    if (
      newPaymentType === "split_payment" &&
      (installmentCount === undefined || Number.isNaN(installmentCount) || installmentCount < 1)
    ) {
      setCreateTransactionError("Number of months must be at least 1.");
      return;
    }

    setCreatingTransaction(true);
    setCreateTransactionError(null);
    try {
      await onCreateTransaction({
        item,
        amount,
        category,
        timestamp,
        paymentType: newPaymentType,
        ...(dayOfMonth !== undefined ? { dayOfMonth } : {}),
        ...(installmentCount !== undefined ? { installmentCount } : {}),
        ...(needsPlanFields ? { createFirstTransactionNow } : {}),
      });
      setAddTransactionOpen(false);
      resetAddTransactionForm();
    } catch (caught) {
      setCreateTransactionError(
        caught instanceof Error ? caught.message : "Unable to create transaction.",
      );
    } finally {
      setCreatingTransaction(false);
    }
  }

  async function handleDeleteBudgetClick(categoryName: string) {
    if (!window.confirm(`Remove budget for "${categoryName}"?`)) return;
    setDeletingBudgetCategory(categoryName);
    try {
      await deleteDashboardBudget(categoryName);
      await onRefreshBudgets();
    } finally {
      setDeletingBudgetCategory(null);
    }
  }

  return (
    <div className="min-h-screen bg-secondary/40">
      <header className="border-b border-border bg-background">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-primary">BudgetFlow</h1>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Your financial command center
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden lg:block text-sm text-muted-foreground">
              Signed in as <span className="font-medium text-foreground">{session.username}</span>
            </div>
            <Button onClick={onLogout} size="sm" variant="outline">
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {error ? (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <Tabs
          value={activeTab}
          onValueChange={(value) => setActiveTab(value as DashboardTab)}
          className="space-y-6"
        >
          <TabsList className="grid w-full grid-cols-3 sm:w-auto sm:grid-cols-5 sm:inline-grid">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="charts">Charts</TabsTrigger>
            <TabsTrigger value="budget">Budget</TabsTrigger>
            <TabsTrigger value="transactions">Transactions</TabsTrigger>
            <TabsTrigger value="plans">Plans</TabsTrigger>
          </TabsList>
          <div className="flex min-h-9 items-center justify-start gap-2">
            <div className="flex items-center gap-2">
              <Button onClick={openAddTransactionDialog} size="sm" className="shrink-0">
                <Plus className="mr-2 h-4 w-4" />
                Add Transaction
              </Button>
              {activeTab === "overview" ? (
                <OverviewInfoPopover
                  visible={visibleOverviewCards}
                  onVisibleChange={handleOverviewVisibleCardsChange}
                />
              ) : null}
            </div>
          </div>

          <TabsContent value="overview" className="space-y-6">
            <OverviewCards
              transactions={transactions}
              budgetTotal={budgetTotal}
              visible={visibleOverviewCards}
            />

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Recent Transactions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {loading ? (
                  <CenteredListMessage label="Loading transactions..." />
                ) : recentTransactions.length === 0 ? (
                  <CenteredListMessage label="No transactions found." />
                ) : (
                  <>
                    <div className="space-y-1">
                      {recentTransactions.map((transaction) => (
                        <div
                          key={transaction.id}
                          className="flex items-center justify-between py-3 border-b border-border last:border-0"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="h-9 w-9 rounded-full bg-secondary flex items-center justify-center shrink-0 text-base leading-none">
                              {categories.find((category) => category.name === transaction.category)
                                ?.emoji ?? "$"}
                            </div>
                            <div className="min-w-0">
                              <p className="font-medium text-sm truncate">{transaction.item}</p>
                              <p className="text-xs text-muted-foreground">
                                {transaction.category} - {format(transaction.timestamp, "MMM d")}
                              </p>
                            </div>
                          </div>
                          <p className="font-semibold text-sm shrink-0">
                            {currency.format(transaction.amount)}
                          </p>
                        </div>
                      ))}
                    </div>
                    <div className="flex justify-center">
                      <Button variant="ghost" onClick={() => setActiveTab("transactions")}>
                        Show all
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="charts" className="space-y-6">
            <TrendCard
              transactions={transactions}
              categories={categories}
              catColorMap={catColorMap}
              loading={loading}
            />

            <div className="grid lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Daily Spending (this week)</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-72 w-full">
                    {loading ? (
                      <CenteredChartMessage label="Loading..." />
                    ) : (
                      <ResponsiveContainer>
                        <BarChart data={dailyData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.92 0.01 256)" />
                          <XAxis dataKey="day" stroke="oklch(0.55 0.04 257)" fontSize={12} />
                          <YAxis
                            stroke="oklch(0.55 0.04 257)"
                            fontSize={12}
                            tickFormatter={(value) => currency.format(Number(value))}
                          />
                          <Tooltip
                            contentStyle={{
                              borderRadius: 8,
                              border: "1px solid oklch(0.92 0.01 256)",
                            }}
                            formatter={(value: number) => currency.format(value)}
                          />
                          <Bar dataKey="amount" fill="oklch(0.65 0.18 254)" radius={[6, 6, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </CardContent>
              </Card>

              <CategoryPieCard
                transactions={transactions}
                categories={categories}
                catColorMap={catColorMap}
                loading={loading}
              />
            </div>
          </TabsContent>

          <TabsContent value="budget" className="space-y-6">
            <div className="grid sm:grid-cols-3 gap-4">
              <StatCard
                label="Total Budget"
                value={currency.format(budgetTotal)}
                sub="Monthly limit"
                icon={Target}
                trend="down"
              />
              <StatCard
                label="Spent"
                value={currency.format(monthTotal)}
                sub={`${budgetTotal > 0 ? Math.round((monthTotal / budgetTotal) * 100) : 0}% used`}
                icon={Wallet}
                trend="up"
              />
              <StatCard
                label="Remaining"
                value={currency.format(budgetRemaining)}
                sub={`${Math.round((budgetRemaining / Math.max(budgetTotal, 1)) * 100)}% left`}
                icon={TrendingDown}
                trend="down"
              />
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Budget by Category</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {loading ? (
                  <CenteredListMessage label="Loading budget data..." />
                ) : categories.length === 0 ? (
                  <CenteredListMessage label="No categories found." />
                ) : (
                  budgetRows.map(({ category, spent, budget }) => {
                    const pct = budget > 0 ? Math.min((spent / budget) * 100, 100) : 0;
                    const over = budget > 0 && spent > budget;
                    return (
                      <div key={category.name} className="space-y-2">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-2 min-w-0">
                            <button
                              className="h-8 w-8 rounded-md bg-secondary flex items-center justify-center shrink-0 text-sm leading-none hover:bg-secondary/80 transition-colors cursor-pointer"
                              aria-label={`View ${category.name} transactions`}
                              onClick={() => {
                                setTxnJump({ category: category.name, version: Date.now() });
                                setActiveTab("transactions");
                              }}
                            >
                              {category.emoji}
                            </button>
                            <p className="font-medium text-sm">{category.name}</p>
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            <p
                              className={`text-sm font-semibold ${over ? "text-destructive" : "text-foreground"}`}
                            >
                              {currency.format(spent)}{" "}
                              <span className="text-muted-foreground font-normal">
                                {budget > 0 ? `/ ${currency.format(budget)}` : ""}
                              </span>
                            </p>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-7 w-7"
                              aria-label={`Edit budget for ${category.name}`}
                              onClick={() => openEditBudget(category.name, budget)}
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-7 w-7 text-destructive hover:text-destructive"
                              aria-label={`Delete budget for ${category.name}`}
                              disabled={deletingBudgetCategory === category.name}
                              onClick={() => void handleDeleteBudgetClick(category.name)}
                            >
                              {deletingBudgetCategory === category.name ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Trash2 className="h-3.5 w-3.5" />
                              )}
                            </Button>
                          </div>
                        </div>
                        <Progress
                          value={pct}
                          className={over ? "[&>div]:bg-destructive" : "[&>div]:bg-accent"}
                        />
                      </div>
                    );
                  })
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="transactions" className="space-y-6">
            <TransactionsTab
              transactions={transactions}
              categories={categories}
              catColorMap={catColorMap}
              loading={loading}
              onDeleteTransaction={onDeleteTransaction}
              onUpdateTransaction={onUpdateTransaction}
              onEditPlanTransaction={openPlanEditById}
              jump={txnJump}
            />
          </TabsContent>

          <TabsContent value="plans" className="space-y-6">
            <PlansTab
              plans={plans}
              categories={categories}
              loading={loading}
              onEditPlan={openPlanEditDialog}
              onDeletePlan={onDeletePlan}
            />
          </TabsContent>
        </Tabs>

        <Dialog
          open={addTransactionOpen}
          onOpenChange={(open) => {
            if (!open) {
              closeAddTransactionDialog();
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Transaction</DialogTitle>
              <DialogDescription>
                Create a one-time expense or set up a recurring or split payment plan.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="new-item">Item</Label>
                <Input
                  id="new-item"
                  value={newItem}
                  onChange={(e) => setNewItem(e.target.value)}
                  disabled={creatingTransaction}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-category">Category</Label>
                <Select
                  value={newCategory}
                  onValueChange={setNewCategory}
                  disabled={creatingTransaction}
                >
                  <SelectTrigger id="new-category">
                    <SelectValue placeholder="Select a category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((category) => (
                      <SelectItem key={category.name} value={category.name}>
                        {category.emoji} {category.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-payment-type">Payment Type</Label>
                <Select
                  value={newPaymentType}
                  onValueChange={(value) => setNewPaymentType(value as DashboardPaymentType)}
                  disabled={creatingTransaction}
                >
                  <SelectTrigger id="new-payment-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="one_time">One-time</SelectItem>
                    <SelectItem value="split_payment">Split payment</SelectItem>
                    <SelectItem value="recurring">Recurring</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-amount">
                  {newPaymentType === "split_payment" ? "Total Amount" : "Amount"}
                </Label>
                <Input
                  id="new-amount"
                  type="number"
                  inputMode="decimal"
                  min="0.01"
                  step="0.01"
                  value={newAmount}
                  onChange={(e) => setNewAmount(e.target.value)}
                  disabled={creatingTransaction}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-date">Date</Label>
                <Input
                  id="new-date"
                  type="datetime-local"
                  value={newTimestamp}
                  onChange={(e) => setNewTimestamp(e.target.value)}
                  disabled={creatingTransaction}
                />
              </div>
              {newPaymentType !== "one_time" ? (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="new-day-of-month">Monthly Charge Day</Label>
                    <Input
                      id="new-day-of-month"
                      type="number"
                      inputMode="numeric"
                      min="1"
                      max="31"
                      value={newDayOfMonth}
                      onChange={(e) => setNewDayOfMonth(e.target.value)}
                      disabled={creatingTransaction}
                    />
                  </div>
                  {newPaymentType === "split_payment" ? (
                    <div className="space-y-2">
                      <Label htmlFor="new-installment-count">Number of Months</Label>
                      <Input
                        id="new-installment-count"
                        type="number"
                        inputMode="numeric"
                        min="1"
                        step="1"
                        value={newInstallmentCount}
                        onChange={(e) => setNewInstallmentCount(e.target.value)}
                        disabled={creatingTransaction}
                      />
                    </div>
                  ) : null}
                  <div className="rounded-xl border border-border/70 bg-secondary/30 px-4 py-3">
                    <label className="flex items-start gap-3 text-sm">
                      <Checkbox
                        checked={createFirstTransactionNow}
                        onCheckedChange={(checked) => setCreateFirstTransactionNow(!!checked)}
                        disabled={creatingTransaction}
                      />
                      <span className="leading-5 text-muted-foreground">
                        Create the first transaction now.
                        <span className="block">
                          If unchecked, only the plan is created and the first charge will post on
                          the next assigned monthly day.
                        </span>
                      </span>
                    </label>
                  </div>
                </>
              ) : null}
              {createTransactionError ? (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {createTransactionError}
                </div>
              ) : null}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={closeAddTransactionDialog}
                disabled={creatingTransaction}
              >
                Cancel
              </Button>
              <Button
                onClick={() => void handleCreateTransactionSubmit()}
                disabled={creatingTransaction}
              >
                {creatingTransaction ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog
          open={editingPlan !== null}
          onOpenChange={(open) => {
            if (!open) {
              closePlanEditDialog();
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit plan</DialogTitle>
              <DialogDescription>
                {editingPlan?.planType === "split_payment"
                  ? "Update name, category, day, total amount, or number of months."
                  : "Update name, category, day, or amount."}
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-2">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input
                  value={planEditItem}
                  onChange={(e) => setPlanEditItem(e.target.value)}
                  disabled={savingPlanEdit}
                />
              </div>
              <div className="space-y-2">
                <Label>Category</Label>
                <Select
                  value={planEditCategory}
                  onValueChange={setPlanEditCategory}
                  disabled={savingPlanEdit}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((category) => (
                      <SelectItem key={category.name} value={category.name}>
                        {category.emoji} {category.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Day of Month</Label>
                <Input
                  type="number"
                  inputMode="numeric"
                  min="1"
                  max="31"
                  value={planEditDay}
                  onChange={(e) => setPlanEditDay(e.target.value)}
                  disabled={savingPlanEdit}
                />
              </div>
              {editingPlan?.planType === "recurring" ? (
                <div className="space-y-2">
                  <Label>Monthly Amount</Label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    min="0.01"
                    step="0.01"
                    value={planEditAmount}
                    onChange={(e) => setPlanEditAmount(e.target.value)}
                    disabled={savingPlanEdit}
                  />
                </div>
              ) : editingPlan ? (
                <>
                  <div className="space-y-2">
                    <Label>Total Amount</Label>
                    <Input
                      type="number"
                      inputMode="decimal"
                      min="0.01"
                      step="0.01"
                      value={planEditAmount}
                      onChange={(e) => setPlanEditAmount(e.target.value)}
                      disabled={savingPlanEdit}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Months</Label>
                    <Input
                      type="number"
                      inputMode="numeric"
                      min={Math.max(1, editingPlan.currentInstallmentNumber)}
                      step="1"
                      value={planEditMonths}
                      onChange={(e) => setPlanEditMonths(e.target.value)}
                      disabled={savingPlanEdit}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Saving a split-plan edit recalculates the schedule and rewrites this plan&apos;s
                    auto-generated charges to stay consistent.
                  </p>
                </>
              ) : null}
              {planEditError ? (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {planEditError}
                </div>
              ) : null}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={closePlanEditDialog}
                disabled={savingPlanEdit}
              >
                Cancel
              </Button>
              <Button onClick={() => void handleSavePlanEdit()} disabled={savingPlanEdit}>
                {savingPlanEdit ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Save
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog
          open={editingBudgetCategory !== null}
          onOpenChange={(open) => {
            if (!open && !savingBudget) setEditingBudgetCategory(null);
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                Edit Budget
                {editingBudgetCategory
                  ? ` — ${categories.find((c) => c.name === editingBudgetCategory)?.emoji ?? ""} ${editingBudgetCategory}`
                  : ""}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              {budgetActionError && <p className="text-sm text-destructive">{budgetActionError}</p>}
              <div className="space-y-2">
                <Label>Budget Amount</Label>
                <Input
                  type="number"
                  inputMode="decimal"
                  min="0.01"
                  step="0.01"
                  value={editingBudgetAmount}
                  onChange={(e) => setEditingBudgetAmount(e.target.value)}
                  disabled={savingBudget}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setEditingBudgetCategory(null)}
                disabled={savingBudget}
              >
                Cancel
              </Button>
              <Button onClick={() => void handleSaveBudgetEdit()} disabled={savingBudget}>
                {savingBudget ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Saving…
                  </>
                ) : (
                  "Save"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}

function OverviewCards({
  transactions,
  budgetTotal,
  visible,
}: {
  transactions: DashboardTransaction[];
  budgetTotal: number;
  visible: string[];
}) {
  const stats = useMemo(() => {
    const now = new Date();
    const end = endOfDay(now);
    const sumFrom = (from: Date) =>
      transactions
        .filter((transaction) => transaction.timestamp >= from && transaction.timestamp <= end)
        .reduce((sum, transaction) => sum + transaction.amount, 0);
    const monthTotal = sumFrom(startOfMonth(now));
    const remaining = Math.max(budgetTotal - monthTotal, 0);
    return {
      todayTotal: sumFrom(startOfDay(now)),
      weekTotal: sumFrom(startOfDay(subDays(now, 6))),
      monthTotal,
      d30Total: sumFrom(startOfDay(subDays(now, 29))),
      d90Total: sumFrom(startOfDay(subDays(now, 89))),
      ytdTotal: sumFrom(startOfYear(now)),
      remaining,
    };
  }, [transactions, budgetTotal]);

  const statCards = [
    {
      key: "today",
      label: "Today",
      value: currency.format(stats.todayTotal),
      sub: "Spent today",
      icon: Wallet,
      trend: "up" as const,
    },
    {
      key: "week",
      label: "This Week",
      value: currency.format(stats.weekTotal),
      sub: "Last 7 days",
      icon: TrendingDown,
      trend: "down" as const,
    },
    {
      key: "month",
      label: "This Month",
      value: currency.format(stats.monthTotal),
      sub: "Current month",
      icon: TrendingUp,
      trend: "up" as const,
    },
    {
      key: "budget",
      label: "Budget Left",
      value: currency.format(stats.remaining),
      sub:
        budgetTotal > 0
          ? `${Math.round((stats.remaining / budgetTotal) * 100)}% left`
          : "No budget set",
      icon: Target,
      trend: "down" as const,
    },
    {
      key: "30d",
      label: "Last 30 Days",
      value: currency.format(stats.d30Total),
      sub: "Rolling 30 days",
      icon: TrendingDown,
      trend: "down" as const,
    },
    {
      key: "90d",
      label: "Last 90 Days",
      value: currency.format(stats.d90Total),
      sub: "Rolling 90 days",
      icon: TrendingUp,
      trend: "up" as const,
    },
    {
      key: "ytd",
      label: "Year to Date",
      value: currency.format(stats.ytdTotal),
      sub: "This year",
      icon: TrendingUp,
      trend: "up" as const,
    },
  ];

  const cards = statCards.filter((card) => visible.includes(card.key));

  return (
    <div className="space-y-5">
      {cards.length > 0 ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {cards.map((card) => (
            <StatCard
              key={card.key}
              label={card.label}
              value={card.value}
              sub={card.sub}
              icon={card.icon}
              trend={card.trend}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground text-center py-8">No cards selected.</p>
      )}
    </div>
  );
}

function OverviewInfoPopover({
  visible,
  onVisibleChange,
}: {
  visible: string[];
  onVisibleChange: (value: string[]) => void | Promise<void>;
}) {
  const statCards = [
    { key: "today", label: "Today" },
    { key: "week", label: "This Week" },
    { key: "month", label: "This Month" },
    { key: "budget", label: "Budget Left" },
    { key: "30d", label: "Last 30 Days" },
    { key: "90d", label: "Last 90 Days" },
    { key: "ytd", label: "Year to Date" },
  ];

  const toggle = (key: string) =>
    onVisibleChange(
      visible.includes(key) ? visible.filter((value) => value !== key) : [...visible, key],
    );

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-9 text-left">
          <Filter className="mr-2 h-4 w-4" />
          Show
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56" align="start">
        <div className="space-y-2">
          {statCards.map((card) => (
            <label key={card.key} className="flex items-center gap-2 text-sm cursor-pointer">
              <Checkbox
                checked={visible.includes(card.key)}
                onCheckedChange={() => toggle(card.key)}
              />
              {card.label}
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function CategoryPieCard({
  transactions,
  categories,
  catColorMap,
  loading,
}: {
  transactions: DashboardTransaction[];
  categories: DashboardCategory[];
  catColorMap: Record<string, string>;
  loading: boolean;
}) {
  const [rangeKey, setRangeKey] = useState<RangeKey>("current-month");
  const [custom, setCustom] = useState<DateRange | undefined>();

  const { from, to } = useMemo(() => getRange(rangeKey, custom), [rangeKey, custom]);

  const pieData = useMemo(() => {
    const summaries: Record<string, number> = {};
    transactions
      .filter((tx) => tx.timestamp >= from && tx.timestamp <= to)
      .forEach((tx) => {
        summaries[tx.category] = (summaries[tx.category] ?? 0) + tx.amount;
      });
    return categories
      .map((cat) => ({
        name: `${cat.emoji} ${cat.name}`,
        value: Number((summaries[cat.name] ?? 0).toFixed(2)),
        color: catColorMap[cat.name],
      }))
      .filter((entry) => entry.value > 0);
  }, [transactions, categories, catColorMap, from, to]);

  const total = pieData.reduce((sum, entry) => sum + entry.value, 0);

  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 space-y-0">
        <CardTitle className="text-lg">By Category</CardTitle>
        <RangeSelector
          rangeKey={rangeKey}
          custom={custom}
          onRangeKeyChange={setRangeKey}
          onCustomChange={setCustom}
        />
      </CardHeader>
      <CardContent>
        <div className="h-80 w-full">
          {loading ? (
            <CenteredChartMessage label="Loading..." />
          ) : pieData.length === 0 ? (
            <CenteredChartMessage label="No data for this period." />
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={50}
                  outerRadius={85}
                  paddingAngle={2}
                >
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: "1px solid oklch(0.92 0.01 256)" }}
                  formatter={(value: number) => currency.format(value)}
                />
                <Legend
                  layout="horizontal"
                  align="center"
                  verticalAlign="bottom"
                  wrapperStyle={{ fontSize: 12, paddingTop: 12 }}
                  formatter={(value, entry: { payload?: { value?: number } }) => (
                    <span className="text-foreground">
                      {value}{" "}
                      <span className="text-muted-foreground">
                        {Math.round(((entry?.payload?.value ?? 0) / Math.max(total, 1)) * 100)}%
                      </span>
                    </span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function TrendCard({
  transactions,
  categories,
  catColorMap,
  loading,
}: {
  transactions: DashboardTransaction[];
  categories: DashboardCategory[];
  catColorMap: Record<string, string>;
  loading: boolean;
}) {
  const [rangeKey, setRangeKey] = useState<RangeKey>("current-month");
  const [custom, setCustom] = useState<DateRange | undefined>();
  const [selected, setSelected] = useState<string[]>([]);
  const [isAllMode, setIsAllMode] = useState(true);

  useEffect(() => {
    setSelected(categories.map((category) => category.name));
    setIsAllMode(true);
  }, [categories]);

  const { from, to } = useMemo(() => getRange(rangeKey, custom), [rangeKey, custom]);

  const data = useMemo(
    () => buildFilledDailySeries(transactions, from, to, selected),
    [transactions, from, to, selected],
  );

  const toggleCategory = (categoryName: string) => {
    setSelected((prev) =>
      prev.includes(categoryName)
        ? prev.filter((value) => value !== categoryName)
        : [...prev, categoryName],
    );
  };

  const toggleAll = (all: boolean) => {
    if (all) {
      setSelected(categories.map((c) => c.name));
      setIsAllMode(true);
    } else {
      setSelected([]);
      setIsAllMode(false);
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 space-y-0">
        <CardTitle className="text-lg">Spending Trend</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <RangeSelector
            rangeKey={rangeKey}
            custom={custom}
            onRangeKeyChange={setRangeKey}
            onCustomChange={setCustom}
          />
          <CategoryFilterPopover
            categories={categories}
            selected={selected}
            catColorMap={catColorMap}
            onToggle={toggleCategory}
            isAllMode={isAllMode}
            onToggleAll={toggleAll}
          />
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-96 w-full">
          {loading ? (
            <CenteredChartMessage label="Loading trend data..." />
          ) : selected.length === 0 ? (
            <CenteredChartMessage label="Select at least one category." />
          ) : (
            <ResponsiveContainer>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.92 0.01 256)" />
                <XAxis dataKey="date" stroke="oklch(0.55 0.04 257)" fontSize={12} minTickGap={24} />
                <YAxis
                  stroke="oklch(0.55 0.04 257)"
                  fontSize={12}
                  tickFormatter={(value) => currency.format(Number(value))}
                />
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: "1px solid oklch(0.92 0.01 256)" }}
                  formatter={(value: number) => currency.format(value)}
                />
                <Line
                  type="linear"
                  dataKey="amount"
                  stroke="oklch(0.32 0.13 265)"
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: "oklch(0.32 0.13 265)" }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function TransactionsTab({
  transactions,
  categories,
  catColorMap,
  loading,
  onDeleteTransaction,
  onUpdateTransaction,
  onEditPlanTransaction,
  jump,
}: {
  transactions: DashboardTransaction[];
  categories: DashboardCategory[];
  catColorMap: Record<string, string>;
  loading: boolean;
  onDeleteTransaction: (transactionId: string) => Promise<void>;
  onUpdateTransaction: (
    transactionId: string,
    payload: {
      item: string;
      amount: number;
      category: string;
      timestamp: Date;
    },
  ) => Promise<void>;
  onEditPlanTransaction: (planId: string) => boolean;
  jump?: { category: string; version: number } | null;
}) {
  const [rangeKey, setRangeKey] = useState<RangeKey>("current-month");
  const [custom, setCustom] = useState<DateRange | undefined>();
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [isCategoryAllMode, setIsCategoryAllMode] = useState(true);
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [sortKey, setSortKey] = useState<TransactionSortKey>("date-desc");
  const [page, setPage] = useState(1);
  const [editingTransactionId, setEditingTransactionId] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState("");
  const [editingAmount, setEditingAmount] = useState("");
  const [editingCategory, setEditingCategory] = useState("");
  const [editingTimestamp, setEditingTimestamp] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [savingTransaction, setSavingTransaction] = useState(false);
  const [deletingTransactionId, setDeletingTransactionId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedCategories(categories.map((category) => category.name));
    setIsCategoryAllMode(true);
  }, [categories]);

  useEffect(() => {
    if (!jump) return;
    setRangeKey("current-month");
    setCustom(undefined);
    setSelectedCategories([jump.category]);
    setIsCategoryAllMode(false);
  }, [jump]);

  const { from, to } = useMemo(() => getRange(rangeKey, custom), [rangeKey, custom]);
  const minValue = minAmount.trim() === "" ? null : Number(minAmount);
  const maxValue = maxAmount.trim() === "" ? null : Number(maxAmount);

  const filteredTransactions = useMemo(() => {
    const selectedSet = new Set(selectedCategories);
    const filtered = transactions.filter((transaction) => {
      if (transaction.timestamp < from || transaction.timestamp > to) {
        return false;
      }
      if (!selectedSet.has(transaction.category)) {
        return false;
      }
      if (minValue !== null && !Number.isNaN(minValue) && transaction.amount < minValue) {
        return false;
      }
      if (maxValue !== null && !Number.isNaN(maxValue) && transaction.amount > maxValue) {
        return false;
      }
      return true;
    });
    return sortTransactions(filtered, sortKey);
  }, [transactions, from, to, selectedCategories, minValue, maxValue, sortKey]);

  useEffect(() => {
    setPage(1);
  }, [rangeKey, custom, selectedCategories, minAmount, maxAmount, sortKey]);

  const totalPages = Math.max(1, Math.ceil(filteredTransactions.length / TRANSACTIONS_PAGE_SIZE));

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const pageRows = useMemo(() => {
    const startIndex = (page - 1) * TRANSACTIONS_PAGE_SIZE;
    return filteredTransactions.slice(startIndex, startIndex + TRANSACTIONS_PAGE_SIZE);
  }, [filteredTransactions, page]);

  const editingTransaction = useMemo(
    () => transactions.find((transaction) => transaction.id === editingTransactionId) ?? null,
    [transactions, editingTransactionId],
  );

  const toggleCategory = (categoryName: string) => {
    setSelectedCategories((prev) =>
      prev.includes(categoryName)
        ? prev.filter((value) => value !== categoryName)
        : [...prev, categoryName],
    );
  };

  const toggleAllCategories = (all: boolean) => {
    if (all) {
      setSelectedCategories(categories.map((c) => c.name));
      setIsCategoryAllMode(true);
    } else {
      setSelectedCategories([]);
      setIsCategoryAllMode(false);
    }
  };

  function openEditDialog(transaction: DashboardTransaction) {
    setActionError(null);
    if (
      (transaction.sourceType === "recurring" || transaction.sourceType === "split_payment") &&
      transaction.sourcePlanId
    ) {
      if (!onEditPlanTransaction(transaction.sourcePlanId)) {
        setActionError("Linked plan not found.");
      }
      return;
    }
    setEditingTransactionId(transaction.id);
    setEditingItem(transaction.item);
    setEditingAmount(String(transaction.amount));
    setEditingCategory(transaction.category);
    setEditingTimestamp(formatDateTimeInputValue(transaction.timestamp));
  }

  function closeEditDialog() {
    if (savingTransaction) {
      return;
    }
    setEditingTransactionId(null);
    setEditingItem("");
    setEditingAmount("");
    setEditingCategory("");
    setEditingTimestamp("");
    setActionError(null);
  }

  async function handleSaveTransactionEdit() {
    if (!editingTransactionId) {
      return;
    }

    const amount = Number(editingAmount);
    const timestamp = new Date(editingTimestamp);

    if (!editingItem.trim()) {
      setActionError("Item name cannot be empty.");
      return;
    }
    if (!editingCategory.trim()) {
      setActionError("Category is required.");
      return;
    }
    if (Number.isNaN(amount) || amount <= 0) {
      setActionError("Amount must be a positive number.");
      return;
    }
    if (Number.isNaN(timestamp.getTime())) {
      setActionError("Date is invalid.");
      return;
    }

    setSavingTransaction(true);
    setActionError(null);
    try {
      await onUpdateTransaction(editingTransactionId, {
        item: editingItem.trim(),
        amount,
        category: editingCategory,
        timestamp,
      });
      closeEditDialog();
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Unable to update transaction.");
    } finally {
      setSavingTransaction(false);
    }
  }

  async function handleDeleteTransactionClick(transaction: DashboardTransaction) {
    const confirmed = window.confirm(`Delete "${transaction.item}"?`);
    if (!confirmed) {
      return;
    }
    setDeletingTransactionId(transaction.id);
    setActionError(null);
    try {
      await onDeleteTransaction(transaction.id);
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Unable to delete transaction.");
    } finally {
      setDeletingTransactionId(null);
    }
  }

  return (
    <>
      <Card>
        <CardHeader className="space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle className="text-lg">All Transactions</CardTitle>
              {!loading && (
                <p className="text-sm text-muted-foreground mt-0.5">
                  {filteredTransactions.length} transaction{filteredTransactions.length !== 1 ? "s" : ""} &middot;{" "}
                  <span className="font-semibold text-foreground">
                    {currency.format(filteredTransactions.reduce((sum, tx) => sum + tx.amount, 0))}
                  </span>
                </p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5">
                <span className="text-sm text-muted-foreground">Min</span>
                <Input
                  id="min-amount"
                  className="h-8 w-14 self-center border-0 px-0 text-sm leading-none shadow-none [appearance:textfield] focus-visible:ring-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                  inputMode="decimal"
                  onChange={(event) => setMinAmount(event.target.value)}
                  placeholder="0.00"
                  type="number"
                  value={minAmount}
                />
                <span className="text-sm text-muted-foreground">-</span>
                <span className="text-sm text-muted-foreground">Max</span>
                <Input
                  id="max-amount"
                  className="h-8 w-14 self-center border-0 px-0 text-sm leading-none shadow-none [appearance:textfield] focus-visible:ring-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                  inputMode="decimal"
                  onChange={(event) => setMaxAmount(event.target.value)}
                  placeholder="Limit"
                  type="number"
                  value={maxAmount}
                />
              </div>
              <RangeSelector
                rangeKey={rangeKey}
                custom={custom}
                onRangeKeyChange={setRangeKey}
                onCustomChange={setCustom}
              />
              <CategoryFilterPopover
                categories={categories}
                selected={selectedCategories}
                catColorMap={catColorMap}
                onToggle={toggleCategory}
                isAllMode={isCategoryAllMode}
                onToggleAll={toggleAllCategories}
              />
              <Select
                value={sortKey}
                onValueChange={(value) => setSortKey(value as TransactionSortKey)}
              >
                <SelectTrigger className="h-9 w-[112px] px-3">
                  <div className="flex items-center gap-2 pr-4">
                    <ListFilter className="h-4 w-4" />
                    <span>Sort</span>
                  </div>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="date-desc">Date (Newest)</SelectItem>
                  <SelectItem value="date-asc">Date (Oldest)</SelectItem>
                  <SelectItem value="category-asc">Category (A-Z)</SelectItem>
                  <SelectItem value="category-desc">Category (Z-A)</SelectItem>
                  <SelectItem value="amount-desc">Amount (High-Low)</SelectItem>
                  <SelectItem value="amount-asc">Amount (Low-High)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {actionError ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {actionError}
            </div>
          ) : null}
          {loading ? (
            <CenteredListMessage label="Loading transactions..." />
          ) : pageRows.length === 0 ? (
            <CenteredListMessage label="No transactions found for the selected filters." />
          ) : (
            <>
              <div className="rounded-xl border border-border/70">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[120px]">Date</TableHead>
                      <TableHead>Item</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead className="w-[96px] text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pageRows.map((transaction) => (
                      <TableRow key={transaction.id}>
                        <TableCell className="whitespace-nowrap">
                          {format(transaction.timestamp, "MMM d, yyyy")}
                        </TableCell>
                        <TableCell className="font-medium">{transaction.item}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span
                              className="h-2.5 w-2.5 rounded-sm shrink-0"
                              style={{
                                background:
                                  catColorMap[transaction.category] ?? colorForCategory(0),
                              }}
                            />
                            <span className="truncate">
                              {categories.find((category) => category.name === transaction.category)
                                ?.emoji ?? "$"}{" "}
                              {transaction.category}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right font-semibold">
                          {currency.format(transaction.amount)}
                        </TableCell>
                        <TableCell>
                          <div className="flex justify-end gap-1">
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8"
                              aria-label={`Edit ${transaction.item}`}
                              onClick={() => openEditDialog(transaction)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8 text-destructive hover:text-destructive"
                              aria-label={`Delete ${transaction.item}`}
                              disabled={deletingTransactionId === transaction.id}
                              onClick={() => void handleDeleteTransactionClick(transaction)}
                            >
                              {deletingTransactionId === transaction.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-muted-foreground">
                  Showing {(page - 1) * TRANSACTIONS_PAGE_SIZE + 1}-
                  {Math.min(page * TRANSACTIONS_PAGE_SIZE, filteredTransactions.length)} of{" "}
                  {filteredTransactions.length}
                </p>
                <Pagination className="mx-0 w-auto justify-end">
                  <PaginationContent>
                    <PaginationItem>
                      <PaginationPrevious
                        href="#"
                        aria-disabled={page === 1}
                        className={page === 1 ? "pointer-events-none opacity-50" : ""}
                        onClick={(event) => {
                          event.preventDefault();
                          if (page > 1) {
                            setPage(page - 1);
                          }
                        }}
                      />
                    </PaginationItem>
                    <PaginationItem>
                      <span className="px-3 text-sm text-muted-foreground">
                        Page {page} of {totalPages}
                      </span>
                    </PaginationItem>
                    <PaginationItem>
                      <PaginationNext
                        href="#"
                        aria-disabled={page === totalPages}
                        className={page === totalPages ? "pointer-events-none opacity-50" : ""}
                        onClick={(event) => {
                          event.preventDefault();
                          if (page < totalPages) {
                            setPage(page + 1);
                          }
                        }}
                      />
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={editingTransaction !== null}
        onOpenChange={(open) => {
          if (!open) {
            closeEditDialog();
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit transaction</DialogTitle>
            <DialogDescription>Update the item, category, amount, and date.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="edit-item">Item</Label>
              <Input
                id="edit-item"
                value={editingItem}
                onChange={(event) => setEditingItem(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-category">Category</Label>
              <Select value={editingCategory} onValueChange={setEditingCategory}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a category" />
                </SelectTrigger>
                <SelectContent>
                  {categories.map((category) => (
                    <SelectItem key={category.name} value={category.name}>
                      {category.emoji} {category.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-amount">Amount</Label>
              <Input
                id="edit-amount"
                type="number"
                inputMode="decimal"
                value={editingAmount}
                onChange={(event) => setEditingAmount(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-date">Date</Label>
              <Input
                id="edit-date"
                type="datetime-local"
                value={editingTimestamp}
                onChange={(event) => setEditingTimestamp(event.target.value)}
              />
            </div>
            {actionError ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {actionError}
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeEditDialog} disabled={savingTransaction}>
              Cancel
            </Button>
            <Button onClick={() => void handleSaveTransactionEdit()} disabled={savingTransaction}>
              {savingTransaction ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function PlansTab({
  plans,
  categories,
  loading,
  onEditPlan,
  onDeletePlan,
}: {
  plans: DashboardPlan[];
  categories: DashboardCategory[];
  loading: boolean;
  onEditPlan: (plan: DashboardPlan) => void;
  onDeletePlan: (planId: string, mode: "future" | "all") => Promise<void>;
}) {
  const [deletingPlan, setDeletingPlan] = useState<DashboardPlan | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const recurringPlans = plans.filter((p) => p.planType === "recurring");
  const splitPlans = plans.filter((p) => p.planType === "split_payment");

  async function handleDeleteConfirm(mode: "future" | "all") {
    if (!deletingPlan) return;
    setDeletingId(deletingPlan.id);
    try {
      await onDeletePlan(deletingPlan.id, mode);
      setDeletingPlan(null);
    } finally {
      setDeletingId(null);
    }
  }

  function formatNextDue(plan: DashboardPlan) {
    if (!plan.nextDueDate) return plan.status === "completed" ? "Completed" : "—";
    try {
      return format(new Date(plan.nextDueDate), "MMM d, yyyy");
    } catch {
      return "—";
    }
  }

  function PlanRow({ plan }: { plan: DashboardPlan }) {
    const isActive = plan.status === "active";
    const emoji = categories.find((c) => c.name === plan.category)?.emoji ?? "🏷️";
    const amountLabel =
      plan.planType === "recurring"
        ? `${currency.format(plan.amount)}/mo`
        : `${currency.format(plan.totalAmount)} total`;
    const progressLabel =
      plan.planType === "split_payment"
        ? `${plan.currentInstallmentNumber}/${plan.installmentCount} paid`
        : null;

    return (
      <TableRow className={!isActive ? "opacity-50" : undefined}>
        <TableCell>
          <div className="flex items-center gap-2">
            <span className="text-base">{emoji}</span>
            <div>
              <p className="font-medium text-sm">{plan.item}</p>
              <p className="text-xs text-muted-foreground">{plan.category}</p>
            </div>
          </div>
        </TableCell>
        <TableCell className="text-sm">
          <div>{amountLabel}</div>
          {progressLabel ? (
            <div className="text-xs text-muted-foreground">{progressLabel}</div>
          ) : null}
        </TableCell>
        <TableCell className="text-sm text-muted-foreground">Day {plan.dayOfMonth}</TableCell>
        <TableCell className="text-sm text-muted-foreground">{formatNextDue(plan)}</TableCell>
        <TableCell>
          <div className="flex justify-end gap-1">
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8"
              disabled={!isActive}
              aria-label={`Edit ${plan.item}`}
              onClick={() => onEditPlan(plan)}
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-destructive hover:text-destructive"
              disabled={!isActive || deletingId === plan.id}
              aria-label={`Delete ${plan.item}`}
              onClick={() => setDeletingPlan(plan)}
            >
              {deletingId === plan.id ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
            </Button>
          </div>
        </TableCell>
      </TableRow>
    );
  }

  function PlanTable({ title, items }: { title: string; items: DashboardPlan[] }) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Repeat2 className="h-4 w-4" />
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <CenteredListMessage label="Loading plans..." />
          ) : items.length === 0 ? (
            <CenteredListMessage label="No plans found." />
          ) : (
            <div className="rounded-xl border border-border/70">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Day</TableHead>
                    <TableHead>Next Due</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((plan) => (
                    <PlanRow key={plan.id} plan={plan} />
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <PlanTable title="Recurring Plans" items={recurringPlans} />
      <PlanTable title="Split Payment Plans" items={splitPlans} />

      {/* Delete dialog */}
      <Dialog open={deletingPlan !== null} onOpenChange={(open) => { if (!open && !deletingId) setDeletingPlan(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete plan</DialogTitle>
            <DialogDescription>
              <strong>{deletingPlan?.item}</strong>
              {deletingPlan?.planType === "split_payment"
                ? " — this will cancel the plan and remove all auto-generated charges."
                : " — choose how to stop this plan."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col gap-2 sm:flex-row">
            <Button variant="outline" onClick={() => setDeletingPlan(null)} disabled={!!deletingId}>
              Cancel
            </Button>
            {deletingPlan?.planType === "recurring" ? (
              <>
                <Button
                  variant="outline"
                  onClick={() => void handleDeleteConfirm("future")}
                  disabled={!!deletingId}
                >
                  {deletingId ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Stop future only
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => void handleDeleteConfirm("all")}
                  disabled={!!deletingId}
                >
                  {deletingId ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Stop + remove past
                </Button>
              </>
            ) : (
              <Button
                variant="destructive"
                onClick={() => void handleDeleteConfirm("all")}
                disabled={!!deletingId}
              >
                {deletingId ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Stop + remove all charges
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function RangeSelector({
  rangeKey,
  custom,
  onRangeKeyChange,
  onCustomChange,
}: {
  rangeKey: RangeKey;
  custom: DateRange | undefined;
  onRangeKeyChange: (value: RangeKey) => void;
  onCustomChange: (value: DateRange | undefined) => void;
}) {
  return (
    <>
      <Select value={rangeKey} onValueChange={(value) => onRangeKeyChange(value as RangeKey)}>
        <SelectTrigger className="w-[170px] h-9">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="today">Today</SelectItem>
          <SelectItem value="yesterday">Yesterday</SelectItem>
          <SelectItem value="weekly">Weekly</SelectItem>
          <SelectItem value="current-month">Current Month</SelectItem>
          <SelectItem value="30d">Last 30 Days</SelectItem>
          <SelectItem value="ytd">Year to Date</SelectItem>
          <SelectItem value="custom">Current Range</SelectItem>
        </SelectContent>
      </Select>

      {rangeKey === "custom" && (
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className={cn(
                "h-9 justify-start text-left font-normal",
                !custom && "text-muted-foreground",
              )}
            >
              <CalendarIcon className="mr-2 h-4 w-4" />
              {custom?.from
                ? custom.to
                  ? `${format(custom.from, "MMM d")} - ${format(custom.to, "MMM d")}`
                  : format(custom.from, "MMM d")
                : "Pick dates"}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar
              mode="range"
              selected={custom}
              onSelect={onCustomChange}
              numberOfMonths={2}
              className={cn("p-3 pointer-events-auto")}
            />
          </PopoverContent>
        </Popover>
      )}
    </>
  );
}

function CategoryFilterPopover({
  categories,
  selected,
  catColorMap,
  onToggle,
  isAllMode,
  onToggleAll,
}: {
  categories: DashboardCategory[];
  selected: string[];
  catColorMap: Record<string, string>;
  onToggle: (categoryName: string) => void;
  isAllMode: boolean;
  onToggleAll: (all: boolean) => void;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-9">
          <Filter className="mr-2 h-4 w-4" />
          Categories ({isAllMode ? categories.length : selected.length}/{categories.length})
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56" align="end">
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm cursor-pointer font-medium">
            <Checkbox
              checked={isAllMode}
              onCheckedChange={(checked) => onToggleAll(!!checked)}
            />
            All
          </label>
          <hr className="border-border" />
          {categories.map((category) => (
            <label
              key={category.name}
              className={`flex items-center gap-2 text-sm ${isAllMode ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
            >
              <Checkbox
                checked={isAllMode || selected.includes(category.name)}
                onCheckedChange={() => !isAllMode && onToggle(category.name)}
                disabled={isAllMode}
              />
              <span
                className="h-2.5 w-2.5 rounded-sm shrink-0"
                style={{ background: catColorMap[category.name] ?? colorForCategory(0) }}
              />
              {category.emoji} {category.name}
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  trend,
}: {
  label: string;
  value: string;
  sub: string;
  icon: React.ComponentType<{ className?: string }>;
  trend?: "up" | "down";
}) {
  return (
    <Card className="border-border/60">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold mt-1 text-foreground">{value}</p>
            <p
              className={`text-xs mt-1 flex items-center gap-1 ${trend === "up" ? "text-destructive" : "text-accent"}`}
            >
              {trend === "up" ? (
                <TrendingUp className="h-3 w-3" />
              ) : (
                <TrendingDown className="h-3 w-3" />
              )}
              {sub}
            </p>
          </div>
          <div className="h-10 w-10 rounded-lg bg-accent/10 flex items-center justify-center text-accent">
            <Icon className="h-5 w-5" />
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
  return (
    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
      {label}
    </div>
  );
}

function CenteredListMessage({ label }: { label: string }) {
  return <div className="py-16 text-center text-sm text-muted-foreground">{label}</div>;
}
