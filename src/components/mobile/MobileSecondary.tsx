import { currency } from "@/lib/dashboard-format";
import type { DashboardPlan } from "@/lib/dashboard-api";
import { MobileEmpty, MobileListCard, MobileRow } from "./MobileList";

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
