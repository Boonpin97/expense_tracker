import { useState } from "react";
import { Loader2, LogOut, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDateTimeInputValue } from "@/lib/dashboard-format";
import type { DashboardViewProps } from "./types";
import { MOBILE_TABS, MobileTabStrip, type MobileTabKey } from "./MobileTabStrip";
import { MobileOverview } from "./MobileOverview";
import { MobileTransactions } from "./MobileTransactions";
import { MobileIncome } from "./MobileIncome";
import { MobileGoals } from "./MobileGoals";
import { MobileProjects } from "./MobileProjects";
import { MobileBudget, MobileCharts, MobilePlans } from "./MobileSecondary";

export function MobileLayout(props: DashboardViewProps) {
  const {
    session,
    loading,
    error,
    categories,
    budgets,
    transactions,
    inflows,
    goals,
    projects,
    plans,
    onLogout,
    onCreateTransaction,
    onDeleteTransaction,
    onCreateInflow,
    onDeleteInflow,
  } = props;

  const [tab, setTab] = useState<MobileTabKey>("overview");
  const [addOpen, setAddOpen] = useState<"expense" | "income" | null>(null);

  const activeLabel = MOBILE_TABS.find((t) => t.key === tab)?.label ?? "";

  return (
    <div className="min-h-screen bg-secondary/40">
      <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
        <div className="flex items-center justify-between gap-2 px-4 py-3">
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold">BudgetFlow</h1>
            <p className="truncate text-xs text-muted-foreground">{session.username}</p>
          </div>
          <Button
            size="icon"
            variant="ghost"
            className="h-11 w-11 shrink-0"
            aria-label="Sign out"
            onClick={onLogout}
          >
            <LogOut className="h-5 w-5" />
          </Button>
        </div>
        <div className="px-4 pb-2">
          <MobileTabStrip active={tab} onChange={setTab} />
        </div>
      </header>

      <main className="space-y-4 px-4 py-4 pb-28">
        {error ? (
          <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        ) : null}

        <h2 className="sr-only">{activeLabel}</h2>

        {tab === "overview" ? (
          <MobileOverview
            transactions={transactions}
            inflows={inflows}
            loading={loading}
            onSeeAll={() => setTab("transactions")}
          />
        ) : null}

        {tab === "transactions" ? (
          <MobileTransactions
            transactions={transactions}
            loading={loading}
            onDeleteTransaction={onDeleteTransaction}
          />
        ) : null}

        {tab === "income" ? (
          <MobileIncome
            inflows={inflows}
            goals={goals}
            projects={projects}
            loading={loading}
            onDeleteInflow={onDeleteInflow}
          />
        ) : null}

        {tab === "goals" ? <MobileGoals goals={goals} loading={loading} /> : null}

        {tab === "projects" ? (
          <MobileProjects projects={projects} inflows={inflows} loading={loading} />
        ) : null}

        {tab === "charts" ? <MobileCharts transactions={transactions} /> : null}
        {tab === "budget" ? (
          <MobileBudget budgets={budgets} transactions={transactions} />
        ) : null}
        {tab === "plans" ? <MobilePlans plans={plans} loading={loading} /> : null}
      </main>

      {/* Thumb-reachable actions. Kept above the iOS home indicator via env(). */}
      <div
        className="fixed inset-x-0 bottom-0 z-30 flex gap-2 border-t bg-background/95 px-4 py-3 backdrop-blur"
        style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}
      >
        <Button className="h-12 flex-1" onClick={() => setAddOpen("expense")}>
          <Plus className="mr-1 h-4 w-4" />
          Expense
        </Button>
        <Button
          className="h-12 flex-1 bg-emerald-700 text-white hover:bg-emerald-800"
          onClick={() => setAddOpen("income")}
        >
          <Plus className="mr-1 h-4 w-4" />
          Income
        </Button>
      </div>

      <MobileAddDialog
        mode={addOpen}
        onClose={() => setAddOpen(null)}
        categories={categories}
        goals={goals}
        projects={projects}
        onCreateTransaction={onCreateTransaction}
        onCreateInflow={onCreateInflow}
      />
    </div>
  );
}

/**
 * One dialog for both quick-add flows. Only the fields that matter on a phone:
 * the desktop Add Transaction dialog carries seven fields plus a checkbox card
 * (~800px tall), which is unusable here. Payment plans stay a desktop task.
 */
function MobileAddDialog({
  mode,
  onClose,
  categories,
  goals,
  projects,
  onCreateTransaction,
  onCreateInflow,
}: {
  mode: "expense" | "income" | null;
  onClose: () => void;
  categories: DashboardViewProps["categories"];
  goals: DashboardViewProps["goals"];
  projects: DashboardViewProps["projects"];
  onCreateTransaction: DashboardViewProps["onCreateTransaction"];
  onCreateInflow: DashboardViewProps["onCreateInflow"];
}) {
  const [item, setItem] = useState("");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [when, setWhen] = useState(formatDateTimeInputValue(new Date()));
  const [goalId, setGoalId] = useState("none");
  const [projectId, setProjectId] = useState("none");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const isIncome = mode === "income";

  function reset() {
    setItem("");
    setAmount("");
    setCategory("");
    setWhen(formatDateTimeInputValue(new Date()));
    setGoalId("none");
    setProjectId("none");
    setFormError(null);
  }

  async function handleSubmit() {
    setFormError(null);
    const trimmed = item.trim();
    const parsed = Number(amount);
    if (!trimmed) {
      setFormError("Description is required.");
      return;
    }
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setFormError("Amount must be a positive number.");
      return;
    }
    const timestamp = new Date(when);
    if (Number.isNaN(timestamp.getTime())) {
      setFormError("Date is invalid.");
      return;
    }
    if (!isIncome && !category) {
      setFormError("Pick a category.");
      return;
    }

    setSaving(true);
    try {
      if (isIncome) {
        await onCreateInflow({
          item: trimmed,
          amount: parsed,
          timestamp,
          goalId: goalId === "none" ? null : goalId,
          projectId: projectId === "none" ? null : projectId,
        });
      } else {
        await onCreateTransaction({
          item: trimmed,
          amount: parsed,
          category,
          timestamp,
          paymentType: "one_time",
        });
      }
      reset();
      onClose();
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Could not save.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={mode !== null}
      onOpenChange={(open) => {
        if (!open && !saving) {
          reset();
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isIncome ? "Add Income" : "Add Expense"}</DialogTitle>
        </DialogHeader>

        <div className="grid gap-4 py-1">
          <div className="space-y-2">
            <Label htmlFor="m-item">Description</Label>
            <Input
              id="m-item"
              className="h-11"
              value={item}
              onChange={(e) => setItem(e.target.value)}
              disabled={saving}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="m-amount">Amount</Label>
            <Input
              id="m-amount"
              className="h-11"
              type="number"
              inputMode="decimal"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              disabled={saving}
            />
          </div>

          {!isIncome ? (
            <div className="space-y-2">
              <Label htmlFor="m-category">Category</Label>
              <Select value={category} onValueChange={setCategory} disabled={saving}>
                <SelectTrigger id="m-category" className="h-11">
                  <SelectValue placeholder="Pick a category" />
                </SelectTrigger>
                <SelectContent>
                  {categories.map((c) => (
                    <SelectItem key={c.name} value={c.name}>
                      {c.emoji} {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="m-when">Date &amp; time</Label>
            <Input
              id="m-when"
              className="h-11"
              type="datetime-local"
              value={when}
              onChange={(e) => setWhen(e.target.value)}
              disabled={saving}
            />
          </div>

          {isIncome ? (
            <>
              <div className="space-y-2">
                <Label htmlFor="m-goal">Assign to goal</Label>
                <Select
                  value={goalId}
                  onValueChange={setGoalId}
                  disabled={saving || goals.length === 0}
                >
                  <SelectTrigger id="m-goal" className="h-11">
                    <SelectValue placeholder="None" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {goals.map((g) => (
                      <SelectItem key={g.id} value={g.id}>
                        {g.emoji} {g.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="m-project">Assign to project</Label>
                <Select
                  value={projectId}
                  onValueChange={setProjectId}
                  disabled={saving || projects.length === 0}
                >
                  <SelectTrigger id="m-project" className="h-11">
                    <SelectValue placeholder="None" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {projects.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.emoji} {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </>
          ) : null}

          {formError ? <p className="text-sm text-destructive">{formError}</p> : null}
        </div>

        <DialogFooter>
          <Button
            className="h-11 w-full"
            onClick={() => void handleSubmit()}
            disabled={saving}
          >
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            {isIncome ? "Add Income" : "Add Expense"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
