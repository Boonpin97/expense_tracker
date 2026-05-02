import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:http/http.dart' as http;

import 'dashboard_http_client.dart';

class ExpenseDashboardApp extends StatelessWidget {
  const ExpenseDashboardApp({super.key});

  @override
  Widget build(BuildContext context) {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: const Color(0xFF0B6E4F),
      brightness: Brightness.light,
    );

    return MaterialApp(
      title: 'Expense Monitor',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: colorScheme,
        scaffoldBackgroundColor: const Color(0xFFF4F6F1),
        useMaterial3: true,
        cardTheme: CardThemeData(
          elevation: 0,
          color: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(24),
            side: BorderSide(color: colorScheme.outlineVariant),
          ),
        ),
      ),
      home: const AuthGate(),
    );
  }
}

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  late Future<DashboardSession?> _sessionFuture;

  @override
  void initState() {
    super.initState();
    _sessionFuture = DashboardRepository.fetchSession();
  }

  void _refreshSession() {
    setState(() {
      _sessionFuture = DashboardRepository.fetchSession();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<DashboardSession?>(
      future: _sessionFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const LoadingScaffold(message: 'Checking session...');
        }

        final session = snapshot.data;
        if (session == null) {
          return SignInScreen(onSignedIn: _refreshSession);
        }
        return DashboardShell(
          session: session,
          onSignedOut: _refreshSession,
        );
      },
    );
  }
}

class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key, required this.onSignedIn});

  final VoidCallback onSignedIn;

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _signIn() async {
    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await DashboardRepository.login(
        username: _usernameController.text,
        password: _passwordController.text,
      );
      widget.onSignedIn();
    } on DashboardApiException catch (error) {
      setState(() => _error = error.message);
    } catch (error) {
      setState(() => _error = error.toString());
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFFF7F8F4), Color(0xFFF1F5EF)],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Card(
              margin: const EdgeInsets.all(24),
              child: Padding(
                padding: const EdgeInsets.all(28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Expense Monitor',
                      style: theme.textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Sign in with the dashboard username and password you set from Telegram.',
                      style: theme.textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 24),
                    TextField(
                      controller: _usernameController,
                      enabled: !_busy,
                      decoration: const InputDecoration(
                        labelText: 'Username',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 14),
                    TextField(
                      controller: _passwordController,
                      enabled: !_busy,
                      obscureText: true,
                      onSubmitted: (_) => _busy ? null : _signIn(),
                      decoration: const InputDecoration(
                        labelText: 'Password',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 14),
                      Text(
                        _error!,
                        style: TextStyle(color: theme.colorScheme.error),
                      ),
                    ],
                    const SizedBox(height: 20),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton(
                        onPressed: _busy ? null : _signIn,
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          child: _busy
                              ? const SizedBox(
                                  height: 18,
                                  width: 18,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              : const Text('Sign in'),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class DashboardShell extends StatefulWidget {
  const DashboardShell({
    super.key,
    required this.session,
    required this.onSignedOut,
  });

  final DashboardSession session;
  final VoidCallback onSignedOut;

  @override
  State<DashboardShell> createState() => _DashboardShellState();
}

class _DashboardShellState extends State<DashboardShell> {
  int _index = 0;

  static const _titles = [
    'Transactions',
    'Reports',
    'Analytics',
    'Categories',
  ];

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.of(context).size.width >= 1080;
    final pages = [
      const TransactionsPage(),
      const ReportsPage(),
      const AnalyticsPage(),
      const CategoriesPage(),
    ];

    final navigation = NavigationRail(
      selectedIndex: _index,
      onDestinationSelected: (value) => setState(() => _index = value),
      extended: isWide,
      backgroundColor: Colors.transparent,
      labelType: isWide ? null : NavigationRailLabelType.all,
      destinations: const [
        NavigationRailDestination(
          icon: Icon(Icons.receipt_long_outlined),
          selectedIcon: Icon(Icons.receipt_long),
          label: Text('Transactions'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.summarize_outlined),
          selectedIcon: Icon(Icons.summarize),
          label: Text('Reports'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.insights_outlined),
          selectedIcon: Icon(Icons.insights),
          label: Text('Analytics'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.category_outlined),
          selectedIcon: Icon(Icons.category),
          label: Text('Categories'),
        ),
      ],
    );

    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        title: Text(_titles[_index]),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: Center(
              child: Text(
                widget.session.username,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ),
          IconButton(
            onPressed: () async {
              await DashboardRepository.logout();
              widget.onSignedOut();
            },
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: Row(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: navigation,
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 240),
              child: KeyedSubtree(
                key: ValueKey<int>(_index),
                child: pages[_index],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class TransactionsPage extends StatefulWidget {
  const TransactionsPage({super.key});

  @override
  State<TransactionsPage> createState() => _TransactionsPageState();
}

class _TransactionsPageState extends State<TransactionsPage> {
  DateTimeRange _range = currentMonthRange();
  String? _category;
  final TextEditingController _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<List<DashboardCategory>>(
      stream: DashboardRepository.streamCategories(),
      builder: (context, categoriesSnapshot) {
        final categories = categoriesSnapshot.data ?? const <DashboardCategory>[];
        return StreamBuilder<List<DashboardTransaction>>(
          stream: DashboardRepository.streamTransactions(
            range: _range,
            category: _category,
          ),
          builder: (context, transactionsSnapshot) {
            if (transactionsSnapshot.connectionState == ConnectionState.waiting) {
              return const LoadingBody();
            }

            final allTransactions = transactionsSnapshot.data ?? const <DashboardTransaction>[];
            final searchTerm = _searchController.text.trim().toLowerCase();
            final transactions = allTransactions
                .where((tx) => searchTerm.isEmpty || tx.item.toLowerCase().contains(searchTerm))
                .toList();

            final total = transactions.fold<double>(
              0,
              (sum, transaction) => sum + transaction.amount,
            );

            final isTable = MediaQuery.of(context).size.width > 920;

            return SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    spacing: 16,
                    runSpacing: 16,
                    children: [
                      _MetricCard(
                        title: 'Visible transactions',
                        value: '${transactions.length}',
                        subtitle: describeDateRange(_range),
                      ),
                      _MetricCard(
                        title: 'Visible spending',
                        value: formatCurrency(total),
                        subtitle: _category ?? 'All categories',
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          FilledButton.tonalIcon(
                            onPressed: () async {
                              final picked = await showDateRangePicker(
                                context: context,
                                firstDate: DateTime(2020),
                                lastDate: DateTime.now().add(const Duration(days: 365)),
                                initialDateRange: _range,
                              );
                              if (picked != null) {
                                setState(() => _range = picked);
                              }
                            },
                            icon: const Icon(Icons.date_range),
                            label: Text(describeDateRange(_range)),
                          ),
                          DropdownButton<String?>(
                            value: _category,
                            hint: const Text('All categories'),
                            items: [
                              const DropdownMenuItem<String?>(
                                value: null,
                                child: Text('All categories'),
                              ),
                              ...categories.map(
                                (category) => DropdownMenuItem<String?>(
                                  value: category.name,
                                  child: Text('${category.emoji} ${category.name}'),
                                ),
                              ),
                            ],
                            onChanged: (value) => setState(() => _category = value),
                          ),
                          SizedBox(
                            width: 260,
                            child: TextField(
                              controller: _searchController,
                              onChanged: (_) => setState(() {}),
                              decoration: const InputDecoration(
                                labelText: 'Search item',
                                prefixIcon: Icon(Icons.search),
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                          TextButton(
                            onPressed: () {
                              setState(() {
                                _range = currentMonthRange();
                                _category = null;
                                _searchController.clear();
                              });
                            },
                            child: const Text('Reset filters'),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: transactions.isEmpty
                          ? const Padding(
                              padding: EdgeInsets.all(24),
                              child: Text('No transactions match the current filters.'),
                            )
                          : isTable
                              ? _TransactionsTable(
                                  transactions: transactions,
                                  categories: categories,
                                )
                              : Column(
                                  children: transactions
                                      .map(
                                        (transaction) => _TransactionTile(
                                          transaction: transaction,
                                          categories: categories,
                                        ),
                                      )
                                      .toList(),
                                ),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}

class ReportsPage extends StatefulWidget {
  const ReportsPage({super.key});

  @override
  State<ReportsPage> createState() => _ReportsPageState();
}

class _ReportsPageState extends State<ReportsPage> {
  late DateTime _selectedMonth;

  @override
  void initState() {
    super.initState();
    _selectedMonth = DateTime(DateTime.now().year, DateTime.now().month);
  }

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final dayRange = singleDayRange(now);
    final weekRange = currentWeekRange();
    final monthRange = currentMonthRange();
    final earliest = [
      dayRange.start,
      weekRange.start,
      monthRange.start,
    ].reduce((a, b) => a.isBefore(b) ? a : b);

    return StreamBuilder<List<DashboardTransaction>>(
      stream: DashboardRepository.streamTransactions(
        range: DateTimeRange(start: earliest, end: now),
      ),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const LoadingBody();
        }

        final transactions = snapshot.data ?? const <DashboardTransaction>[];
        final daily = filterTransactionsByRange(transactions, dayRange);
        final weekly = filterTransactionsByRange(transactions, weekRange);
        final monthly = filterTransactionsByRange(transactions, monthRange);

        final recentMonths = List.generate(
          12,
          (index) => DateTime(now.year, now.month - index),
        );
        final monthChoices = <DateTime>[
          if (!recentMonths.any(
            (month) =>
                month.year == _selectedMonth.year &&
                month.month == _selectedMonth.month,
          ))
            _selectedMonth,
          ...recentMonths,
        ];

        final selectedRange = monthRangeFor(_selectedMonth);

        return SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  _ReportSummaryCard(
                    title: 'Today',
                    transactions: daily,
                    range: dayRange,
                  ),
                  _ReportSummaryCard(
                    title: 'This week',
                    transactions: weekly,
                    range: weekRange,
                  ),
                  _ReportSummaryCard(
                    title: 'This month',
                    transactions: monthly,
                    range: monthRange,
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              'Historical month report',
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                          ),
                          DropdownButton<DateTime>(
                            value: monthChoices.firstWhere(
                              (month) =>
                                  month.year == _selectedMonth.year &&
                                  month.month == _selectedMonth.month,
                            ),
                            items: monthChoices
                                .map(
                                  (month) => DropdownMenuItem<DateTime>(
                                    value: month,
                                    child: Text(DateFormat('MMMM yyyy').format(month)),
                                  ),
                                )
                                .toList(),
                            onChanged: (value) {
                              if (value != null) {
                                setState(() => _selectedMonth = value);
                              }
                            },
                          ),
                          const SizedBox(width: 12),
                          OutlinedButton.icon(
                            onPressed: () async {
                              final picked = await showDatePicker(
                                context: context,
                                initialDate: _selectedMonth,
                                firstDate: DateTime(2020),
                                lastDate: DateTime.now().add(const Duration(days: 365)),
                                initialDatePickerMode: DatePickerMode.year,
                              );
                              if (picked != null) {
                                setState(() {
                                  _selectedMonth = DateTime(picked.year, picked.month);
                                });
                              }
                            },
                            icon: const Icon(Icons.calendar_month),
                            label: const Text('Pick month'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      _HistoricalMonthPanel(range: selectedRange),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class AnalyticsPage extends StatefulWidget {
  const AnalyticsPage({super.key});

  @override
  State<AnalyticsPage> createState() => _AnalyticsPageState();
}

class _AnalyticsPageState extends State<AnalyticsPage> {
  DateTimeRange _range = currentMonthRange();
  String? _category;

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<List<DashboardCategory>>(
      stream: DashboardRepository.streamCategories(),
      builder: (context, categorySnapshot) {
        final categories = categorySnapshot.data ?? const <DashboardCategory>[];
        return StreamBuilder<List<DashboardTransaction>>(
          stream: DashboardRepository.streamTransactions(
            range: _range,
            category: _category,
          ),
          builder: (context, transactionSnapshot) {
            if (transactionSnapshot.connectionState == ConnectionState.waiting) {
              return const LoadingBody();
            }

            final transactions = transactionSnapshot.data ?? const <DashboardTransaction>[];
            final summaries = buildCategorySummaries(transactions, categories);
            final trend = buildTrendSeries(transactions);
            final topCategories = summaries.take(6).toList();
            final maxBarTotal = topCategories.isEmpty
                ? 1.0
                : topCategories
                    .map((summary) => summary.total)
                    .reduce(math.max);

            return StreamBuilder<Map<String, double>>(
              stream: DashboardRepository.streamBudgets(),
              builder: (context, budgetSnapshot) {
                final budgets = budgetSnapshot.data ?? const <String, double>{};

                return SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(20),
                          child: Wrap(
                            spacing: 12,
                            runSpacing: 12,
                            children: [
                              FilledButton.tonalIcon(
                                onPressed: () async {
                                  final picked = await showDateRangePicker(
                                    context: context,
                                    firstDate: DateTime(2020),
                                    lastDate: DateTime.now().add(const Duration(days: 365)),
                                    initialDateRange: _range,
                                  );
                                  if (picked != null) {
                                    setState(() => _range = picked);
                                  }
                                },
                                icon: const Icon(Icons.date_range),
                                label: Text(describeDateRange(_range)),
                              ),
                              DropdownButton<String?>(
                                value: _category,
                                hint: const Text('All categories'),
                                items: [
                                  const DropdownMenuItem<String?>(
                                    value: null,
                                    child: Text('All categories'),
                                  ),
                                  ...categories.map(
                                    (category) => DropdownMenuItem<String?>(
                                      value: category.name,
                                      child: Text('${category.emoji} ${category.name}'),
                                    ),
                                  ),
                                ],
                                onChanged: (value) => setState(() => _category = value),
                              ),
                              TextButton(
                                onPressed: () {
                                  setState(() {
                                    _range = currentMonthRange();
                                    _category = null;
                                  });
                                },
                                child: const Text('Reset'),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),
                      Wrap(
                        spacing: 16,
                        runSpacing: 16,
                        children: [
                          _MetricCard(
                            title: 'Filtered spend',
                            value: formatCurrency(
                              transactions.fold<double>(
                                0,
                                (sum, tx) => sum + tx.amount,
                              ),
                            ),
                            subtitle: '${transactions.length} transactions',
                          ),
                          _MetricCard(
                            title: 'Average transaction',
                            value: formatCurrency(
                              transactions.isEmpty
                                  ? 0
                                  : transactions.fold<double>(
                                          0,
                                          (sum, tx) => sum + tx.amount,
                                        ) /
                                      transactions.length,
                            ),
                            subtitle: _category ?? 'All categories',
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      Wrap(
                        spacing: 16,
                        runSpacing: 16,
                        children: [
                          SizedBox(
                            width: 720,
                            child: _ChartCard(
                              title: 'Spending trend',
                              child: trend.isEmpty
                                  ? const _EmptyChart(message: 'No data in the current range.')
                                  : SizedBox(
                                      height: 280,
                                      child: LineChart(
                                        LineChartData(
                                          minY: 0,
                                          gridData: const FlGridData(show: true),
                                          titlesData: minimalChartTitles(
                                            bottomBuilder: (value, meta) {
                                              final index = value.toInt();
                                              if (index < 0 || index >= trend.length) {
                                                return const SizedBox.shrink();
                                              }
                                              return Text(
                                                DateFormat('d MMM').format(trend[index].date),
                                                style: const TextStyle(fontSize: 10),
                                              );
                                            },
                                          ),
                                          lineBarsData: [
                                            LineChartBarData(
                                              isCurved: true,
                                              color: const Color(0xFF0B6E4F),
                                              barWidth: 3,
                                              spots: [
                                                for (var i = 0; i < trend.length; i++)
                                                  FlSpot(i.toDouble(), trend[i].total),
                                              ],
                                              dotData: const FlDotData(show: false),
                                            ),
                                          ],
                                        ),
                                      ),
                                    ),
                            ),
                          ),
                          SizedBox(
                            width: 420,
                            child: _ChartCard(
                              title: 'Category breakdown',
                              child: summaries.isEmpty
                                  ? const _EmptyChart(message: 'No category totals to plot.')
                                  : SizedBox(
                                      height: 280,
                                      child: PieChart(
                                        PieChartData(
                                          sectionsSpace: 2,
                                          centerSpaceRadius: 50,
                                          sections: [
                                            for (var i = 0; i < summaries.length; i++)
                                              PieChartSectionData(
                                                color: paletteColor(i),
                                                value: summaries[i].total,
                                                title:
                                                    '${(summaries[i].total / summaries.fold<double>(0, (sum, item) => sum + item.total) * 100).toStringAsFixed(0)}%',
                                                radius: 80,
                                                titleStyle: const TextStyle(
                                                  fontSize: 11,
                                                  fontWeight: FontWeight.bold,
                                                  color: Colors.white,
                                                ),
                                              ),
                                          ],
                                        ),
                                      ),
                                    ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Wrap(
                        spacing: 16,
                        runSpacing: 16,
                        children: [
                          SizedBox(
                            width: 720,
                            child: _ChartCard(
                              title: 'Category comparison',
                              child: topCategories.isEmpty
                                  ? const _EmptyChart(message: 'No categories match the filters.')
                                  : SizedBox(
                                      height: 300,
                                      child: BarChart(
                                        BarChartData(
                                          maxY: maxBarTotal * 1.15,
                                          gridData: const FlGridData(show: true),
                                          titlesData: minimalChartTitles(
                                            bottomBuilder: (value, meta) {
                                              final index = value.toInt();
                                              if (index < 0 || index >= topCategories.length) {
                                                return const SizedBox.shrink();
                                              }
                                              return Padding(
                                                padding: const EdgeInsets.only(top: 8),
                                                child: Text(
                                                  topCategories[index].label,
                                                  style: const TextStyle(fontSize: 10),
                                                ),
                                              );
                                            },
                                          ),
                                          barGroups: [
                                            for (var i = 0; i < topCategories.length; i++)
                                              BarChartGroupData(
                                                x: i,
                                                barRods: [
                                                  BarChartRodData(
                                                    toY: topCategories[i].total,
                                                    color: paletteColor(i),
                                                    borderRadius: BorderRadius.circular(6),
                                                  ),
                                                ],
                                              ),
                                          ],
                                        ),
                                      ),
                                    ),
                            ),
                          ),
                          SizedBox(
                            width: 420,
                            child: _ChartCard(
                              title: 'Budget progress',
                              child: budgets.isEmpty
                                  ? const _EmptyChart(message: 'No budget documents found.')
                                  : _BudgetProgressList(
                                      budgets: budgets,
                                      categoryTotals: {
                                        for (final summary in summaries)
                                          summary.name: summary.total,
                                      },
                                    ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                );
              },
            );
          },
        );
      },
    );
  }
}

class CategoriesPage extends StatelessWidget {
  const CategoriesPage({super.key});

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<List<DashboardCategory>>(
      stream: DashboardRepository.streamCategories(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const LoadingBody();
        }

        final categories = snapshot.data ?? const <DashboardCategory>[];

        return SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton.icon(
                  onPressed: () => showCategoryDialog(context, categories: categories),
                  icon: const Icon(Icons.add),
                  label: const Text('Add category'),
                ),
              ),
              const SizedBox(height: 16),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: categories
                        .map(
                          (category) => _CategoryRow(
                            category: category,
                            categories: categories,
                          ),
                        )
                        .toList(),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _TransactionsTable extends StatelessWidget {
  const _TransactionsTable({
    required this.transactions,
    required this.categories,
  });

  final List<DashboardTransaction> transactions;
  final List<DashboardCategory> categories;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        columns: const [
          DataColumn(label: Text('Date')),
          DataColumn(label: Text('Item')),
          DataColumn(label: Text('Category')),
          DataColumn(label: Text('Amount')),
          DataColumn(label: Text('Actions')),
        ],
        rows: transactions
            .map(
              (transaction) => DataRow(
                cells: [
                  DataCell(Text(DateFormat('dd MMM yyyy').format(transaction.timestamp))),
                  DataCell(Text(transaction.item)),
                  DataCell(Text(transaction.category)),
                  DataCell(Text(formatCurrency(transaction.amount))),
                  DataCell(
                    IconButton(
                      onPressed: () => showTransactionEditor(
                        context,
                        transaction: transaction,
                        categories: categories,
                      ),
                      icon: const Icon(Icons.edit_outlined),
                    ),
                  ),
                ],
              ),
            )
            .toList(),
      ),
    );
  }
}

class _TransactionTile extends StatelessWidget {
  const _TransactionTile({
    required this.transaction,
    required this.categories,
  });

  final DashboardTransaction transaction;
  final List<DashboardCategory> categories;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      title: Text(transaction.item),
      subtitle: Text(
        '${transaction.category} • ${DateFormat('dd MMM yyyy').format(transaction.timestamp)}',
      ),
      trailing: Wrap(
        spacing: 8,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Text(
            formatCurrency(transaction.amount),
            style: Theme.of(context).textTheme.titleMedium,
          ),
          IconButton(
            onPressed: () => showTransactionEditor(
              context,
              transaction: transaction,
              categories: categories,
            ),
            icon: const Icon(Icons.edit_outlined),
          ),
        ],
      ),
    );
  }
}

class _ReportSummaryCard extends StatelessWidget {
  const _ReportSummaryCard({
    required this.title,
    required this.transactions,
    required this.range,
  });

  final String title;
  final List<DashboardTransaction> transactions;
  final DateTimeRange range;

  @override
  Widget build(BuildContext context) {
    final total = transactions.fold<double>(0, (sum, tx) => sum + tx.amount);
    return SizedBox(
      width: 320,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Text(describeDateRange(range)),
              const SizedBox(height: 20),
              Text(
                formatCurrency(total),
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text('${transactions.length} transactions'),
            ],
          ),
        ),
      ),
    );
  }
}

class _HistoricalMonthPanel extends StatelessWidget {
  const _HistoricalMonthPanel({required this.range});

  final DateTimeRange range;

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<List<DashboardTransaction>>(
      stream: DashboardRepository.streamTransactions(range: range),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Padding(
            padding: EdgeInsets.all(20),
            child: CircularProgressIndicator(),
          );
        }

        final transactions = snapshot.data ?? const <DashboardTransaction>[];
        final totals = <String, double>{};
        for (final transaction in transactions) {
          totals.update(
            transaction.category,
            (value) => value + transaction.amount,
            ifAbsent: () => transaction.amount,
          );
        }

        final sortedEntries = totals.entries.toList()
          ..sort((a, b) => b.value.compareTo(a.value));

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              DateFormat('MMMM yyyy').format(range.start),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            Text(
              formatCurrency(
                transactions.fold<double>(0, (sum, tx) => sum + tx.amount),
              ),
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text('${transactions.length} transactions'),
            const SizedBox(height: 20),
            if (sortedEntries.isEmpty)
              const Text('No spending recorded for this month.')
            else
              ...sortedEntries.map(
                (entry) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    children: [
                      Expanded(child: Text(entry.key)),
                      Text(formatCurrency(entry.value)),
                    ],
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}

class _ChartCard extends StatelessWidget {
  const _ChartCard({
    required this.title,
    required this.child,
  });

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 16),
            child,
          ],
        ),
      ),
    );
  }
}

class _EmptyChart extends StatelessWidget {
  const _EmptyChart({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 220,
      child: Center(child: Text(message)),
    );
  }
}

class _BudgetProgressList extends StatelessWidget {
  const _BudgetProgressList({
    required this.budgets,
    required this.categoryTotals,
  });

  final Map<String, double> budgets;
  final Map<String, double> categoryTotals;

  @override
  Widget build(BuildContext context) {
    final rows = budgets.entries.toList()
      ..sort((a, b) => a.key.compareTo(b.key));

    return Column(
      children: rows.map((entry) {
        final spent = categoryTotals[entry.key] ?? 0;
        final limit = entry.value <= 0 ? 1.0 : entry.value;
        final progress = (spent / limit).clamp(0, 1).toDouble();
        final over = spent > entry.value;

        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(child: Text(entry.key)),
                  Text('${formatCurrency(spent)} / ${formatCurrency(entry.value)}'),
                ],
              ),
              const SizedBox(height: 8),
              LinearProgressIndicator(
                value: progress,
                minHeight: 10,
                color: over ? Colors.redAccent : const Color(0xFF0B6E4F),
                backgroundColor: Colors.black12,
              ),
            ],
          ),
        );
      }).toList(),
    );
  }
}

class _CategoryRow extends StatelessWidget {
  const _CategoryRow({
    required this.category,
    required this.categories,
  });

  final DashboardCategory category;
  final List<DashboardCategory> categories;

  @override
  Widget build(BuildContext context) {
    final movable = category.name != 'Other';
    final orderedCategories = categories.where((item) => item.name != 'Other').toList();
    final index = orderedCategories.indexWhere((item) => item.name == category.name);

    return ListTile(
      leading: CircleAvatar(child: Text(category.emoji)),
      title: Text(category.name),
      subtitle: Text('Order ${category.order}'),
      trailing: Wrap(
        spacing: 8,
        children: [
          IconButton(
            onPressed: movable && index > 0
                ? () => runWithSnackbar(
                      context,
                      () => DashboardRepository.moveCategory(
                        categories: categories,
                        category: category,
                        direction: -1,
                      ),
                      successMessage: 'Moved ${category.name} up.',
                    )
                : null,
            icon: const Icon(Icons.arrow_upward),
          ),
          IconButton(
            onPressed: movable && index != -1 && index < orderedCategories.length - 1
                ? () => runWithSnackbar(
                      context,
                      () => DashboardRepository.moveCategory(
                        categories: categories,
                        category: category,
                        direction: 1,
                      ),
                      successMessage: 'Moved ${category.name} down.',
                    )
                : null,
            icon: const Icon(Icons.arrow_downward),
          ),
          IconButton(
            onPressed: () => showCategoryDialog(
              context,
              categories: categories,
              original: category,
            ),
            icon: const Icon(Icons.edit_outlined),
          ),
          IconButton(
            onPressed: movable
                ? () async {
                    final confirmed = await showDialog<bool>(
                          context: context,
                          builder: (context) => AlertDialog(
                            title: Text('Delete ${category.name}?'),
                            content: const Text(
                              'Transactions and item mappings in this category will be reassigned to Other.',
                            ),
                            actions: [
                              TextButton(
                                onPressed: () => Navigator.of(context).pop(false),
                                child: const Text('Cancel'),
                              ),
                              FilledButton(
                                onPressed: () => Navigator.of(context).pop(true),
                                child: const Text('Delete'),
                              ),
                            ],
                          ),
                        ) ??
                        false;

                    if (!confirmed || !context.mounted) {
                      return;
                    }

                    await runWithSnackbar(
                      context,
                      () => DashboardRepository.deleteCategory(category),
                      successMessage: '${category.name} deleted and reassigned.',
                    );
                  }
                : null,
            icon: const Icon(Icons.delete_outline),
          ),
        ],
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.title,
    required this.value,
    required this.subtitle,
  });

  final String title;
  final String value;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 260,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 12),
              Text(value, style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 8),
              Text(subtitle),
            ],
          ),
        ),
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        child: Text(label),
      ),
    );
  }
}

enum _LandingTone { neutral, warning, error }

class _LandingShell extends StatelessWidget {
  const _LandingShell({
    required this.eyebrow,
    required this.title,
    required this.description,
    required this.highlights,
    required this.featureCard,
    required this.sidePanel,
  });

  final String eyebrow;
  final String title;
  final String description;
  final List<String> highlights;
  final Widget featureCard;
  final Widget sidePanel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isWide = MediaQuery.of(context).size.width >= 1100;

    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFFF8FBF7), Color(0xFFF1F6FF), Color(0xFFFFF8EF)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Stack(
          children: [
            Positioned(
              top: -120,
              left: -60,
              child: _GlowOrb(
                color: const Color(0xFF91E4C1).withValues(alpha: 0.35),
                size: 320,
              ),
            ),
            Positioned(
              top: 80,
              right: -40,
              child: _GlowOrb(
                color: const Color(0xFFBBD6FF).withValues(alpha: 0.38),
                size: 280,
              ),
            ),
            SafeArea(
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1280),
                  child: Padding(
                    padding: const EdgeInsets.all(28),
                    child: Column(
                      children: [
                        Row(
                          children: [
                            const _Wordmark(),
                            const Spacer(),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 14,
                                vertical: 10,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.8),
                                borderRadius: BorderRadius.circular(999),
                                border: Border.all(
                                  color: theme.colorScheme.outlineVariant,
                                ),
                              ),
                              child: Text(
                                'Private finance dashboard',
                                style: theme.textTheme.labelLarge,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 28),
                        Expanded(
                          child: isWide
                              ? Row(
                                  crossAxisAlignment: CrossAxisAlignment.stretch,
                                  children: [
                                    Expanded(
                                      flex: 6,
                                      child: _HeroStory(
                                        eyebrow: eyebrow,
                                        title: title,
                                        description: description,
                                        highlights: highlights,
                                        featureCard: featureCard,
                                      ),
                                    ),
                                    const SizedBox(width: 24),
                                    Expanded(
                                      flex: 4,
                                      child: sidePanel,
                                    ),
                                  ],
                                )
                              : ListView(
                                  children: [
                                    _HeroStory(
                                      eyebrow: eyebrow,
                                      title: title,
                                      description: description,
                                      highlights: highlights,
                                      featureCard: featureCard,
                                    ),
                                    const SizedBox(height: 20),
                                    sidePanel,
                                  ],
                                ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HeroStory extends StatelessWidget {
  const _HeroStory({
    required this.eyebrow,
    required this.title,
    required this.description,
    required this.highlights,
    required this.featureCard,
  });

  final String eyebrow;
  final String title;
  final String description;
  final List<String> highlights;
  final Widget featureCard;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: const Color(0xFFDBF1E6),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Text(
            eyebrow.toUpperCase(),
            style: theme.textTheme.labelLarge?.copyWith(
              letterSpacing: 1.1,
              fontWeight: FontWeight.w700,
              color: const Color(0xFF0B6E4F),
            ),
          ),
        ),
        const SizedBox(height: 20),
        Text(
          title,
          style: theme.textTheme.displayMedium?.copyWith(
            height: 1.05,
            fontWeight: FontWeight.w700,
            color: const Color(0xFF193225),
          ),
        ),
        const SizedBox(height: 18),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 700),
          child: Text(
            description,
            style: theme.textTheme.titleMedium?.copyWith(
              height: 1.45,
              color: const Color(0xFF42554A),
            ),
          ),
        ),
        const SizedBox(height: 24),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: highlights.map((text) => _HighlightPill(text: text)).toList(),
        ),
        const SizedBox(height: 28),
        Expanded(child: featureCard),
      ],
    );
  }
}

class _PreviewCard extends StatelessWidget {
  const _PreviewCard({
    required this.title,
    required this.subtitle,
    required this.child,
  });

  final String title;
  final String subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      color: Colors.white.withValues(alpha: 0.88),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: theme.textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text(
              subtitle,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: const Color(0xFF5A6C61),
              ),
            ),
            const SizedBox(height: 20),
            Expanded(
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: const Color(0xFFF7FAF8),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: theme.colorScheme.outlineVariant),
                ),
                child: child,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PreviewDashboardCard extends StatelessWidget {
  const _PreviewDashboardCard();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return _PreviewCard(
      title: 'What the dashboard gives you',
      subtitle:
          'A web-first control surface for monitoring, filtering, and correcting expense data.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              Expanded(
                child: _MiniStat(title: 'Monthly spend', value: '\$2,184'),
              ),
              SizedBox(width: 12),
              Expanded(
                child: _MiniStat(title: 'Active categories', value: '8'),
              ),
              SizedBox(width: 12),
              Expanded(
                child: _MiniStat(title: 'Transactions', value: '146'),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: theme.colorScheme.outlineVariant),
              ),
              child: Column(
                children: const [
                  _MiniChartBar(widthFactor: 0.88, color: Color(0xFF0B6E4F)),
                  SizedBox(height: 10),
                  _MiniChartBar(widthFactor: 0.64, color: Color(0xFF1768AC)),
                  SizedBox(height: 10),
                  _MiniChartBar(widthFactor: 0.51, color: Color(0xFFE67E22)),
                  SizedBox(height: 22),
                  _InsightRow(
                    label: 'Top category',
                    value: 'Food & Drink',
                  ),
                  SizedBox(height: 10),
                  _InsightRow(
                    label: 'Most recent correction',
                    value: 'Grab date fixed',
                  ),
                  SizedBox(height: 10),
                  _InsightRow(
                    label: 'Filters',
                    value: 'Category • Date range',
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SignInPanel extends StatelessWidget {
  const _SignInPanel({
    required this.busy,
    required this.error,
    required this.onSignIn,
  });

  final bool busy;
  final String? error;
  final Future<void> Function() onSignIn;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      color: Colors.white.withValues(alpha: 0.94),
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(14),
              decoration: const BoxDecoration(
                color: Color(0xFFE9F2FF),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.shield_outlined, size: 28),
            ),
            const SizedBox(height: 20),
            Text(
              'Sign in with Google',
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              'Only Firebase Auth users with a matching '
              '`dashboard_admins/<uid>` document can access or edit data.',
              style: theme.textTheme.bodyLarge?.copyWith(
                height: 1.45,
                color: const Color(0xFF4B5F53),
              ),
            ),
            const SizedBox(height: 24),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFFF7FAF8),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: theme.colorScheme.outlineVariant),
              ),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _InsightRow(label: 'Access model', value: 'Single-owner dashboard'),
                  SizedBox(height: 10),
                  _InsightRow(label: 'Data path', value: 'Direct Firestore reads'),
                  SizedBox(height: 10),
                  _InsightRow(label: 'Hosting', value: 'Firebase Hosting'),
                ],
              ),
            ),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: busy ? null : onSignIn,
                icon: busy
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.login),
                label: Text(busy ? 'Signing in...' : 'Continue with Google'),
              ),
            ),
            if (error != null) ...[
              const SizedBox(height: 14),
              Text(
                error!,
                style: TextStyle(color: theme.colorScheme.error),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SideStatusCard extends StatelessWidget {
  const _SideStatusCard({
    required this.icon,
    required this.title,
    required this.description,
    required this.tone,
    this.action,
  });

  final IconData icon;
  final String title;
  final String description;
  final _LandingTone tone;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final config = switch (tone) {
      _LandingTone.neutral => (
          background: const Color(0xFFF7FAF8),
          accent: const Color(0xFF0B6E4F),
        ),
      _LandingTone.warning => (
          background: const Color(0xFFFFF5E8),
          accent: const Color(0xFFB96D14),
        ),
      _LandingTone.error => (
          background: const Color(0xFFFFEEF0),
          accent: const Color(0xFFC4374F),
        ),
    };

    return Card(
      color: Colors.white.withValues(alpha: 0.94),
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: config.background,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(icon, color: config.accent, size: 30),
            ),
            const SizedBox(height: 20),
            Text(
              title,
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              description,
              style: theme.textTheme.bodyLarge?.copyWith(
                height: 1.45,
                color: const Color(0xFF4B5F53),
              ),
            ),
            if (action != null) ...[
              const SizedBox(height: 24),
              action!,
            ],
          ],
        ),
      ),
    );
  }
}

class _Wordmark extends StatelessWidget {
  const _Wordmark();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            gradient: const LinearGradient(
              colors: [Color(0xFF0B6E4F), Color(0xFF27A36F)],
            ),
          ),
          child: const Icon(Icons.insights, color: Colors.white),
        ),
        const SizedBox(width: 12),
        Text(
          'Expense Monitor',
          style: theme.textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.w700,
            color: const Color(0xFF193225),
          ),
        ),
      ],
    );
  }
}

class _HighlightPill extends StatelessWidget {
  const _HighlightPill({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.82),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: Theme.of(context).colorScheme.outlineVariant,
        ),
      ),
      child: Text(text),
    );
  }
}

class _GlowOrb extends StatelessWidget {
  const _GlowOrb({required this.color, required this.size});

  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: RadialGradient(
            colors: [color, color.withValues(alpha: 0)],
          ),
        ),
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  const _MiniStat({required this.title, required this.value});

  final String title;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF7FAF8),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 6),
          Text(
            value,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
        ],
      ),
    );
  }
}

class _MiniChartBar extends StatelessWidget {
  const _MiniChartBar({
    required this.widthFactor,
    required this.color,
  });

  final double widthFactor;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: FractionallySizedBox(
        widthFactor: widthFactor,
        child: Container(
          height: 14,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(999),
          ),
        ),
      ),
    );
  }
}

class _InsightRow extends StatelessWidget {
  const _InsightRow({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Expanded(
          child: Text(
            label,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: const Color(0xFF6A7B71),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Text(
          value,
          style: theme.textTheme.bodyMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: const Color(0xFF22382D),
          ),
        ),
      ],
    );
  }
}

class LoadingScaffold extends StatelessWidget {
  const LoadingScaffold({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            Text(message),
          ],
        ),
      ),
    );
  }
}

class LoadingBody extends StatelessWidget {
  const LoadingBody({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(child: CircularProgressIndicator());
  }
}

class DashboardTransaction {
  DashboardTransaction({
    required this.id,
    required this.item,
    required this.amount,
    required this.category,
    required this.timestamp,
    required this.chatId,
  });

  factory DashboardTransaction.fromJson(Map<String, dynamic> data) {
    return DashboardTransaction(
      id: (data['_doc_id'] ?? data['id'] ?? '').toString(),
      item: (data['item'] ?? '').toString(),
      amount: (data['amount'] as num?)?.toDouble() ?? 0,
      category: (data['category'] ?? 'Other').toString(),
      timestamp: DateTime.tryParse((data['timestamp'] ?? '').toString()) ??
          DateTime.fromMillisecondsSinceEpoch(0),
      chatId: (data['chat_id'] as num?)?.toInt() ?? 0,
    );
  }

  factory DashboardTransaction.fromDocument(
    DocumentSnapshot<Map<String, dynamic>> document,
  ) {
    final data = document.data() ?? const <String, dynamic>{};
    return DashboardTransaction.fromJson({
      ...data,
      '_doc_id': document.id,
    });
  }

  final String id;
  final String item;
  final double amount;
  final String category;
  final DateTime timestamp;
  final int chatId;
}

class DashboardCategory {
  DashboardCategory({
    required this.name,
    required this.emoji,
    required this.order,
  });

  factory DashboardCategory.fromJson(Map<String, dynamic> data) {
    return DashboardCategory(
      name: (data['name'] ?? '').toString(),
      emoji: (data['emoji'] ?? '🏷️').toString(),
      order: (data['order'] as num?)?.toInt() ?? 9998,
    );
  }

  factory DashboardCategory.fromDocument(
    DocumentSnapshot<Map<String, dynamic>> document,
  ) {
    final data = document.data() ?? const <String, dynamic>{};
    return DashboardCategory(
      name: (data['name'] ?? document.id).toString(),
      emoji: (data['emoji'] ?? '🏷️').toString(),
      order: (data['order'] as num?)?.toInt() ?? 9998,
    );
  }

  final String name;
  final String emoji;
  final int order;
}

class CategorySummary {
  CategorySummary({
    required this.name,
    required this.label,
    required this.total,
  });

  final String name;
  final String label;
  final double total;
}

class TrendPoint {
  TrendPoint({required this.date, required this.total});

  final DateTime date;
  final double total;
}

class DashboardSession {
  const DashboardSession({
    required this.username,
    required this.chatId,
  });

  factory DashboardSession.fromJson(Map<String, dynamic> json) {
    return DashboardSession(
      username: (json['username'] ?? '').toString(),
      chatId: (json['chat_id'] as num?)?.toInt() ?? 0,
    );
  }

  final String username;
  final int chatId;
}

class DashboardApiException implements Exception {
  DashboardApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

class LegacyDashboardRepository {
  static final http.Client _client = createDashboardHttpClient();
  static final StreamController<int> _refreshController =
      StreamController<int>.broadcast();
  static int _refreshTick = 0;
  static const String _defaultApiBaseUrl =
      'https://finance-bot-318969558548.asia-southeast1.run.app';
  static const String _configuredApiBaseUrl =
      String.fromEnvironment('DASHBOARD_API_BASE_URL');

  static String get _apiBaseUrl =>
      (_configuredApiBaseUrl.isNotEmpty
              ? _configuredApiBaseUrl
              : _defaultApiBaseUrl)
          .replaceAll(RegExp(r'/$'), '');

  static Uri _uri(
    String path, {
    Map<String, String?> query = const {},
  }) {
    final cleaned = <String, String>{};
    for (final entry in query.entries) {
      final value = entry.value;
      if (value != null && value.isNotEmpty) {
        cleaned[entry.key] = value;
      }
    }
    return Uri.parse('$_apiBaseUrl$path').replace(queryParameters: cleaned);
  }

  static void _notifyRefresh() {
    _refreshController.add(++_refreshTick);
  }

  static Stream<T> _refreshableStream<T>(Future<T> Function() loader) async* {
    yield await loader();
    yield* _refreshController.stream.asyncMap((_) => loader());
  }

  static dynamic _decodeJson(http.Response response) {
    if (response.body.isEmpty) {
      return null;
    }
    return jsonDecode(response.body);
  }

  static Future<dynamic> _requestJson(
    String method,
    String path, {
    Map<String, String?> query = const {},
    Object? body,
  }) async {
    final uri = _uri(path, query: query);
    const headers = {'Content-Type': 'application/json'};
    late final http.Response response;

    switch (method) {
      case 'GET':
        response = await _client.get(uri, headers: headers);
        break;
      case 'POST':
        response = await _client.post(
          uri,
          headers: headers,
          body: body == null ? null : jsonEncode(body),
        );
        break;
      case 'PATCH':
        response = await _client.patch(
          uri,
          headers: headers,
          body: body == null ? null : jsonEncode(body),
        );
        break;
      case 'DELETE':
        response = await _client.delete(uri, headers: headers);
        break;
      default:
        throw UnsupportedError('Unsupported method $method');
    }

    final decoded = _decodeJson(response);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return decoded;
    }
    final message = decoded is Map<String, dynamic>
        ? (decoded['detail'] ?? decoded['message'] ?? 'Request failed.')
              .toString()
        : 'Request failed.';
    throw DashboardApiException(message);
  }

  static Future<DashboardSession?> fetchSession() async {
    final data = await _requestJson('GET', '/dashboard/auth/session');
    if (data is! Map<String, dynamic> || data['authenticated'] != true) {
      return null;
    }
    return DashboardSession.fromJson(data);
  }

  static Future<void> login({
    required String username,
    required String password,
  }) async {
    await _requestJson(
      'POST',
      '/dashboard/auth/login',
      body: {
        'username': username.trim(),
        'password': password,
      },
    );
    _notifyRefresh();
  }

  static Future<void> logout() async {
    await _requestJson('POST', '/dashboard/auth/logout');
    _notifyRefresh();
  }

  static Stream<List<DashboardTransaction>> streamTransactions({
    required DateTimeRange range,
    String? category,
  }) {
    return _refreshableStream(() async {
      final data = await _requestJson(
        'GET',
        '/dashboard/transactions',
        query: {
          'start': startOfDay(range.start).toIso8601String(),
          'end': endExclusive(range.end).toIso8601String(),
          'category': category,
        },
      );
      final raw = (data as Map<String, dynamic>)['transactions'] as List<dynamic>? ??
          const [];
      return raw
          .whereType<Map<String, dynamic>>()
          .map(DashboardTransaction.fromJson)
          .toList();
    });
  }

  static Stream<List<DashboardCategory>> streamCategories() {
    return _refreshableStream(() async {
      final data = await _requestJson('GET', '/dashboard/categories');
      final raw =
          (data as Map<String, dynamic>)['categories'] as List<dynamic>? ?? const [];
      final categories = raw
          .whereType<Map<String, dynamic>>()
          .map(DashboardCategory.fromJson)
          .toList();
      categories.sort((a, b) => a.order.compareTo(b.order));
      return categories;
    });
  }

  static Stream<Map<String, double>> streamBudgets() {
    return _refreshableStream(() async {
      final data = await _requestJson('GET', '/dashboard/budgets');
      final raw = (data as Map<String, dynamic>)['budgets'] as Map<String, dynamic>? ??
          const <String, dynamic>{};
      final budgets = <String, double>{};
      for (final entry in raw.entries) {
        if (entry.value is num) {
          budgets[entry.key] = (entry.value as num).toDouble();
        }
      }
      return budgets;
    });
  }

  static Future<void> updateTransaction({
    required DashboardTransaction transaction,
    required String item,
    required double amount,
    required String category,
    required DateTime date,
  }) async {
    final current = transaction.timestamp;
    final updatedTimestamp = DateTime(
      date.year,
      date.month,
      date.day,
      current.hour,
      current.minute,
      current.second,
      current.millisecond,
      current.microsecond,
    );

    await _requestJson(
      'PATCH',
      '/dashboard/transactions/${Uri.encodeComponent(transaction.id)}',
      body: {
        'item': item.trim(),
        'amount': amount,
        'category': category,
        'timestamp': updatedTimestamp.toIso8601String(),
      },
    );
    _notifyRefresh();
  }

  static Future<void> createCategory({
    required String name,
    required String emoji,
    required List<DashboardCategory> currentCategories,
  }) async {
    final normalizedName = titleCase(name);
    if (normalizedName.isEmpty) {
      throw Exception('Category name cannot be empty.');
    }

    final exists = await _firestore
        .collection('category_list')
        .doc(normalizedName)
        .get();
    if (exists.exists) {
      throw Exception('Category $normalizedName already exists.');
    }

    final nonOther = currentCategories.where((category) => category.name != 'Other');
    final maxOrder = nonOther.fold<int>(0, (value, category) {
      return math.max(value, category.order);
    });

    await _firestore.collection('category_list').doc(normalizedName).set({
      'name': normalizedName,
      'emoji': emoji.trim().isEmpty ? '🏷️' : emoji.trim(),
      'order': maxOrder + 1,
    });
  }

  static Future<void> updateCategory({
    required DashboardCategory original,
    required String name,
    required String emoji,
  }) async {
    final normalizedName = titleCase(name);
    if (normalizedName.isEmpty) {
      throw Exception('Category name cannot be empty.');
    }
    if (original.name == 'Other' && normalizedName != 'Other') {
      throw Exception('The Other category cannot be renamed.');
    }

    if (normalizedName == original.name) {
      await _firestore.collection('category_list').doc(original.name).update({
        'emoji': emoji.trim().isEmpty ? original.emoji : emoji.trim(),
      });
      return;
    }

    final targetDoc =
        await _firestore.collection('category_list').doc(normalizedName).get();
    if (targetDoc.exists) {
      throw Exception('Category $normalizedName already exists.');
    }

    final batch = _firestore.batch();
    final oldRef = _firestore.collection('category_list').doc(original.name);
    final newRef = _firestore.collection('category_list').doc(normalizedName);

    batch.set(newRef, {
      'name': normalizedName,
      'emoji': emoji.trim().isEmpty ? original.emoji : emoji.trim(),
      'order': original.order,
    });
    batch.delete(oldRef);

    final transactionDocs = await _firestore
        .collection('transactions')
        .where('category', isEqualTo: original.name)
        .get();
    for (final doc in transactionDocs.docs) {
      batch.update(doc.reference, {'category': normalizedName});
    }

    final mappingDocs = await _firestore
        .collection('category_map')
        .where('category', isEqualTo: original.name)
        .get();
    for (final doc in mappingDocs.docs) {
      batch.update(doc.reference, {'category': normalizedName});
    }

    await batch.commit();
  }

  static Future<void> deleteCategory(DashboardCategory category) async {
    if (category.name == 'Other') {
      throw Exception('The Other category cannot be removed.');
    }

    final batch = _firestore.batch();

    final transactionDocs = await _firestore
        .collection('transactions')
        .where('category', isEqualTo: category.name)
        .get();
    for (final doc in transactionDocs.docs) {
      batch.update(doc.reference, {'category': 'Other'});
    }

    final mappingDocs = await _firestore
        .collection('category_map')
        .where('category', isEqualTo: category.name)
        .get();
    for (final doc in mappingDocs.docs) {
      batch.update(doc.reference, {'category': 'Other'});
    }

    batch.delete(_firestore.collection('category_list').doc(category.name));
    await batch.commit();
  }

  static Future<void> moveCategory({
    required List<DashboardCategory> categories,
    required DashboardCategory category,
    required int direction,
  }) async {
    if (category.name == 'Other') {
      throw Exception('The Other category cannot be reordered.');
    }

    final movable = categories.where((item) => item.name != 'Other').toList()
      ..sort((a, b) => a.order.compareTo(b.order));
    final index = movable.indexWhere((item) => item.name == category.name);
    final targetIndex = index + direction;
    if (index < 0 || targetIndex < 0 || targetIndex >= movable.length) {
      return;
    }

    final target = movable[targetIndex];
    final batch = _firestore.batch();
    batch.update(
      _firestore.collection('category_list').doc(category.name),
      {'order': target.order},
    );
    batch.update(
      _firestore.collection('category_list').doc(target.name),
      {'order': category.order},
    );
    await batch.commit();
  }
}

class DashboardSession {
  const DashboardSession({
    required this.username,
    required this.chatId,
  });

  factory DashboardSession.fromJson(Map<String, dynamic> json) {
    return DashboardSession(
      username: (json['username'] ?? '').toString(),
      chatId: (json['chat_id'] as num?)?.toInt() ?? 0,
    );
  }

  final String username;
  final int chatId;
}

class DashboardApiException implements Exception {
  DashboardApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

class DashboardRepository {
  static final http.Client _client = createDashboardHttpClient();
  static final StreamController<int> _refreshController =
      StreamController<int>.broadcast();
  static int _refreshTick = 0;
  static const String _defaultApiBaseUrl =
      'https://finance-bot-318969558548.asia-southeast1.run.app';
  static const String _configuredApiBaseUrl =
      String.fromEnvironment('DASHBOARD_API_BASE_URL');

  static String get _apiBaseUrl =>
      (_configuredApiBaseUrl.isNotEmpty
              ? _configuredApiBaseUrl
              : _defaultApiBaseUrl)
          .replaceAll(RegExp(r'/$'), '');

  static Uri _uri(
    String path, {
    Map<String, String?> query = const {},
  }) {
    final cleaned = <String, String>{};
    for (final entry in query.entries) {
      final value = entry.value;
      if (value != null && value.isNotEmpty) {
        cleaned[entry.key] = value;
      }
    }
    return Uri.parse('$_apiBaseUrl$path').replace(queryParameters: cleaned);
  }

  static void _notifyRefresh() {
    _refreshController.add(++_refreshTick);
  }

  static Stream<T> _refreshableStream<T>(Future<T> Function() loader) async* {
    yield await loader();
    yield* _refreshController.stream.asyncMap((_) => loader());
  }

  static dynamic _decodeJson(http.Response response) {
    if (response.body.isEmpty) {
      return null;
    }
    return jsonDecode(response.body);
  }

  static Future<dynamic> _requestJson(
    String method,
    String path, {
    Map<String, String?> query = const {},
    Object? body,
  }) async {
    final uri = _uri(path, query: query);
    const headers = {'Content-Type': 'application/json'};
    late final http.Response response;

    switch (method) {
      case 'GET':
        response = await _client.get(uri, headers: headers);
        break;
      case 'POST':
        response = await _client.post(
          uri,
          headers: headers,
          body: body == null ? null : jsonEncode(body),
        );
        break;
      case 'PATCH':
        response = await _client.patch(
          uri,
          headers: headers,
          body: body == null ? null : jsonEncode(body),
        );
        break;
      case 'DELETE':
        response = await _client.delete(uri, headers: headers);
        break;
      default:
        throw UnsupportedError('Unsupported method $method');
    }

    final decoded = _decodeJson(response);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return decoded;
    }

    final message = decoded is Map<String, dynamic>
        ? (decoded['detail'] ?? decoded['message'] ?? 'Request failed.')
              .toString()
        : 'Request failed.';
    throw DashboardApiException(message);
  }

  static Future<DashboardSession?> fetchSession() async {
    final data = await _requestJson('GET', '/dashboard/auth/session');
    if (data is! Map<String, dynamic> || data['authenticated'] != true) {
      return null;
    }
    return DashboardSession.fromJson(data);
  }

  static Future<void> login({
    required String username,
    required String password,
  }) async {
    await _requestJson(
      'POST',
      '/dashboard/auth/login',
      body: {
        'username': username.trim(),
        'password': password,
      },
    );
    _notifyRefresh();
  }

  static Future<void> logout() async {
    await _requestJson('POST', '/dashboard/auth/logout');
    _notifyRefresh();
  }

  static Stream<List<DashboardTransaction>> streamTransactions({
    required DateTimeRange range,
    String? category,
  }) {
    return _refreshableStream(() async {
      final data = await _requestJson(
        'GET',
        '/dashboard/transactions',
        query: {
          'start': startOfDay(range.start).toIso8601String(),
          'end': endExclusive(range.end).toIso8601String(),
          'category': category,
        },
      );
      final raw = (data as Map<String, dynamic>)['transactions'] as List<dynamic>? ??
          const [];
      return raw
          .whereType<Map<String, dynamic>>()
          .map(DashboardTransaction.fromJson)
          .toList();
    });
  }

  static Stream<List<DashboardCategory>> streamCategories() {
    return _refreshableStream(() async {
      final data = await _requestJson('GET', '/dashboard/categories');
      final raw =
          (data as Map<String, dynamic>)['categories'] as List<dynamic>? ?? const [];
      final categories = raw
          .whereType<Map<String, dynamic>>()
          .map(DashboardCategory.fromJson)
          .toList();
      categories.sort((a, b) => a.order.compareTo(b.order));
      return categories;
    });
  }

  static Stream<Map<String, double>> streamBudgets() {
    return _refreshableStream(() async {
      final data = await _requestJson('GET', '/dashboard/budgets');
      final raw = (data as Map<String, dynamic>)['budgets'] as Map<String, dynamic>? ??
          const <String, dynamic>{};
      final budgets = <String, double>{};
      for (final entry in raw.entries) {
        if (entry.value is num) {
          budgets[entry.key] = (entry.value as num).toDouble();
        }
      }
      return budgets;
    });
  }

  static Future<void> updateTransaction({
    required DashboardTransaction transaction,
    required String item,
    required double amount,
    required String category,
    required DateTime date,
  }) async {
    final current = transaction.timestamp;
    final updatedTimestamp = DateTime(
      date.year,
      date.month,
      date.day,
      current.hour,
      current.minute,
      current.second,
      current.millisecond,
      current.microsecond,
    );

    await _requestJson(
      'PATCH',
      '/dashboard/transactions/${Uri.encodeComponent(transaction.id)}',
      body: {
        'item': item.trim(),
        'amount': amount,
        'category': category,
        'timestamp': updatedTimestamp.toIso8601String(),
      },
    );
    _notifyRefresh();
  }

  static Future<void> createCategory({
    required String name,
    required String emoji,
    required List<DashboardCategory> currentCategories,
  }) async {
    final normalizedName = titleCase(name);
    if (normalizedName.isEmpty) {
      throw Exception('Category name cannot be empty.');
    }

    await _requestJson(
      'POST',
      '/dashboard/categories',
      body: {
        'name': normalizedName,
        'emoji': emoji.trim().isEmpty ? '🏷️' : emoji.trim(),
      },
    );
    _notifyRefresh();
  }

  static Future<void> updateCategory({
    required DashboardCategory original,
    required String name,
    required String emoji,
  }) async {
    final normalizedName = titleCase(name);
    if (normalizedName.isEmpty) {
      throw Exception('Category name cannot be empty.');
    }
    if (original.name == 'Other' && normalizedName != 'Other') {
      throw Exception('The Other category cannot be renamed.');
    }

    await _requestJson(
      'PATCH',
      '/dashboard/categories/${Uri.encodeComponent(original.name)}',
      body: {
        'name': normalizedName,
        'emoji': emoji.trim().isEmpty ? original.emoji : emoji.trim(),
      },
    );
    _notifyRefresh();
  }

  static Future<void> deleteCategory(DashboardCategory category) async {
    if (category.name == 'Other') {
      throw Exception('The Other category cannot be removed.');
    }

    await _requestJson(
      'DELETE',
      '/dashboard/categories/${Uri.encodeComponent(category.name)}',
    );
    _notifyRefresh();
  }

  static Future<void> moveCategory({
    required List<DashboardCategory> categories,
    required DashboardCategory category,
    required int direction,
  }) async {
    if (category.name == 'Other') {
      throw Exception('The Other category cannot be reordered.');
    }

    final movable = categories.where((item) => item.name != 'Other').toList()
      ..sort((a, b) => a.order.compareTo(b.order));
    final index = movable.indexWhere((item) => item.name == category.name);
    final targetIndex = index + direction;
    if (index < 0 || targetIndex < 0 || targetIndex >= movable.length) {
      return;
    }

    await _requestJson(
      'POST',
      '/dashboard/categories/${Uri.encodeComponent(category.name)}/move',
      body: {'direction': direction},
    );
    _notifyRefresh();
  }
}

Future<void> showTransactionEditor(
  BuildContext context, {
  required DashboardTransaction transaction,
  required List<DashboardCategory> categories,
}) async {
  final itemController = TextEditingController(text: transaction.item);
  final amountController =
      TextEditingController(text: transaction.amount.toStringAsFixed(2));
  var category = transaction.category;
  var date = transaction.timestamp;
  var saving = false;
  String? errorText;

  await showDialog<void>(
    context: context,
    builder: (context) {
      return StatefulBuilder(
        builder: (context, setState) {
          return AlertDialog(
            title: const Text('Edit transaction'),
            content: SizedBox(
              width: 420,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: itemController,
                    decoration: const InputDecoration(labelText: 'Item'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: amountController,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Amount'),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: categories.any((entry) => entry.name == category)
                        ? category
                        : null,
                    items: categories
                        .map(
                          (entry) => DropdownMenuItem(
                            value: entry.name,
                            child: Text('${entry.emoji} ${entry.name}'),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value != null) {
                        setState(() => category = value);
                      }
                    },
                    decoration: const InputDecoration(labelText: 'Category'),
                  ),
                  const SizedBox(height: 12),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      onPressed: () async {
                        final picked = await showDatePicker(
                          context: context,
                          initialDate: date,
                          firstDate: DateTime(2020),
                          lastDate: DateTime.now().add(const Duration(days: 365)),
                        );
                        if (picked != null) {
                          setState(() => date = picked);
                        }
                      },
                      icon: const Icon(Icons.event),
                      label: Text(DateFormat('dd MMM yyyy').format(date)),
                    ),
                  ),
                  if (errorText != null) ...[
                    const SizedBox(height: 12),
                    Text(
                      errorText!,
                      style: TextStyle(color: Theme.of(context).colorScheme.error),
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.of(context).pop(),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: saving
                    ? null
                    : () async {
                        final amount = double.tryParse(amountController.text.trim());
                        if (itemController.text.trim().isEmpty ||
                            amount == null ||
                            amount <= 0) {
                          setState(() {
                            errorText = 'Enter a valid item and positive amount.';
                          });
                          return;
                        }

                        setState(() {
                          saving = true;
                          errorText = null;
                        });

                        try {
                          await DashboardRepository.updateTransaction(
                            transaction: transaction,
                            item: itemController.text,
                            amount: amount,
                            category: category,
                            date: date,
                          );
                          if (context.mounted) {
                            Navigator.of(context).pop();
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Transaction updated.')),
                            );
                          }
                        } catch (error) {
                          setState(() => errorText = error.toString());
                        } finally {
                          if (context.mounted) {
                            setState(() => saving = false);
                          }
                        }
                      },
                child: Text(saving ? 'Saving...' : 'Save'),
              ),
            ],
          );
        },
      );
    },
  );
}

Future<void> showCategoryDialog(
  BuildContext context, {
  required List<DashboardCategory> categories,
  DashboardCategory? original,
}) async {
  final nameController = TextEditingController(text: original?.name ?? '');
  final emojiController = TextEditingController(text: original?.emoji ?? '');
  var saving = false;
  String? errorText;

  await showDialog<void>(
    context: context,
    builder: (context) => StatefulBuilder(
      builder: (context, setState) {
        return AlertDialog(
          title: Text(original == null ? 'Add category' : 'Edit category'),
          content: SizedBox(
            width: 420,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameController,
                  decoration: const InputDecoration(labelText: 'Name'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: emojiController,
                  decoration: const InputDecoration(labelText: 'Emoji'),
                ),
                if (errorText != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    errorText!,
                    style: TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: saving ? null : () => Navigator.of(context).pop(),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: saving
                  ? null
                  : () async {
                      setState(() {
                        saving = true;
                        errorText = null;
                      });
                      try {
                        if (original == null) {
                          await DashboardRepository.createCategory(
                            name: nameController.text,
                            emoji: emojiController.text,
                            currentCategories: categories,
                          );
                        } else {
                          await DashboardRepository.updateCategory(
                            original: original,
                            name: nameController.text,
                            emoji: emojiController.text,
                          );
                        }
                        if (context.mounted) {
                          Navigator.of(context).pop();
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(
                                original == null
                                    ? 'Category created.'
                                    : 'Category updated.',
                              ),
                            ),
                          );
                        }
                      } catch (error) {
                        setState(() => errorText = error.toString());
                      } finally {
                        if (context.mounted) {
                          setState(() => saving = false);
                        }
                      }
                    },
              child: Text(saving ? 'Saving...' : 'Save'),
            ),
          ],
        );
      },
    ),
  );
}

Future<void> runWithSnackbar(
  BuildContext context,
  Future<void> Function() action, {
  required String successMessage,
}) async {
  try {
    await action();
    if (!context.mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(successMessage)),
    );
  } catch (error) {
    if (!context.mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(error.toString())),
    );
  }
}

List<DashboardTransaction> filterTransactionsByRange(
  List<DashboardTransaction> transactions,
  DateTimeRange range,
) {
  final start = startOfDay(range.start);
  final end = endExclusive(range.end);
  return transactions
      .where(
        (tx) => !tx.timestamp.isBefore(start) && tx.timestamp.isBefore(end),
      )
      .toList();
}

List<CategorySummary> buildCategorySummaries(
  List<DashboardTransaction> transactions,
  List<DashboardCategory> categories,
) {
  final emojiByName = {
    for (final category in categories) category.name: category.emoji,
  };
  final totals = <String, double>{};
  for (final transaction in transactions) {
    totals.update(
      transaction.category,
      (value) => value + transaction.amount,
      ifAbsent: () => transaction.amount,
    );
  }

  final summaries = totals.entries
      .map(
        (entry) => CategorySummary(
          name: entry.key,
          label: '${emojiByName[entry.key] ?? '🏷️'} ${entry.key}',
          total: entry.value,
        ),
      )
      .toList()
    ..sort((a, b) => b.total.compareTo(a.total));
  return summaries;
}

List<TrendPoint> buildTrendSeries(List<DashboardTransaction> transactions) {
  final totals = <DateTime, double>{};
  for (final transaction in transactions) {
    final date = DateTime(
      transaction.timestamp.year,
      transaction.timestamp.month,
      transaction.timestamp.day,
    );
    totals.update(date, (value) => value + transaction.amount,
        ifAbsent: () => transaction.amount);
  }

  final points = totals.entries
      .map((entry) => TrendPoint(date: entry.key, total: entry.value))
      .toList()
    ..sort((a, b) => a.date.compareTo(b.date));
  return points;
}

FlTitlesData minimalChartTitles({
  required Widget Function(double value, TitleMeta meta) bottomBuilder,
}) {
  return FlTitlesData(
    topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
    rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
    bottomTitles: AxisTitles(
      sideTitles: SideTitles(
        showTitles: true,
        getTitlesWidget: bottomBuilder,
        reservedSize: 40,
      ),
    ),
    leftTitles: AxisTitles(
      sideTitles: SideTitles(
        showTitles: true,
        reservedSize: 56,
        getTitlesWidget: (value, meta) => Text(
          compactCurrency(value),
          style: const TextStyle(fontSize: 10),
        ),
      ),
    ),
  );
}

String compactCurrency(double value) {
  if (value >= 1000) {
    return '\$${(value / 1000).toStringAsFixed(1)}k';
  }
  return '\$${value.toStringAsFixed(0)}';
}

Color paletteColor(int index) {
  const colors = [
    Color(0xFF0B6E4F),
    Color(0xFF1768AC),
    Color(0xFFE67E22),
    Color(0xFF8E5A9B),
    Color(0xFFB56576),
    Color(0xFF2A9D8F),
    Color(0xFFF4A261),
  ];
  return colors[index % colors.length];
}

String formatCurrency(double value) {
  return NumberFormat.currency(symbol: '\$', decimalDigits: 2).format(value);
}

String describeDateRange(DateTimeRange range) {
  final formatter = DateFormat('dd MMM yyyy');
  return '${formatter.format(range.start)} - ${formatter.format(range.end)}';
}

DateTimeRange currentMonthRange() {
  final now = DateTime.now();
  return monthRangeFor(DateTime(now.year, now.month));
}

DateTimeRange currentWeekRange() {
  final now = DateTime.now();
  final start = DateTime(now.year, now.month, now.day)
      .subtract(Duration(days: now.weekday - 1));
  final end = start.add(const Duration(days: 6));
  return DateTimeRange(start: start, end: end);
}

DateTimeRange singleDayRange(DateTime date) {
  final start = DateTime(date.year, date.month, date.day);
  return DateTimeRange(start: start, end: start);
}

DateTimeRange monthRangeFor(DateTime month) {
  final start = DateTime(month.year, month.month, 1);
  final end = DateTime(month.year, month.month + 1, 0);
  return DateTimeRange(start: start, end: end);
}

DateTime startOfDay(DateTime date) {
  return DateTime(date.year, date.month, date.day);
}

DateTime endExclusive(DateTime date) {
  return DateTime(date.year, date.month, date.day + 1);
}

String titleCase(String input) {
  return input
      .trim()
      .split(RegExp(r'\s+'))
      .where((part) => part.isNotEmpty)
      .map(
        (part) => part.length == 1
            ? part.toUpperCase()
            : '${part[0].toUpperCase()}${part.substring(1)}',
      )
      .join(' ');
}
