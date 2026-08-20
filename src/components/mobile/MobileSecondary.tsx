import { useState } from "react";
import { format } from "date-fns";
import { Loader2, Pencil, Repeat2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { currency } from "@/lib/dashboard-format";
import type { DashboardCategory, DashboardPlan } from "@/lib/dashboard-api";
import { MobileEmpty, MobileListCard, MobileRow } from "./MobileList";
import type { DashboardViewProps } from "./types";

/**
 * Subscriptions, split into the same two sections as the desktop PlansTab —
 * recurring plans and split payment plans — each row carrying the edit and
 * delete actions the desktop table has.
 */
export function MobilePlans({
  plans,
  categories,
  loading,
  onUpdatePlan,
  onDeletePlan,
}: {
  plans: DashboardPlan[];
  categories: DashboardCategory[];
  loading: boolean;
  onUpdatePlan: DashboardViewProps["onUpdatePlan"];
  onDeletePlan: DashboardViewProps["onDeletePlan"];
}) {
  const [editingPlan, setEditingPlan] = useState<DashboardPlan | null>(null);
  const [deletingPlan, setDeletingPlan] = useState<DashboardPlan | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Mobile shows only live plans. The desktop table keeps cancelled/completed
  // rows around (dimmed) as a history; on a phone that is just noise between
  // the plans you can still act on.
  const activePlans = plans.filter((p) => p.status === "active");
  const recurringPlans = activePlans.filter((p) => p.planType === "recurring");
  const splitPlans = activePlans.filter((p) => p.planType === "split_payment");

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
    if (!plan.nextDueDate) return "—";
    try {
      return format(new Date(plan.nextDueDate), "MMM d, yyyy");
    } catch {
      return "—";
    }
  }

  function PlanSection({ title, items }: { title: string; items: DashboardPlan[] }) {
    return (
      <div className="space-y-2">
        <p className="flex items-center gap-2 px-1 pt-2 text-sm font-medium">
          <Repeat2 className="h-4 w-4" />
          {title}
        </p>
        <MobileListCard>
          {loading ? (
            <MobileEmpty label="Loading plans..." />
          ) : items.length === 0 ? (
            <MobileEmpty label="No active plans." />
          ) : (
            items.map((plan) => {
              const emoji = categories.find((c) => c.name === plan.category)?.emoji ?? "🏷️";
              const isSplit = plan.planType === "split_payment";
              const amountLabel = isSplit
                ? `${currency.format(plan.totalAmount)} total`
                : `${currency.format(plan.amount)}/mo`;
              const progress = isSplit
                ? ` · ${plan.currentInstallmentNumber}/${plan.installmentCount} paid`
                : "";

              return (
                <MobileRow
                  key={plan.id}
                  title={`${emoji} ${plan.item}`}
                  subtitle={`${plan.category} · day ${plan.dayOfMonth} · next ${formatNextDue(
                    plan,
                  )}${progress}`}
                  amount={amountLabel}
                  actions={
                    <>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-9 w-9"
                        aria-label={`Edit ${plan.item}`}
                        onClick={() => setEditingPlan(plan)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-9 w-9 text-destructive hover:text-destructive"
                        disabled={deletingId === plan.id}
                        aria-label={`Delete ${plan.item}`}
                        onClick={() => setDeletingPlan(plan)}
                      >
                        {deletingId === plan.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                    </>
                  }
                />
              );
            })
          )}
        </MobileListCard>
      </div>
    );
  }

  return (
    <>
      <PlanSection title="Recurring Plans" items={recurringPlans} />
      <PlanSection title="Split Payment Plans" items={splitPlans} />

      <MobilePlanEditDialog
        plan={editingPlan}
        categories={categories}
        onClose={() => setEditingPlan(null)}
        onUpdatePlan={onUpdatePlan}
      />

      <Dialog
        open={deletingPlan !== null}
        onOpenChange={(open) => {
          if (!open && !deletingId) setDeletingPlan(null);
        }}
      >
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
          <DialogFooter className="flex-col gap-2">
            {deletingPlan?.planType === "recurring" ? (
              <>
                <Button
                  variant="outline"
                  className="h-11 w-full"
                  onClick={() => void handleDeleteConfirm("future")}
                  disabled={!!deletingId}
                >
                  {deletingId ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Stop future only
                </Button>
                <Button
                  variant="destructive"
                  className="h-11 w-full"
                  onClick={() => void handleDeleteConfirm("all")}
                  disabled={!!deletingId}
                >
                  {deletingId ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Stop + remove past
                </Button>
              </>
            ) : (
              <Button
                variant="destructive"
                className="h-11 w-full"
                onClick={() => void handleDeleteConfirm("all")}
                disabled={!!deletingId}
              >
                {deletingId ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Stop + remove all charges
              </Button>
            )}
            <Button
              variant="outline"
              className="h-11 w-full"
              onClick={() => setDeletingPlan(null)}
              disabled={!!deletingId}
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/**
 * Same fields and validation as the desktop "Edit plan" dialog. Keyed on the
 * plan id so opening a different plan remounts with fresh field state instead
 * of needing an effect to copy the plan into local state.
 */
function MobilePlanEditDialog({
  plan,
  categories,
  onClose,
  onUpdatePlan,
}: {
  plan: DashboardPlan | null;
  categories: DashboardCategory[];
  onClose: () => void;
  onUpdatePlan: DashboardViewProps["onUpdatePlan"];
}) {
  return (
    <Dialog
      open={plan !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent>
        {plan ? (
          <PlanEditForm
            key={plan.id}
            plan={plan}
            categories={categories}
            onClose={onClose}
            onUpdatePlan={onUpdatePlan}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function PlanEditForm({
  plan,
  categories,
  onClose,
  onUpdatePlan,
}: {
  plan: DashboardPlan;
  categories: DashboardCategory[];
  onClose: () => void;
  onUpdatePlan: DashboardViewProps["onUpdatePlan"];
}) {
  const isSplit = plan.planType === "split_payment";
  const [item, setItem] = useState(plan.item);
  const [category, setCategory] = useState(plan.category);
  const [startDate, setStartDate] = useState(
    `${plan.startYear.toString().padStart(4, "0")}-${plan.startMonth
      .toString()
      .padStart(2, "0")}-${plan.dayOfMonth.toString().padStart(2, "0")}`,
  );
  const [amount, setAmount] = useState(String(isSplit ? plan.totalAmount : plan.amount));
  const [months, setMonths] = useState(isSplit ? String(plan.installmentCount) : "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!item.trim()) {
      setError("Name cannot be empty.");
      return;
    }
    if (!startDate || Number.isNaN(new Date(startDate).getTime())) {
      setError("Start date is required.");
      return;
    }

    const parsedAmount = parseFloat(amount);
    let installmentCount: number | undefined;

    if (!isSplit) {
      if (Number.isNaN(parsedAmount) || parsedAmount <= 0) {
        setError("Amount must be a positive number.");
        return;
      }
    } else {
      installmentCount = parseInt(months, 10);
      if (Number.isNaN(parsedAmount) || parsedAmount <= 0) {
        setError("Total amount must be a positive number.");
        return;
      }
      if (Number.isNaN(installmentCount) || installmentCount < 1) {
        setError("Months must be at least 1.");
        return;
      }
      if (installmentCount < plan.currentInstallmentNumber) {
        setError(
          `Months cannot be less than already posted installments (${plan.currentInstallmentNumber}).`,
        );
        return;
      }
    }

    setSaving(true);
    setError(null);
    try {
      await onUpdatePlan(plan.id, {
        item: item.trim(),
        category,
        startDate,
        ...(isSplit
          ? { totalAmount: parsedAmount, installmentCount }
          : { amount: parsedAmount }),
      });
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to update plan.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Edit plan</DialogTitle>
        <DialogDescription>
          {isSplit
            ? "Update name, category, day, total amount, or number of months."
            : "Update name, category, start date, or amount."}
        </DialogDescription>
      </DialogHeader>

      <div className="grid gap-4 py-1">
        <div className="space-y-2">
          <Label htmlFor="m-plan-item">Name</Label>
          <Input
            id="m-plan-item"
            className="h-11"
            value={item}
            onChange={(e) => setItem(e.target.value)}
            disabled={saving}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="m-plan-category">Category</Label>
          <Select value={category} onValueChange={setCategory} disabled={saving}>
            <SelectTrigger id="m-plan-category" className="h-11">
              <SelectValue placeholder="Select a category" />
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

        <div className="space-y-2">
          <Label htmlFor="m-plan-start">Start Date</Label>
          <Input
            id="m-plan-start"
            className="h-11"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            disabled={saving}
          />
          <p className="text-xs text-muted-foreground">
            Sets when the plan starts and the monthly posting day.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="m-plan-amount">{isSplit ? "Total Amount" : "Monthly Amount"}</Label>
          <Input
            id="m-plan-amount"
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

        {isSplit ? (
          <div className="space-y-2">
            <Label htmlFor="m-plan-months">Months</Label>
            <Input
              id="m-plan-months"
              className="h-11"
              type="number"
              inputMode="numeric"
              min={Math.max(1, plan.currentInstallmentNumber)}
              step="1"
              value={months}
              onChange={(e) => setMonths(e.target.value)}
              disabled={saving}
            />
            <p className="text-xs text-muted-foreground">
              Saving a split-plan edit recalculates the schedule and rewrites this plan&apos;s
              auto-generated charges to stay consistent.
            </p>
          </div>
        ) : null}

        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </div>

      <DialogFooter className="flex-col gap-2">
        <Button className="h-11 w-full" onClick={() => void handleSave()} disabled={saving}>
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Save
        </Button>
        <Button variant="outline" className="h-11 w-full" onClick={onClose} disabled={saving}>
          Cancel
        </Button>
      </DialogFooter>
    </>
  );
}
