import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { Loader2, Search, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { currency } from "@/lib/dashboard-format";
import { sortTransactions, type TransactionSortKey } from "@/lib/dashboard-analytics";
import type { DashboardCategory, DashboardTransaction } from "@/lib/dashboard-api";
import { MobileEmpty, MobileListCard, MobileRow } from "./MobileList";
import { MobilePagination } from "./MobilePagination";
import {
  MobileCategoryFilter,
  MobileRangeSelect,
  MobileSortSelect,
  mobileRange,
  useCategorySelection,
  type MobileRangeKey,
  type MobileTxnJump,
} from "./MobileFilters";

const PAGE_SIZE = 20;

/**
 * Card list with a numbered pager. The desktop table needs ~420px in ~295px of
 * card width, and its Prev/"Page X of Y"/Next row needs ~322px, both of which
 * push the whole page sideways.
 *
 * The filter set matches the desktop TransactionsTab — search, amount range,
 * date range, categories, sort — stacked into rows that fit a 375px viewport.
 */
export function MobileTransactions({
  transactions,
  categories,
  loading,
  onDeleteTransaction,
  jump,
}: {
  transactions: DashboardTransaction[];
  categories: DashboardCategory[];
  loading: boolean;
  onDeleteTransaction: (transactionId: string) => Promise<void>;
  jump?: MobileTxnJump | null;
}) {
  const [query, setQuery] = useState("");
  const [rangeKey, setRangeKey] = useState<MobileRangeKey>("current-month");
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [sortKey, setSortKey] = useState<TransactionSortKey>("date-desc");
  const [page, setPage] = useState(1);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const cats = useCategorySelection(categories);
  const { selectOnly, toggleAll } = cats;

  // A jump from the Budget tab arrives with its own range and category.
  useEffect(() => {
    if (!jump) return;
    setRangeKey(jump.rangeKey);
    if (jump.category !== null) {
      selectOnly(jump.category);
    } else {
      toggleAll(true);
    }
  }, [jump, selectOnly, toggleAll]);

  const emojiByCategory = useMemo(
    () => new Map(categories.map((c) => [c.name, c.emoji])),
    [categories],
  );

  const minValue = minAmount.trim() === "" ? null : Number(minAmount);
  const maxValue = maxAmount.trim() === "" ? null : Number(maxAmount);

  const filtered = useMemo(() => {
    const { from, to } = mobileRange(rangeKey);
    const allowed = new Set(cats.selected);
    const needle = query.trim().toLowerCase();

    const matched = transactions.filter((tx) => {
      if (tx.timestamp < from || tx.timestamp > to) return false;
      if (!allowed.has(tx.category)) return false;
      if (minValue !== null && !Number.isNaN(minValue) && tx.amount < minValue) return false;
      if (maxValue !== null && !Number.isNaN(maxValue) && tx.amount > maxValue) return false;
      if (needle) {
        const searchable = [
          tx.item,
          tx.category,
          format(tx.timestamp, "MMM d, yyyy"),
          format(tx.timestamp, "yyyy-MM-dd"),
        ]
          .join(" ")
          .toLowerCase();
        if (!searchable.includes(needle)) return false;
      }
      return true;
    });

    return sortTransactions(matched, sortKey);
  }, [transactions, rangeKey, cats.selected, minValue, maxValue, query, sortKey]);

  // Any filter change puts the user back on the first page.
  useEffect(() => {
    setPage(1);
  }, [rangeKey, cats.selected, query, minAmount, maxAmount, sortKey]);

  const total = filtered.reduce((sum, tx) => sum + tx.amount, 0);
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  // Clamp so deleting the last row on the final page cannot strand the view.
  const safePage = Math.min(page, totalPages);
  const shown = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  async function handleDelete(tx: DashboardTransaction) {
    if (!window.confirm(`Delete "${tx.item}"?`)) return;
    setDeletingId(tx.id);
    try {
      await onDeleteTransaction(tx.id);
    } catch {
      // Row stays; the next refresh reconciles.
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by item, category, or date"
          className="h-11 pl-9"
          inputMode="search"
        />
      </div>

      <div className="flex gap-2">
        <MobileRangeSelect value={rangeKey} onChange={setRangeKey} />
        <MobileCategoryFilter
          categories={categories}
          selected={cats.selected}
          isAllMode={cats.isAllMode}
          onToggleAll={cats.toggleAll}
          onToggleOne={cats.toggleOne}
        />
      </div>

      <div className="flex gap-2">
        <MobileSortSelect value={sortKey} onChange={setSortKey} />
        {/* Bare number inputs: a bordered Min/Max group like the desktop one
            leaves ~35px per field at 375px. */}
        <Input
          aria-label="Minimum amount"
          className="h-10 w-[76px] shrink-0 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          inputMode="decimal"
          onChange={(e) => setMinAmount(e.target.value)}
          placeholder="Min"
          type="number"
          value={minAmount}
        />
        <Input
          aria-label="Maximum amount"
          className="h-10 w-[76px] shrink-0 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          inputMode="decimal"
          onChange={(e) => setMaxAmount(e.target.value)}
          placeholder="Max"
          type="number"
          value={maxAmount}
        />
      </div>

      <div className="flex items-center justify-between px-1 text-xs text-muted-foreground">
        <span>
          {filtered.length} {filtered.length === 1 ? "expense" : "expenses"}
        </span>
        <span className="font-semibold tabular-nums text-destructive">
          {currency.format(total)}
        </span>
      </div>

      <MobileListCard>
        {loading ? (
          <MobileEmpty label="Loading expenses..." />
        ) : shown.length === 0 ? (
          <MobileEmpty label="No expenses found for the selected filters." />
        ) : (
          shown.map((tx) => (
            <MobileRow
              key={tx.id}
              title={tx.item}
              subtitle={`${emojiByCategory.get(tx.category) ?? "$"} ${tx.category} · ${format(
                tx.timestamp,
                "MMM d, yyyy",
              )}`}
              amount={currency.format(tx.amount)}
              actions={
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-9 w-9 text-destructive hover:text-destructive"
                  aria-label={`Delete ${tx.item}`}
                  disabled={deletingId === tx.id}
                  onClick={() => void handleDelete(tx)}
                >
                  {deletingId === tx.id ? (
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

      <MobilePagination page={safePage} totalPages={totalPages} onChange={setPage} />
    </div>
  );
}
