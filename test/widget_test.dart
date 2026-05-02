import 'package:expense_bot/dashboard_app.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('shows dashboard sign-in form',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const ExpenseDashboardApp(),
    );

    expect(find.text('Expense Monitor'), findsOneWidget);
    expect(find.text('Username'), findsOneWidget);
    expect(find.text('Password'), findsOneWidget);
  });
}
