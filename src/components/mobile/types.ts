import type {
  DashboardCategory,
  DashboardGoal,
  DashboardInflow,
  DashboardPaymentType,
  DashboardPlan,
  DashboardPreferences,
  DashboardProject,
  DashboardSession,
  DashboardTransaction,
} from "@/lib/dashboard-api";

/**
 * Props handed down from DashboardShell, which owns all data fetching and
 * every mutation handler. Both the desktop layout and the mobile layout
 * consume this one definition so the two presentation trees cannot drift.
 */
export type DashboardViewProps = {
  session: DashboardSession;
  loading: boolean;
  error: string | null;
  categories: DashboardCategory[];
  budgets: Record<string, number>;
  transactions: DashboardTransaction[];
  inflows: DashboardInflow[];
  goals: DashboardGoal[];
  projects: DashboardProject[];
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
    startDate?: string;
    numberOfMonths?: number;
    createFirstTransactionNow?: boolean;
  }) => Promise<void>;
  onCreateInflow: (payload: {
    item: string;
    amount: number;
    timestamp: Date;
    goalId?: string | null;
    projectId?: string | null;
  }) => Promise<void>;
  onDeleteInflow: (inflowId: string) => Promise<void>;
  onRefreshBudgets: () => Promise<void>;
  onUpdatePlan: (
    planId: string,
    payload: {
      item?: string;
      category?: string;
      dayOfMonth?: number;
      startDate?: string;
      amount?: number;
      totalAmount?: number;
      installmentCount?: number;
    },
  ) => Promise<void>;
  onDeletePlan: (planId: string, mode: "future" | "all") => Promise<void>;
  onUpdatePreferences: (next: DashboardPreferences) => Promise<void>;
  onCreateGoal: (payload: { name: string; targetAmount: number; emoji: string }) => Promise<void>;
  onUpdateGoal: (
    goalId: string,
    payload: { name?: string; targetAmount?: number; emoji?: string },
  ) => Promise<void>;
  onDeleteGoal: (goalId: string) => Promise<void>;
  onMoveGoal: (goalId: string, direction: -1 | 1) => Promise<void>;
  onCreateProject: (payload: {
    name: string;
    targetAmount: number;
    initialAmount: number;
    deadline: string;
    emoji: string;
  }) => Promise<void>;
  onUpdateProject: (
    projectId: string,
    payload: {
      name?: string;
      targetAmount?: number;
      initialAmount?: number;
      deadline?: string;
      emoji?: string;
    },
  ) => Promise<void>;
  onDeleteProject: (projectId: string) => Promise<void>;
  onMoveProject: (projectId: string, direction: -1 | 1) => Promise<void>;
  onCreateCategory: (payload: { name: string; emoji: string }) => Promise<void>;
  onUpdateCategory: (categoryName: string, payload: { name: string; emoji: string }) => Promise<void>;
  onDeleteCategory: (categoryName: string) => Promise<void>;
  onMoveCategory: (categoryName: string, direction: -1 | 1) => Promise<void>;
};
