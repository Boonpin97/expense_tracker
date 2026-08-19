import { useMemo, useState } from "react";
import { Loader2, Search, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { currency } from "@/lib/dashboard-format";
import type { DashboardTransaction } from "@/lib/dashboard-api";
import { MobileEmpty, MobileListCard, MobileRow } from "./MobileList";

const PAGE_SIZE = 20;

/**
 * Card list with incremental "load more" instead of the desktop table plus
 * Prev/Next pager. The desktop pager needs about 322px in ~295px of card width,
 * which is one of the things that pushes the whole page sideways.
 */
export function MobileTransactions({
  transactions,
  loading,
  onDeleteTransaction,
}: {
  transactions: DashboardTransaction[];
  loading: boolean;
  onDeleteTransaction: (transactionId: string) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [visible, setVisible] = useState(PAGE_SIZE);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const sorted = [...transactions].sort(
      (a, b) => b.timestamp.getTime() - a.timestamp.getTime(),
    );
    if (!needle) return sorted;
    return sorted.filter(
      (tx) =>
        tx.item.toLowerCase().includes(needle) || tx.category.toLowerCase().includes(needle),
    );
  }, [transactions, query]);

  const shown = filtered.slice(0, visible);
  const total = filtered.reduce((sum, tx) => sum + tx.amount, 0);

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
          onChange={(e) => {
            setQuery(e.target.value);
            setVisible(PAGE_SIZE);
          }}
          placeholder="Search expenses"
          className="h-11 pl-9"
          inputMode="search"
        />
      </div>

      <div className="flex items-center justify-between px-1 text-xs text-muted-foreground">
        <span>
          {filtered.length} {filtered.length === 1 ? "expense" : "expenses"}
        </span>
        <span className="font-semibold tabular-nums text-foreground">
          {currency.format(total)}
        </span>
      </div>

      <MobileListCard>
        {loading ? (
          <MobileEmpty label="Loading expenses..." />
        ) : shown.length === 0 ? (
          <MobileEmpty label={query ? "Nothing matches that search." : "No expenses yet."} />
        ) : (
          shown.map((tx) => (
            <MobileRow
              key={tx.id}
              title={tx.item}
              subtitle={`${tx.category} · ${tx.timestamp.toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}`}
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

      {shown.length < filtered.length ? (
        <Button
          variant="outline"
          className="h-11 w-full"
          onClick={() => setVisible((n) => n + PAGE_SIZE)}
        >
          Load {Math.min(PAGE_SIZE, filtered.length - shown.length)} more
        </Button>
      ) : null}
    </div>
  );
}
