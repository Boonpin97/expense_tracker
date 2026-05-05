import 'package:expense_bot/dashboard_app.dart';
import 'package:flutter_test/flutter_test.dart';

DashboardTransaction _tx(
  String id,
  String category,
  double amount,
  DateTime timestamp,
) {
  return DashboardTransaction(
    id: id,
    item: id,
    amount: amount,
    category: category,
    timestamp: timestamp,
    chatId: 1,
  );
}

void main() {
  test('analyticsRangeForPreset builds stable preset windows', () {
    final now = DateTime(2026, 5, 5, 14, 30);

    final last30 = analyticsRangeForPreset(
      AnalyticsRangePreset.last30Days,
      now: now,
    );
    expect(last30.start, DateTime(2026, 4, 6));
    expect(last30.end, DateTime(2026, 5, 5));

    final yearToDate = analyticsRangeForPreset(
      AnalyticsRangePreset.yearToDate,
      now: now,
    );
    expect(yearToDate.start, DateTime(2026, 1, 1));
    expect(yearToDate.end, DateTime(2026, 5, 5));
  });

  test('applyAnalyticsFilters keeps only categories with budgets when requested', () {
    final transactions = [
      _tx('1', 'Food', 24, DateTime(2026, 5, 1)),
      _tx('2', 'Travel', 80, DateTime(2026, 5, 2)),
      _tx('3', 'Food', 10, DateTime(2026, 5, 3)),
    ];

    final filtered = applyAnalyticsFilters(
      transactions,
      budgets: const {'Food': 200},
      budgetedOnly: true,
      overBudgetOnly: false,
    );

    expect(filtered.map((tx) => tx.category).toSet(), {'Food'});
  });

  test('applyAnalyticsFilters keeps only over-budget categories when requested', () {
    final transactions = [
      _tx('1', 'Food', 90, DateTime(2026, 5, 1)),
      _tx('2', 'Food', 40, DateTime(2026, 5, 2)),
      _tx('3', 'Travel', 60, DateTime(2026, 5, 3)),
    ];

    final filtered = applyAnalyticsFilters(
      transactions,
      budgets: const {
        'Food': 100,
        'Travel': 80,
      },
      budgetedOnly: false,
      overBudgetOnly: true,
    );

    expect(filtered.length, 2);
    expect(filtered.every((tx) => tx.category == 'Food'), isTrue);

    final summaries = buildCategorySummaries(filtered, const []);
    expect(
      countOverBudgetCategories(
        summaries,
        const {
          'Food': 100,
          'Travel': 80,
        },
      ),
      1,
    );
  });
}
