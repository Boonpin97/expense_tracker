import 'package:expense_bot/dashboard_app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('filters analytics transactions by selected categories', () {
    final transactions = [
      DashboardTransaction(
        id: '1',
        item: 'Lunch',
        amount: 12,
        category: 'Food',
        timestamp: DateTime(2026, 5, 1),
        chatId: 7,
      ),
      DashboardTransaction(
        id: '2',
        item: 'Train',
        amount: 3,
        category: 'Transport',
        timestamp: DateTime(2026, 5, 2),
        chatId: 7,
      ),
    ];

    final filtered = filterTransactionsBySelectedCategories(
      transactions,
      {'Food'},
    );

    expect(filtered, hasLength(1));
    expect(filtered.single.category, 'Food');
  });

  test('category selection label reports all categories by default', () {
    final categories = [
      DashboardCategory(name: 'Food', emoji: '🍜', order: 1),
      DashboardCategory(name: 'Transport', emoji: '🚆', order: 2),
    ];

    expect(
      analyticsCategorySelectionLabel({'Food', 'Transport'}, categories),
      'All categories',
    );
    expect(
      analyticsCategorySelectionLabel({'Food'}, categories),
      '🍜 Food',
    );
    expect(
      analyticsCategorySelectionLabel({'Food', 'Transport', 'Other'}, categories),
      'All categories',
    );
  });

  test('analytics custom preset is inclusive of the selected end date', () {
    final transactions = [
      DashboardTransaction(
        id: '1',
        item: 'Breakfast',
        amount: 5,
        category: 'Food',
        timestamp: DateTime(2026, 5, 1, 9),
        chatId: 7,
      ),
      DashboardTransaction(
        id: '2',
        item: 'Dinner',
        amount: 8,
        category: 'Food',
        timestamp: DateTime(2026, 5, 3, 20),
        chatId: 7,
      ),
    ];

    final filtered = filterTransactionsByRange(
      transactions,
      DateTimeRange(
        start: DateTime(2026, 5, 1),
        end: DateTime(2026, 5, 3),
      ),
    );

    expect(filtered, hasLength(2));
  });
}
