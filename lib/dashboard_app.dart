// ignore_for_file: unused_element, unused_element_parameter

import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:http/http.dart' as http;

import 'dashboard_http_client.dart';

// ============================================================================
// Design tokens — "Editorial Finance Terminal"
// Dark, refined, magazine-meets-private-banking. Pine-ink ground, warm cream
// foreground, electric lime signature accent. All surfaces use hairline 1px
// borders rather than shadows — depth comes from value contrast, not blur.
// ============================================================================

class Ink {
  static const ground = Color(0xFFF5F0E6);
  static const surface = Color(0xFFFFFCF6);
  static const surfaceHi = Color(0xFFF2EBDD);
  static const surfaceLo = Color(0xFFEEE4D3);
  static const hairline = Color(0xFFD8CBB8);
  static const hairlineHi = Color(0xFFB9AC98);
}

class Cream {
  static const primary = Color(0xFF1E2822);
  static const secondary = Color(0xFF566459);
  static const tertiary = Color(0xFF7D877D);
}

class Accent {
  static const lime = Color(0xFF1F6B4F);
  static const limeDeep = Color(0xFF174F3C);
  static const amber = Color(0xFFB67B2D);
  static const terracotta = Color(0xFFBA6147);
  static const mauve = Color(0xFF8B74B7);
  static const sky = Color(0xFF5E93B3);
  static const sage = Color(0xFF6F9A78);
  static const rose = Color(0xFFC57A88);
}

TextStyle display(double size, {FontWeight weight = FontWeight.w400, Color? color, double? letterSpacing, double? height}) {
  return GoogleFonts.fraunces(
    fontSize: size,
    fontWeight: weight,
    color: color ?? Cream.primary,
    height: height ?? 1.05,
    letterSpacing: letterSpacing ?? -0.5,
  );
}

TextStyle ui(double size, {FontWeight weight = FontWeight.w400, Color? color, double? letterSpacing, double? height}) {
  return GoogleFonts.sora(
    fontSize: size,
    fontWeight: weight,
    color: color ?? Cream.primary,
    height: height ?? 1.4,
    letterSpacing: letterSpacing ?? 0,
  );
}

TextStyle mono(double size, {FontWeight weight = FontWeight.w500, Color? color, double? letterSpacing}) {
  return GoogleFonts.jetBrainsMono(
    fontSize: size,
    fontWeight: weight,
    color: color ?? Cream.primary,
    letterSpacing: letterSpacing ?? 0,
    fontFeatures: const [FontFeature.tabularFigures()],
  );
}

TextStyle eyebrow({Color? color}) {
  return GoogleFonts.sora(
    fontSize: 11,
    fontWeight: FontWeight.w500,
    color: color ?? Cream.tertiary,
    letterSpacing: 1.6,
    height: 1.2,
  );
}

class ExpenseDashboardApp extends StatelessWidget {
  const ExpenseDashboardApp({super.key});

  @override
  Widget build(BuildContext context) {
    final colorScheme = const ColorScheme.light(
      brightness: Brightness.light,
      primary: Accent.lime,
      onPrimary: Ink.surface,
      secondary: Accent.amber,
      onSecondary: Ink.surface,
      surface: Ink.surface,
      onSurface: Cream.primary,
      surfaceContainerHighest: Ink.surfaceHi,
      outline: Ink.hairlineHi,
      outlineVariant: Ink.hairline,
      error: Accent.terracotta,
      onError: Ink.surface,
    );

    return MaterialApp(
      title: 'Expense Monitor',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: colorScheme,
        scaffoldBackgroundColor: Ink.ground,
        canvasColor: Ink.ground,
        useMaterial3: true,
        textTheme: TextTheme(
          displayLarge: display(72, weight: FontWeight.w300),
          displayMedium: display(56, weight: FontWeight.w300),
          displaySmall: display(44, weight: FontWeight.w400),
          headlineLarge: display(36, weight: FontWeight.w400),
          headlineMedium: display(28, weight: FontWeight.w500),
          headlineSmall: display(22, weight: FontWeight.w500),
          titleLarge: ui(18, weight: FontWeight.w600),
          titleMedium: ui(14, weight: FontWeight.w600),
          titleSmall: ui(12, weight: FontWeight.w600),
          bodyLarge: ui(15, color: Cream.primary),
          bodyMedium: ui(14, color: Cream.primary),
          bodySmall: ui(12, color: Cream.secondary),
          labelLarge: ui(13, weight: FontWeight.w500),
          labelMedium: ui(11, weight: FontWeight.w500, color: Cream.secondary),
          labelSmall: eyebrow(),
        ),
        cardTheme: const CardThemeData(
          elevation: 0,
          color: Ink.surface,
          surfaceTintColor: Colors.transparent,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.zero,
            side: BorderSide(color: Ink.hairline),
          ),
        ),
        appBarTheme: AppBarTheme(
          backgroundColor: Ink.ground,
          foregroundColor: Cream.primary,
          elevation: 0,
          scrolledUnderElevation: 0,
          surfaceTintColor: Colors.transparent,
          titleTextStyle: ui(15, weight: FontWeight.w500),
        ),
        dividerColor: Ink.hairline,
        dividerTheme: const DividerThemeData(
          color: Ink.hairline,
          thickness: 1,
          space: 1,
        ),
        iconTheme: const IconThemeData(color: Cream.secondary, size: 20),
        navigationRailTheme: NavigationRailThemeData(
          backgroundColor: Colors.transparent,
          indicatorColor: Accent.lime.withValues(alpha: 0.12),
          indicatorShape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(2)),
          ),
          selectedIconTheme: const IconThemeData(color: Accent.lime, size: 20),
          unselectedIconTheme: const IconThemeData(color: Cream.tertiary, size: 20),
          selectedLabelTextStyle: ui(13, weight: FontWeight.w500, color: Cream.primary),
          unselectedLabelTextStyle: ui(13, color: Cream.tertiary),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Ink.surfaceLo,
          contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
          labelStyle: ui(13, color: Cream.secondary),
          hintStyle: ui(13, color: Cream.tertiary),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(2),
            borderSide: const BorderSide(color: Ink.hairline),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(2),
            borderSide: const BorderSide(color: Ink.hairline),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(2),
            borderSide: const BorderSide(color: Accent.lime, width: 1.4),
          ),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            backgroundColor: Accent.lime,
            foregroundColor: Ink.surface,
            textStyle: ui(13, weight: FontWeight.w600, letterSpacing: 0.4),
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(2)),
          ),
        ),
        textButtonTheme: TextButtonThemeData(
          style: TextButton.styleFrom(
            foregroundColor: Cream.secondary,
            textStyle: ui(12, weight: FontWeight.w500, letterSpacing: 0.6),
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            foregroundColor: Cream.primary,
            side: const BorderSide(color: Ink.hairline),
            textStyle: ui(13, weight: FontWeight.w500),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(2)),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          ),
        ),
        snackBarTheme: SnackBarThemeData(
          backgroundColor: Ink.surfaceHi,
          contentTextStyle: ui(13, color: Cream.primary),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(2),
            side: const BorderSide(color: Ink.hairline),
          ),
        ),
        dialogTheme: DialogThemeData(
          backgroundColor: Ink.surface,
          surfaceTintColor: Colors.transparent,
          titleTextStyle: display(20, weight: FontWeight.w500),
          contentTextStyle: ui(13, color: Cream.secondary),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(2),
            side: const BorderSide(color: Ink.hairline),
          ),
        ),
        progressIndicatorTheme: const ProgressIndicatorThemeData(
          color: Accent.lime,
          linearTrackColor: Ink.hairline,
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
    if (_usernameController.text.trim().isEmpty) {
      setState(() => _error = 'Username field is empty.');
      return;
    }

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
    } catch (_) {
      setState(() => _error = 'Something went wrong. Please try again.');
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Ink.ground,
      body: Stack(
        children: [
          Positioned.fill(
            child: CustomPaint(painter: _LoginGridPainter()),
          ),
          Positioned(
            top: 32,
            left: 32,
            child: Row(
              children: [
                const _BrandMark(size: 28),
                const SizedBox(width: 12),
                Text(
                  'EXPENSE TERMINAL',
                  style: ui(11, weight: FontWeight.w600, color: Cream.secondary, letterSpacing: 2.4),
                ),
              ],
            ),
          ),
          Positioned(
            bottom: 28,
            left: 32,
            right: 32,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'V · 1.0',
                  style: mono(11, color: Cream.tertiary),
                ),
                Text(
                  'PRIVATE LEDGER · ENCRYPTED',
                  style: eyebrow(color: Cream.tertiary),
                ),
              ],
            ),
          ),
          Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(32),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: AutofillGroup(
                  child: Container(
                    padding: const EdgeInsets.all(36),
                    decoration: BoxDecoration(
                      color: Ink.surface,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: Ink.hairline),
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Row(
                          children: [
                            Text(
                              'SIGN IN',
                              style: eyebrow(color: Accent.lime),
                            ),
                            const Spacer(),
                            const _PulseDot(),
                          ],
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Welcome back.',
                          style: display(38, color: Cream.primary, height: 1.0),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Authenticate to access your private ledger.',
                          style: ui(13, color: Cream.secondary, height: 1.5),
                        ),
                        const SizedBox(height: 32),
                        _LoginField(
                          controller: _usernameController,
                          enabled: !_busy,
                          label: 'Username',
                          autofillHints: const [AutofillHints.username],
                          textInputAction: TextInputAction.next,
                        ),
                        const SizedBox(height: 14),
                        _LoginField(
                          controller: _passwordController,
                          enabled: !_busy,
                          label: 'Password',
                          obscureText: true,
                          autofillHints: const [AutofillHints.password],
                          onSubmitted: (_) => _busy ? null : _signIn(),
                        ),
                        AnimatedSwitcher(
                          duration: const Duration(milliseconds: 180),
                          child: _error == null
                              ? const SizedBox(height: 20)
                              : Padding(
                                  padding: const EdgeInsets.only(top: 14, bottom: 6),
                                  child: Row(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      const Icon(Icons.error_outline,
                                          size: 14, color: Accent.terracotta),
                                      const SizedBox(width: 8),
                                      Expanded(
                                        child: Text(
                                          _error!,
                                          style: ui(12, color: Accent.terracotta, height: 1.4),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                        ),
                        const SizedBox(height: 20),
                        FilledButton(
                          onPressed: _busy ? null : _signIn,
                          style: FilledButton.styleFrom(
                            backgroundColor: Accent.lime,
                            foregroundColor: Ink.surface,
                            disabledBackgroundColor: Ink.surfaceHi,
                            disabledForegroundColor: Cream.tertiary,
                            minimumSize: const Size.fromHeight(52),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                            textStyle: ui(13, weight: FontWeight.w700, letterSpacing: 1.2),
                          ),
                          child: _busy
                              ? const SizedBox(
                                  height: 18,
                                  width: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Ink.surface,
                                  ),
                                )
                              : const Text('SIGN IN'),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _LoginGridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Ink.hairline.withOpacity(0.35)
      ..strokeWidth = 1;
    const spacing = 56.0;
    for (double x = 0; x < size.width; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y < size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }

    final dotPaint = Paint()..color = Accent.lime.withOpacity(0.06);
    canvas.drawCircle(Offset(size.width * 0.85, size.height * 0.2), 240, dotPaint);
    canvas.drawCircle(Offset(size.width * 0.15, size.height * 0.85), 180, dotPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _LoginField extends StatelessWidget {
  const _LoginField({
    required this.controller,
    required this.enabled,
    required this.label,
    this.autofillHints,
    this.obscureText = false,
    this.onSubmitted,
    this.textInputAction,
  });

  final TextEditingController controller;
  final bool enabled;
  final String label;
  final Iterable<String>? autofillHints;
  final bool obscureText;
  final ValueChanged<String>? onSubmitted;
  final TextInputAction? textInputAction;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      enabled: enabled,
      obscureText: obscureText,
      autofillHints: autofillHints,
      onSubmitted: onSubmitted,
      textInputAction: textInputAction,
      style: ui(14, color: Cream.primary, letterSpacing: 0.2),
      cursorColor: Accent.lime,
      decoration: InputDecoration(
        labelText: label.toUpperCase(),
        labelStyle: eyebrow(color: Cream.tertiary),
        floatingLabelStyle: eyebrow(color: Accent.lime),
        filled: true,
        fillColor: Ink.surfaceLo,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Ink.hairline),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Ink.hairline),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Accent.lime, width: 1.4),
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

  static const _navItems = <_NavItem>[
    _NavItem('Analytics', 'Overview · trends · budgets', Icons.auto_graph_outlined, Icons.auto_graph),
    _NavItem('Ledger', 'Every transaction', Icons.receipt_long_outlined, Icons.receipt_long),
    _NavItem('Reports', 'Day · week · month', Icons.calendar_view_month_outlined, Icons.calendar_view_month),
    _NavItem('Categories', 'Taxonomy & order', Icons.bookmarks_outlined, Icons.bookmarks),
  ];

  @override
  Widget build(BuildContext context) {
    final pages = const [
      AnalyticsPage(),
      TransactionsPage(),
      ReportsPage(),
      CategoriesPage(),
    ];

    final media = MediaQuery.of(context);
    final isCompact = media.size.width < 880;

    return Scaffold(
      backgroundColor: Ink.ground,
      body: SafeArea(
        child: Row(
          children: [
            _Sidebar(
              items: _navItems,
              selected: _index,
              onSelect: (i) => setState(() => _index = i),
              compact: isCompact,
              session: widget.session,
              onSignOut: () async {
                await DashboardRepository.logout();
                widget.onSignedOut();
              },
            ),
            const VerticalDivider(width: 1),
            Expanded(
              child: Column(
                children: [
                  _TopBar(
                    eyebrow: 'Section',
                    title: _navItems[_index].label,
                    subtitle: _navItems[_index].sub,
                    sessionName: widget.session.username,
                  ),
                  const Divider(height: 1),
                  Expanded(
                    child: AnimatedSwitcher(
                      duration: const Duration(milliseconds: 320),
                      switchInCurve: Curves.easeOutCubic,
                      switchOutCurve: Curves.easeInCubic,
                      transitionBuilder: (child, animation) => FadeTransition(
                        opacity: animation,
                        child: SlideTransition(
                          position: Tween<Offset>(
                            begin: const Offset(0, 0.012),
                            end: Offset.zero,
                          ).animate(animation),
                          child: child,
                        ),
                      ),
                      child: KeyedSubtree(
                        key: ValueKey<int>(_index),
                        child: pages[_index],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavItem {
  const _NavItem(this.label, this.sub, this.icon, this.iconActive);
  final String label;
  final String sub;
  final IconData icon;
  final IconData iconActive;
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({
    required this.items,
    required this.selected,
    required this.onSelect,
    required this.compact,
    required this.session,
    required this.onSignOut,
  });

  final List<_NavItem> items;
  final int selected;
  final ValueChanged<int> onSelect;
  final bool compact;
  final DashboardSession session;
  final VoidCallback onSignOut;

  @override
  Widget build(BuildContext context) {
    final width = compact ? 76.0 : 244.0;
    return SizedBox(
      width: width,
      child: Container(
        color: Ink.surfaceLo,
        padding: EdgeInsets.symmetric(horizontal: compact ? 14 : 22, vertical: 22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Brand wordmark
            if (compact)
              const _BrandMark()
            else ...[
              const _BrandMark(),
              const SizedBox(height: 4),
              Text(
                'Expense Monitor',
                style: display(18, weight: FontWeight.w500, height: 1.0),
              ),
              const SizedBox(height: 2),
              Text(
                'a private ledger',
                style: ui(11, color: Cream.tertiary).copyWith(fontStyle: FontStyle.italic),
              ),
            ],
            const SizedBox(height: 32),
            if (!compact)
              Padding(
                padding: const EdgeInsets.only(left: 2, bottom: 14),
                child: Text('NAVIGATE', style: eyebrow()),
              ),
            // Nav items
            for (var i = 0; i < items.length; i++) ...[
              _NavTile(
                item: items[i],
                isSelected: i == selected,
                compact: compact,
                onTap: () => onSelect(i),
              ),
              const SizedBox(height: 4),
            ],
            const Spacer(),
            const Divider(),
            const SizedBox(height: 16),
            if (!compact) ...[
              Padding(
                padding: const EdgeInsets.only(left: 2, bottom: 8),
                child: Text('SESSION', style: eyebrow()),
              ),
              Row(
                children: [
                  Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: Accent.lime,
                      borderRadius: BorderRadius.circular(2),
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      session.username.isNotEmpty
                          ? session.username[0].toUpperCase()
                          : '?',
                      style: ui(13, weight: FontWeight.w700, color: Ink.surface),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      session.username,
                      overflow: TextOverflow.ellipsis,
                      style: ui(13, weight: FontWeight.w500),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
            ],
            InkWell(
              onTap: onSignOut,
              borderRadius: BorderRadius.circular(2),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
                child: Row(
                  mainAxisAlignment: compact ? MainAxisAlignment.center : MainAxisAlignment.start,
                  children: [
                    const Icon(Icons.logout, size: 16, color: Cream.tertiary),
                    if (!compact) ...[
                      const SizedBox(width: 12),
                      Text('Sign out', style: ui(12, color: Cream.secondary)),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavTile extends StatefulWidget {
  const _NavTile({
    required this.item,
    required this.isSelected,
    required this.compact,
    required this.onTap,
  });

  final _NavItem item;
  final bool isSelected;
  final bool compact;
  final VoidCallback onTap;

  @override
  State<_NavTile> createState() => _NavTileState();
}

class _NavTileState extends State<_NavTile> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final selected = widget.isSelected;
    final iconColor = selected
        ? Accent.lime
        : (_hover ? Cream.primary : Cream.tertiary);
    final labelColor = selected
        ? Cream.primary
        : (_hover ? Cream.primary : Cream.secondary);

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        behavior: HitTestBehavior.opaque,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: EdgeInsets.symmetric(
            horizontal: widget.compact ? 10 : 12,
            vertical: 12,
          ),
          decoration: BoxDecoration(
            border: Border(
              left: BorderSide(
                color: selected ? Accent.lime : Colors.transparent,
                width: 2,
              ),
            ),
            color: selected
                ? Accent.lime.withValues(alpha: 0.06)
                : (_hover ? Ink.surface : Colors.transparent),
          ),
          child: Row(
            mainAxisAlignment: widget.compact
                ? MainAxisAlignment.center
                : MainAxisAlignment.start,
            children: [
              Icon(
                selected ? widget.item.iconActive : widget.item.icon,
                color: iconColor,
                size: 18,
              ),
              if (!widget.compact) ...[
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.item.label,
                        style: ui(13, weight: FontWeight.w500, color: labelColor),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        widget.item.sub,
                        style: ui(10.5, color: Cream.tertiary, height: 1.1),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _BrandMark extends StatelessWidget {
  const _BrandMark({this.size = 32});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        border: Border.all(color: Accent.lime, width: 1.4),
      ),
      child: CustomPaint(painter: _BrandMarkPainter()),
    );
  }
}

class _BrandMarkPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Accent.lime
      ..strokeWidth = 1.4
      ..strokeCap = StrokeCap.square;
    // Two diagonals → a financial "X" mark
    canvas.drawLine(
      Offset(size.width * 0.22, size.height * 0.78),
      Offset(size.width * 0.78, size.height * 0.22),
      paint,
    );
    // tick at top-right
    canvas.drawLine(
      Offset(size.width * 0.55, size.height * 0.22),
      Offset(size.width * 0.78, size.height * 0.22),
      paint,
    );
    canvas.drawLine(
      Offset(size.width * 0.78, size.height * 0.22),
      Offset(size.width * 0.78, size.height * 0.45),
      paint,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _TopBar extends StatelessWidget {
  const _TopBar({
    required this.eyebrow,
    required this.title,
    required this.subtitle,
    required this.sessionName,
  });

  final String eyebrow;
  final String title;
  final String subtitle;
  final String sessionName;

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    return Container(
      padding: const EdgeInsets.fromLTRB(36, 22, 28, 22),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(eyebrow.toUpperCase(), style: eyebrow_()),
                const SizedBox(height: 8),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(
                      title,
                      style: display(34, weight: FontWeight.w400, height: 1.0),
                    ),
                    const SizedBox(width: 14),
                    Container(
                      width: 4,
                      height: 4,
                      decoration: const BoxDecoration(
                        color: Accent.lime,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Text(
                      subtitle,
                      style: ui(12, color: Cream.secondary, letterSpacing: 0.4),
                    ),
                  ],
                ),
              ],
            ),
          ),
          // Live clock / date strip
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  border: Border.all(color: Ink.hairline),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const _PulseDot(),
                    const SizedBox(width: 8),
                    Text('LIVE', style: eyebrow_(color: Cream.primary)),
                    const SizedBox(width: 10),
                    Container(width: 1, height: 12, color: Ink.hairline),
                    const SizedBox(width: 10),
                    Text(
                      DateFormat('EEE, dd MMM').format(now).toUpperCase(),
                      style: mono(11, color: Cream.secondary, letterSpacing: 1.2),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

TextStyle eyebrow_({Color? color}) => eyebrow(color: color);

class _PulseDot extends StatefulWidget {
  const _PulseDot();
  @override
  State<_PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<_PulseDot> with SingleTickerProviderStateMixin {
  late final AnimationController _c;
  @override
  void initState() {
    super.initState();
    _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))
      ..repeat(reverse: true);
  }
  @override
  void dispose() { _c.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) {
        final t = Curves.easeInOut.transform(_c.value);
        return Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(
            color: Color.lerp(Accent.lime, Accent.limeDeep, t),
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: Accent.lime.withValues(alpha: 0.35 * (1 - t)),
                blurRadius: 6 + 4 * t,
                spreadRadius: 1,
              ),
            ],
          ),
        );
      },
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
              padding: const EdgeInsets.fromLTRB(32, 12, 32, 32),
              child: _StaggeredColumn(
                spacing: 24,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: _MetricCard(
                          title: 'Visible transactions',
                          value: '${transactions.length}',
                          subtitle: describeDateRange(_range),
                          accent: Accent.lime,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: _MetricCard(
                          title: 'Visible spending',
                          value: formatCurrency(total),
                          subtitle: _category ?? 'All categories',
                          accent: Accent.amber,
                        ),
                      ),
                    ],
                  ),
                  _PanelCard(
                    eyebrow: 'FILTERS',
                    title: 'Refine the ledger',
                    child: Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        _PillButton(
                          icon: Icons.date_range,
                          label: describeDateRange(_range),
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
                        ),
                        _PillDropdown<String?>(
                          icon: Icons.category_outlined,
                          value: _category,
                          placeholder: 'All categories',
                          onChanged: (value) => setState(() => _category = value),
                          items: [
                            const _PillDropdownItem<String?>(
                              value: null,
                              label: 'All categories',
                            ),
                            ...categories.map(
                              (category) => _PillDropdownItem<String?>(
                                value: category.name,
                                label: '${category.emoji} ${category.name}',
                              ),
                            ),
                          ],
                        ),
                        SizedBox(
                          width: 260,
                          child: TextField(
                            controller: _searchController,
                            onChanged: (_) => setState(() {}),
                            style: ui(13, color: Cream.primary),
                            decoration: InputDecoration(
                              hintText: 'Search item',
                              hintStyle: ui(13, color: Cream.tertiary),
                              prefixIcon: Icon(Icons.search, size: 18, color: Cream.tertiary),
                              isDense: true,
                              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                            ),
                          ),
                        ),
                        TextButton.icon(
                          onPressed: () {
                            setState(() {
                              _range = currentMonthRange();
                              _category = null;
                              _searchController.clear();
                            });
                          },
                          icon: Icon(Icons.refresh, size: 16, color: Cream.tertiary),
                          label: Text(
                            'RESET',
                            style: eyebrow(color: Cream.tertiary),
                          ),
                        ),
                      ],
                    ),
                  ),
                  _PanelCard(
                    eyebrow: 'LEDGER',
                    title: '${transactions.length} entries',
                    child: transactions.isEmpty
                        ? Padding(
                            padding: const EdgeInsets.symmetric(vertical: 32),
                            child: Center(
                              child: Column(
                                children: [
                                  Icon(Icons.receipt_long_outlined, size: 36, color: Cream.tertiary.withOpacity(0.4)),
                                  const SizedBox(height: 12),
                                  Text(
                                    'NO TRANSACTIONS MATCH',
                                    style: eyebrow(color: Cream.tertiary),
                                  ),
                                ],
                              ),
                            ),
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
          padding: const EdgeInsets.fromLTRB(32, 12, 32, 32),
          child: _StaggeredColumn(
            spacing: 24,
            children: [
              Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  _ReportSummaryCard(
                    title: 'TODAY',
                    transactions: daily,
                    range: dayRange,
                  ),
                  _ReportSummaryCard(
                    title: 'THIS WEEK',
                    transactions: weekly,
                    range: weekRange,
                  ),
                  _ReportSummaryCard(
                    title: 'THIS MONTH',
                    transactions: monthly,
                    range: monthRange,
                  ),
                ],
              ),
              _PanelCard(
                eyebrow: 'HISTORICAL',
                title: 'Month report',
                trailing: Wrap(
                  spacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    _PillDropdown<DateTime>(
                      icon: Icons.calendar_view_month,
                      value: monthChoices.firstWhere(
                        (month) =>
                            month.year == _selectedMonth.year &&
                            month.month == _selectedMonth.month,
                      ),
                      onChanged: (value) => setState(() => _selectedMonth = value),
                      items: monthChoices
                          .map(
                            (month) => _PillDropdownItem<DateTime>(
                              value: month,
                              label: DateFormat('MMMM yyyy').format(month),
                            ),
                          )
                          .toList(),
                    ),
                    _PillButton(
                      icon: Icons.calendar_month,
                      label: 'Pick month',
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
                    ),
                  ],
                ),
                child: _HistoricalMonthPanel(range: selectedRange),
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
  AnalyticsRangePreset _rangePreset = AnalyticsRangePreset.currentMonth;
  DateTimeRange _range = currentMonthRange();
  Set<String> _selectedCategories = <String>{};
  Set<String> _knownCategories = <String>{};
  bool _categoriesInitialized = false;

  void _setRangePreset(AnalyticsRangePreset preset) {
    setState(() {
      _rangePreset = preset;
      if (preset != AnalyticsRangePreset.custom) {
        _range = analyticsRangeForPreset(preset, now: DateTime.now());
      }
    });
  }

  Future<void> _pickCustomRange(BuildContext context) async {
    final picked = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime.now().add(const Duration(days: 365)),
      initialDateRange: _range,
      builder: (context, child) => Theme(
        data: Theme.of(context).copyWith(
          colorScheme: const ColorScheme.light(
            primary: Accent.lime,
            onPrimary: Ink.surface,
            surface: Ink.surface,
            onSurface: Cream.primary,
          ),
        ),
        child: child ?? const SizedBox.shrink(),
      ),
    );
    if (picked == null) {
      return;
    }
    setState(() {
      _rangePreset = AnalyticsRangePreset.custom;
      _range = picked;
    });
  }

  Future<void> _handleRangePresetChange(
    BuildContext context,
    AnalyticsRangePreset preset,
  ) async {
    if (preset == AnalyticsRangePreset.custom) {
      await _pickCustomRange(context);
      return;
    }
    _setRangePreset(preset);
  }

  void _syncSelectedCategories(List<DashboardCategory> categories) {
    final currentNames = categories.map((category) => category.name).toSet();
    if (!_categoriesInitialized) {
      _selectedCategories = {...currentNames};
      _knownCategories = {...currentNames};
      _categoriesInitialized = true;
      return;
    }

    final hadAllSelected = _selectedCategories.length == _knownCategories.length &&
        _selectedCategories.containsAll(_knownCategories);
    _selectedCategories = _selectedCategories.where(currentNames.contains).toSet();
    if (hadAllSelected) {
      _selectedCategories = {...currentNames};
    } else if (_selectedCategories.isEmpty && currentNames.isNotEmpty) {
      _selectedCategories = {...currentNames};
    }
    _knownCategories = {...currentNames};
  }

  void _toggleCategorySelection(String categoryName) {
    setState(() {
      if (_selectedCategories.contains(categoryName)) {
        if (_selectedCategories.length == 1) {
          return;
        }
        _selectedCategories.remove(categoryName);
      } else {
        _selectedCategories.add(categoryName);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<List<DashboardCategory>>(
      stream: DashboardRepository.streamCategories(),
      builder: (context, categorySnapshot) {
        final categories = categorySnapshot.data ?? const <DashboardCategory>[];
        _syncSelectedCategories(categories);
        return StreamBuilder<List<DashboardTransaction>>(
          stream: DashboardRepository.streamTransactions(
            range: _range,
          ),
          builder: (context, transactionSnapshot) {
            if (transactionSnapshot.connectionState == ConnectionState.waiting) {
              return const LoadingBody();
            }

            final rangeTransactions =
                transactionSnapshot.data ?? const <DashboardTransaction>[];

            return StreamBuilder<Map<String, double>>(
              stream: DashboardRepository.streamBudgets(),
              builder: (context, budgetSnapshot) {
                final budgets = budgetSnapshot.data ?? const <String, double>{};
                final transactions = filterTransactionsBySelectedCategories(
                  rangeTransactions,
                  _selectedCategories,
                );
                final summaries = buildCategorySummaries(transactions, categories);
                final trend = buildTrendSeries(transactions);
                final topCategories = summaries.take(6).toList();
                final maxBarTotal = topCategories.isEmpty
                    ? 1.0
                    : topCategories
                        .map((summary) => summary.total)
                        .reduce(math.max);
                final total = transactions.fold<double>(0, (s, t) => s + t.amount);
                final avg = transactions.isEmpty ? 0.0 : total / transactions.length;
                final topCat = summaries.isNotEmpty ? summaries.first : null;
                final overBudget = countOverBudgetCategories(summaries, budgets);
                final hasBaseData = rangeTransactions.isNotEmpty;
                final emptyMessage = hasBaseData
                    ? 'No transactions match the current filters.'
                    : 'No transactions in this range yet.';

                return _StaggeredColumn(
                  padding: const EdgeInsets.fromLTRB(36, 8, 36, 32),
                  children: [
                    _FilterStrip(
                      rangePreset: _rangePreset,
                      range: _range,
                      categories: categories,
                      selectedCategories: _selectedCategories,
                      onRangePresetChange: (preset) =>
                          _handleRangePresetChange(context, preset),
                      onToggleCategory: _toggleCategorySelection,
                      onReset: () => setState(() {
                        _rangePreset = AnalyticsRangePreset.currentMonth;
                        _range = currentMonthRange();
                        _selectedCategories = {
                          for (final category in categories) category.name,
                        };
                      }),
                    ),
                    const SizedBox(height: 18),
                    _PanelCard(
                      eyebrow: 'TIMELINE',
                      title: 'Spending trend',
                      trailing: Text(
                        describeDateRange(_range),
                        style: ui(11, color: Cream.tertiary, letterSpacing: 0.4),
                      ),
                      child: trend.isEmpty
                          ? _EmptyChart(message: emptyMessage)
                          : SizedBox(
                              height: 380,
                              child: LineChart(
                                LineChartData(
                                  minY: 0,
                                  gridData: _gridData(),
                                  borderData: FlBorderData(show: false),
                                  titlesData: minimalChartTitles(
                                    bottomBuilder: (value, meta) {
                                      final index = value.toInt();
                                      if (index < 0 || index >= trend.length) {
                                        return const SizedBox.shrink();
                                      }
                                      if (trend.length > 12 && index.isOdd) {
                                        return const SizedBox.shrink();
                                      }
                                      return Padding(
                                        padding: const EdgeInsets.only(top: 8),
                                        child: Text(
                                          DateFormat('d MMM').format(trend[index].date),
                                          style: mono(
                                            10,
                                            color: Cream.tertiary,
                                            letterSpacing: 0.3,
                                          ),
                                        ),
                                      );
                                    },
                                  ),
                                  lineTouchData: LineTouchData(
                                    touchTooltipData: LineTouchTooltipData(
                                      getTooltipColor: (_) => Ink.surfaceHi,
                                      tooltipBorder: const BorderSide(color: Ink.hairline),
                                      getTooltipItems: (spots) => spots.map((spot) {
                                        final point = trend[spot.x.toInt()];
                                        return LineTooltipItem(
                                          '${formatCurrency(point.total)}\n',
                                          mono(
                                            13,
                                            color: Cream.primary,
                                            weight: FontWeight.w600,
                                          ),
                                          children: [
                                            TextSpan(
                                              text: DateFormat('EEE, d MMM').format(point.date),
                                              style: ui(10, color: Cream.tertiary),
                                            ),
                                          ],
                                        );
                                      }).toList(),
                                    ),
                                  ),
                                  lineBarsData: [
                                    LineChartBarData(
                                      isCurved: false,
                                      color: Accent.lime,
                                      barWidth: 2,
                                      spots: [
                                        for (var i = 0; i < trend.length; i++)
                                          FlSpot(i.toDouble(), trend[i].total),
                                      ],
                                      dotData: FlDotData(
                                        show: true,
                                        getDotPainter: (_, __, ___, ____) =>
                                            FlDotCirclePainter(
                                          radius: 3.2,
                                          color: Accent.lime,
                                          strokeWidth: 1.4,
                                          strokeColor: Ink.surface,
                                        ),
                                      ),
                                      belowBarData: BarAreaData(
                                        show: true,
                                        gradient: LinearGradient(
                                          begin: Alignment.topCenter,
                                          end: Alignment.bottomCenter,
                                          colors: [
                                            Accent.lime.withValues(alpha: 0.16),
                                            Accent.lime.withValues(alpha: 0.0),
                                          ],
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                    ),
                    const SizedBox(height: 18),
                    LayoutBuilder(builder: (ctx, c) {
                      final wide = c.maxWidth >= 920;
                      final children = <Widget>[
                        Expanded(
                          flex: 1,
                          child: _MetricCard(
                            title: 'Filtered spend',
                            value: formatCurrency(total),
                            subtitle: '${transactions.length} transactions',
                            accent: Accent.lime,
                          ),
                        ),
                        Expanded(
                          flex: 1,
                          child: _MetricCard(
                            title: 'Average ticket',
                            value: formatCurrency(avg),
                            subtitle: analyticsCategorySelectionLabel(
                              _selectedCategories,
                              categories,
                            ),
                            accent: Accent.amber,
                          ),
                        ),
                        Expanded(
                          flex: 1,
                          child: _MetricCard(
                            title: 'Over budget',
                            value: '$overBudget',
                            subtitle: budgets.isEmpty ? 'No budgets set' : '${budgets.length} budgets tracked',
                            accent: overBudget > 0 ? Accent.terracotta : Accent.sage,
                          ),
                        ),
                      ];
                      return wide
                          ? Row(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                children[0],
                                const SizedBox(width: 16),
                                children[1],
                                const SizedBox(width: 16),
                                children[2],
                              ],
                            )
                          : Column(
                              children: [
                                for (var i = 0; i < children.length; i++) ...[
                                  if (i > 0) const SizedBox(height: 16),
                                  Row(children: [Expanded(child: children[i])]),
                                ],
                              ],
                            );
                    }),
                    const SizedBox(height: 20),
                    LayoutBuilder(builder: (ctx, c) {
                      final wide = c.maxWidth >= 1100;
                      final breakdownCard = _PanelCard(
                        eyebrow: 'COMPOSITION',
                        title: 'Category breakdown',
                        trailing: Text(
                          '${summaries.length} active',
                          style: ui(11, color: Cream.tertiary, letterSpacing: 0.4),
                        ),
                        child: summaries.isEmpty
                            ? _EmptyChart(message: emptyMessage)
                            : Column(
                                children: [
                                  SizedBox(
                                    height: 200,
                                    child: PieChart(
                                      PieChartData(
                                        sectionsSpace: 2,
                                        centerSpaceRadius: 56,
                                        startDegreeOffset: -90,
                                        sections: [
                                          for (var i = 0; i < summaries.length; i++)
                                            PieChartSectionData(
                                              color: paletteColor(i),
                                              value: summaries[i].total,
                                              title: '',
                                              radius: 22,
                                              borderSide: const BorderSide(
                                                color: Ink.surface,
                                                width: 2,
                                              ),
                                            ),
                                        ],
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: 16),
                                  _CategoryLegend(summaries: summaries.take(5).toList()),
                                ],
                              ),
                      );
                      if (wide) {
                        return breakdownCard;
                      }
                      return breakdownCard;
                    }),
                    const SizedBox(height: 16),

                    // === CHARTS SECONDARY: 5/7 split (budget + bars) ===
                    LayoutBuilder(builder: (ctx, c) {
                      final wide = c.maxWidth >= 1100;
                      final budgetsCard = _PanelCard(
                        eyebrow: 'COMMITMENTS',
                        title: 'Budget progress',
                        trailing: budgets.isNotEmpty
                            ? Text(
                                '${budgets.length} active',
                                style: ui(11, color: Cream.tertiary, letterSpacing: 0.4),
                              )
                            : null,
                        child: budgets.isEmpty
                            ? const _EmptyChart(message: 'No budgets set yet.')
                            : transactions.isEmpty
                                ? _EmptyChart(message: emptyMessage)
                            : _BudgetProgressList(
                                budgets: budgets,
                                categoryTotals: {
                                  for (final s in summaries) s.name: s.total,
                                },
                              ),
                      );
                      final barsCard = _PanelCard(
                        eyebrow: 'RANK',
                        title: 'Top categories',
                        child: topCategories.isEmpty
                            ? _EmptyChart(message: emptyMessage)
                            : SizedBox(
                                height: 320,
                                child: BarChart(
                                  BarChartData(
                                    maxY: maxBarTotal * 1.18,
                                    gridData: _gridData(),
                                    borderData: FlBorderData(show: false),
                                    titlesData: minimalChartTitles(
                                      bottomBuilder: (value, meta) {
                                        final index = value.toInt();
                                        if (index < 0 || index >= topCategories.length) {
                                          return const SizedBox.shrink();
                                        }
                                        return Padding(
                                          padding: const EdgeInsets.only(top: 10),
                                          child: SizedBox(
                                            width: 60,
                                            child: Text(
                                              topCategories[index].label,
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                              textAlign: TextAlign.center,
                                              style: ui(10, color: Cream.tertiary),
                                            ),
                                          ),
                                        );
                                      },
                                    ),
                                    barTouchData: BarTouchData(
                                      touchTooltipData: BarTouchTooltipData(
                                        getTooltipColor: (_) => Ink.surfaceHi,
                                        tooltipBorder: const BorderSide(color: Ink.hairline),
                                        getTooltipItem: (g, i, rod, ri) => BarTooltipItem(
                                          '${topCategories[g.x].label}\n',
                                          ui(11, color: Cream.tertiary),
                                          children: [
                                            TextSpan(
                                              text: formatCurrency(rod.toY),
                                              style: mono(13, weight: FontWeight.w600),
                                            ),
                                          ],
                                        ),
                                      ),
                                    ),
                                    barGroups: [
                                      for (var i = 0; i < topCategories.length; i++)
                                        BarChartGroupData(
                                          x: i,
                                          barRods: [
                                            BarChartRodData(
                                              toY: topCategories[i].total,
                                              color: paletteColor(i),
                                              width: 18,
                                              borderRadius: BorderRadius.zero,
                                            ),
                                          ],
                                        ),
                                    ],
                                  ),
                                ),
                              ),
                      );
                      if (wide) {
                        return IntrinsicHeight(
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Expanded(flex: 7, child: barsCard),
                              const SizedBox(width: 16),
                              Expanded(flex: 5, child: budgetsCard),
                            ],
                          ),
                        );
                      }
                      return Column(
                        children: [
                          barsCard,
                          const SizedBox(height: 16),
                          budgetsCard,
                        ],
                      );
                    }),
                  ],
                );
              },
            );
          },
        );
      },
    );
  }
}

// ============================================================================
// Hero block — the dominant headline number for analytics landing
// ============================================================================
class _HeroBlock extends StatelessWidget {
  const _HeroBlock({
    required this.total,
    required this.transactionCount,
    required this.avg,
    required this.topCategory,
    required this.overBudget,
    required this.range,
    required this.trend,
  });

  final double total;
  final int transactionCount;
  final double avg;
  final CategorySummary? topCategory;
  final int overBudget;
  final DateTimeRange range;
  final List<TrendPoint> trend;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Ink.surface,
        border: Border.all(color: Ink.hairline),
      ),
      padding: const EdgeInsets.fromLTRB(24, 22, 24, 22),
      child: LayoutBuilder(builder: (ctx, c) {
        final wide = c.maxWidth >= 980;
        final left = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('TOTAL · ${describeDateRange(range).toUpperCase()}', style: eyebrow()),
                const SizedBox(width: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    border: Border.all(color: Ink.hairline),
                  ),
                  child: Text(
                    '$transactionCount TX',
                    style: mono(10, color: Cream.secondary, letterSpacing: 1.2),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            // The hero number — Fraunces, big, dominant
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text('\$', style: display(48, weight: FontWeight.w300, color: Cream.tertiary, height: 1.0)),
                const SizedBox(width: 6),
                Text(
                  NumberFormat('#,##0').format(total.truncate()),
                  style: display(86, weight: FontWeight.w300, height: 0.95, letterSpacing: -2),
                ),
                const SizedBox(width: 4),
                Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: Text(
                    '.${(total - total.truncate()).toStringAsFixed(2).substring(2)}',
                    style: display(36, weight: FontWeight.w300, color: Cream.tertiary, height: 1.0),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 28,
              runSpacing: 12,
              children: [
                _HeroStat(
                  label: 'AVG TICKET',
                  value: formatCurrency(avg),
                ),
                _HeroStat(
                  label: 'TOP CATEGORY',
                  value: topCategory?.label ?? '—',
                ),
                _HeroStat(
                  label: 'OVER BUDGET',
                  value: overBudget > 0 ? '$overBudget cat.' : 'on track',
                  highlight: overBudget > 0 ? Accent.terracotta : Accent.sage,
                ),
              ],
            ),
          ],
        );
        final right = SizedBox(
          height: 124,
          child: trend.isEmpty
              ? Center(
                  child: Text(
                    'awaiting data',
                    style: ui(12, color: Cream.tertiary).copyWith(fontStyle: FontStyle.italic),
                  ),
                )
              : LineChart(
                  LineChartData(
                    minY: 0,
                    gridData: const FlGridData(show: false),
                    titlesData: const FlTitlesData(show: false),
                    borderData: FlBorderData(show: false),
                    lineTouchData: const LineTouchData(enabled: false),
                    lineBarsData: [
                      LineChartBarData(
                        isCurved: true,
                        curveSmoothness: 0.32,
                        color: Accent.lime,
                        barWidth: 1.6,
                        spots: [
                          for (var i = 0; i < trend.length; i++)
                            FlSpot(i.toDouble(), trend[i].total),
                        ],
                        dotData: const FlDotData(show: false),
                        belowBarData: BarAreaData(
                          show: true,
                          gradient: LinearGradient(
                            begin: Alignment.topCenter,
                            end: Alignment.bottomCenter,
                            colors: [
                              Accent.lime.withValues(alpha: 0.22),
                              Accent.lime.withValues(alpha: 0.0),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
        );
        if (wide) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(flex: 7, child: left),
              const SizedBox(width: 24),
              Expanded(flex: 4, child: right),
            ],
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [left, const SizedBox(height: 18), right],
        );
      }),
    );
  }
}

class _HeroStat extends StatelessWidget {
  const _HeroStat({required this.label, required this.value, this.highlight});
  final String label;
  final String value;
  final Color? highlight;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(label, style: eyebrow()),
        const SizedBox(height: 6),
        Text(
          value,
          style: ui(15, weight: FontWeight.w500, color: highlight ?? Cream.primary),
        ),
      ],
    );
  }
}

class _CategoryLegend extends StatelessWidget {
  const _CategoryLegend({required this.summaries});
  final List<CategorySummary> summaries;

  @override
  Widget build(BuildContext context) {
    final total = summaries.fold<double>(0, (s, x) => s + x.total);
    return Column(
      children: [
        for (var i = 0; i < summaries.length; i++) ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 5),
            child: Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: paletteColor(i),
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    summaries[i].label,
                    overflow: TextOverflow.ellipsis,
                    style: ui(12, color: Cream.primary),
                  ),
                ),
                Text(
                  total > 0
                      ? '${(summaries[i].total / total * 100).toStringAsFixed(0)}%'
                      : '0%',
                  style: mono(11, color: Cream.secondary),
                ),
                const SizedBox(width: 12),
                SizedBox(
                  width: 70,
                  child: Text(
                    formatCurrency(summaries[i].total),
                    textAlign: TextAlign.end,
                    style: mono(11, weight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _FilterStrip extends StatelessWidget {
  const _FilterStrip({
    required this.rangePreset,
    required this.range,
    required this.categories,
    required this.selectedCategories,
    required this.onRangePresetChange,
    required this.onToggleCategory,
    required this.onReset,
  });

  final AnalyticsRangePreset rangePreset;
  final DateTimeRange range;
  final List<DashboardCategory> categories;
  final Set<String> selectedCategories;
  final ValueChanged<AnalyticsRangePreset> onRangePresetChange;
  final ValueChanged<String> onToggleCategory;
  final VoidCallback onReset;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
      decoration: BoxDecoration(
        color: Ink.surfaceLo,
        border: Border.all(color: Ink.hairline),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('FILTERS', style: eyebrow()),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  rangePreset == AnalyticsRangePreset.custom
                      ? 'Custom window active'
                      : '${analyticsRangePresetLabel(rangePreset)} selected',
                  style: ui(11, color: Cream.tertiary, letterSpacing: 0.3),
                ),
              ),
              TextButton.icon(
                onPressed: onReset,
                icon: const Icon(Icons.refresh, size: 14, color: Cream.tertiary),
                label: const Text('RESET'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              _CategoryMultiSelectButton(
                categories: categories,
                selectedCategories: selectedCategories,
                onToggleCategory: onToggleCategory,
              ),
              _PillDropdown<AnalyticsRangePreset>(
                value: rangePreset,
                icon: Icons.calendar_today_outlined,
                items: [
                  for (final preset in AnalyticsRangePreset.values)
                    _PillDropdownItem<AnalyticsRangePreset>(
                      value: preset,
                      label: analyticsRangePresetLabel(preset),
                    ),
                ],
                onChanged: onRangePresetChange,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _CategoryMultiSelectButton extends StatelessWidget {
  const _CategoryMultiSelectButton({
    required this.categories,
    required this.selectedCategories,
    required this.onToggleCategory,
  });

  final List<DashboardCategory> categories;
  final Set<String> selectedCategories;
  final ValueChanged<String> onToggleCategory;

  @override
  Widget build(BuildContext context) {
    return MenuAnchor(
      crossAxisUnconstrained: false,
      style: const MenuStyle(
        backgroundColor: WidgetStatePropertyAll(Ink.surfaceHi),
        side: WidgetStatePropertyAll(BorderSide(color: Ink.hairline)),
        padding: WidgetStatePropertyAll(EdgeInsets.zero),
      ),
      menuChildren: [
        SizedBox(
          width: 280,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 10),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('CATEGORY FILTER', style: eyebrow(color: Cream.tertiary)),
                const SizedBox(height: 4),
                Text(
                  '${selectedCategories.length}/${categories.length} selected',
                  style: ui(11, color: Cream.tertiary),
                ),
                const SizedBox(height: 12),
                for (var i = 0; i < categories.length; i++) ...[
                  if (i > 0) Container(height: 1, color: Ink.hairline),
                  InkWell(
                    onTap: () => onToggleCategory(categories[i].name),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      child: Row(
                        children: [
                          AnimatedContainer(
                            duration: const Duration(milliseconds: 160),
                            width: 18,
                            height: 18,
                            decoration: BoxDecoration(
                              color: selectedCategories.contains(categories[i].name)
                                  ? Accent.lime
                                  : Colors.transparent,
                              border: Border.all(
                                color: selectedCategories.contains(categories[i].name)
                                    ? Accent.lime
                                    : Cream.tertiary,
                              ),
                            ),
                            child: selectedCategories.contains(categories[i].name)
                                ? const Icon(Icons.check, size: 13, color: Ink.surface)
                                : null,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              '${categories[i].emoji} ${categories[i].name}',
                              style: ui(12, color: Cream.primary),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ],
      builder: (context, controller, child) {
        return _PillButton(
          icon: Icons.category_outlined,
          label:
              'Category · ${analyticsCategorySelectionLabel(selectedCategories, categories)}',
          onPressed: () {
            if (controller.isOpen) {
              controller.close();
            } else {
              controller.open();
            }
          },
        );
      },
    );
  }
}

class _PillButton extends StatefulWidget {
  const _PillButton({
    required this.icon,
    required this.label,
    this.onTap,
    this.onPressed,
  });
  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  final VoidCallback? onPressed;
  @override
  State<_PillButton> createState() => _PillButtonState();
}

class _PillButtonState extends State<_PillButton> {
  bool _hover = false;
  @override
  Widget build(BuildContext context) {
    final action = widget.onPressed ?? widget.onTap;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: action,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: _hover ? Ink.surfaceHi : Ink.surface,
            border: Border.all(color: _hover ? Ink.hairlineHi : Ink.hairline),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(widget.icon, size: 14, color: Cream.secondary),
              const SizedBox(width: 8),
              Text(widget.label, style: ui(12, color: Cream.primary)),
            ],
          ),
        ),
      ),
    );
  }
}

class _PillDropdownItem<T> {
  const _PillDropdownItem({required this.value, required this.label});
  final T value;
  final String label;
}

class _PillDropdown<T> extends StatelessWidget {
  const _PillDropdown({
    required this.value,
    required this.items,
    required this.onChanged,
    this.placeholder = '',
    this.icon,
  });

  final T value;
  final String placeholder;
  final IconData? icon;
  final List<_PillDropdownItem<T>> items;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) {
    final selected = items.firstWhere(
      (i) => i.value == value,
      orElse: () => _PillDropdownItem<T>(value: value, label: placeholder),
    );
    return Theme(
      data: Theme.of(context).copyWith(
        canvasColor: Ink.surfaceHi,
        popupMenuTheme: PopupMenuThemeData(
          color: Ink.surfaceHi,
          shape: RoundedRectangleBorder(
            side: const BorderSide(color: Ink.hairline),
            borderRadius: BorderRadius.circular(2),
          ),
        ),
      ),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        decoration: BoxDecoration(
          color: Ink.surface,
          border: Border.all(color: Ink.hairline),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, size: 14, color: Cream.secondary),
              const SizedBox(width: 8),
            ],
            DropdownButtonHideUnderline(
              child: DropdownButton<T>(
                value: value,
                hint: Text(placeholder, style: ui(12, color: Cream.secondary)),
                icon: const Icon(Icons.expand_more, size: 16, color: Cream.tertiary),
                style: ui(12, color: Cream.primary),
                dropdownColor: Ink.surfaceHi,
                isDense: true,
                items: items
                    .map((i) => DropdownMenuItem<T>(
                          value: i.value,
                          child: Text(i.label, style: ui(12, color: Cream.primary)),
                        ))
                    .toList(),
                onChanged: (v) {
                  if (v != null || null is T) onChanged(v as T);
                },
                selectedItemBuilder: (_) => items
                    .map((i) => Align(
                          alignment: Alignment.centerLeft,
                          child: Text(
                            i.value == selected.value ? selected.label : i.label,
                            style: ui(12, color: Cream.primary),
                          ),
                        ))
                    .toList(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PanelCard extends StatelessWidget {
  const _PanelCard({
    required this.eyebrow,
    required this.title,
    required this.child,
    this.trailing,
  });

  final String eyebrow;
  final String title;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Ink.surface,
        border: Border.all(color: Ink.hairline),
      ),
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(eyebrow, style: eyebrow_()),
                    const SizedBox(height: 6),
                    Text(title, style: display(20, weight: FontWeight.w500)),
                  ],
                ),
              ),
              if (trailing != null) trailing!,
            ],
          ),
          const SizedBox(height: 18),
          Container(height: 1, color: Ink.hairline),
          const SizedBox(height: 18),
          child,
        ],
      ),
    );
  }
}

FlGridData _gridData() => FlGridData(
      show: true,
      drawVerticalLine: false,
      horizontalInterval: null,
      getDrawingHorizontalLine: (_) => const FlLine(
        color: Ink.hairline,
        strokeWidth: 1,
        dashArray: [3, 3],
      ),
    );

// Staggered fade-in column for page-load delight
class _StaggeredColumn extends StatefulWidget {
  const _StaggeredColumn({
    required this.children,
    this.padding,
    this.spacing = 0,
  });
  final List<Widget> children;
  final EdgeInsets? padding;
  final double spacing;

  @override
  State<_StaggeredColumn> createState() => _StaggeredColumnState();
}

class _StaggeredColumnState extends State<_StaggeredColumn>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(
      vsync: this,
      duration: Duration(milliseconds: 400 + 80 * widget.children.length),
    )..forward();
  }

  @override
  void dispose() { _c.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final column = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var i = 0; i < widget.children.length; i++) ...[
          if (i > 0 && widget.spacing > 0) SizedBox(height: widget.spacing),
          AnimatedBuilder(
            animation: _c,
            builder: (_, __) {
              final start = (i * 0.08).clamp(0.0, 0.9);
              final end = (start + 0.5).clamp(0.0, 1.0);
              final t = CurvedAnimation(
                parent: _c,
                curve: Interval(start, end, curve: Curves.easeOutCubic),
              ).value;
              return Opacity(
                opacity: t,
                child: Transform.translate(
                  offset: Offset(0, (1 - t) * 12),
                  child: widget.children[i],
                ),
              );
            },
          ),
        ],
      ],
    );
    if (widget.padding != null) {
      return SingleChildScrollView(padding: widget.padding, child: column);
    }
    return column;
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
          padding: const EdgeInsets.fromLTRB(32, 12, 32, 32),
          child: _StaggeredColumn(
            spacing: 24,
            children: [
              _PanelCard(
                eyebrow: 'TAXONOMY',
                title: '${categories.length} categories',
                trailing: _PillButton(
                  icon: Icons.add,
                  label: 'Add category',
                  onPressed: () => showCategoryDialog(context, categories: categories),
                ),
                child: Column(
                  children: [
                    for (var i = 0; i < categories.length; i++) ...[
                      if (i > 0) Container(height: 1, color: Ink.hairline),
                      _CategoryRow(
                        category: categories[i],
                        categories: categories,
                      ),
                    ],
                  ],
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
    final headerStyle = eyebrow(color: Cream.tertiary);
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 0, 4, 12),
          child: Row(
            children: [
              SizedBox(width: 130, child: Text('DATE', style: headerStyle)),
              Expanded(child: Text('ITEM', style: headerStyle)),
              SizedBox(width: 160, child: Text('CATEGORY', style: headerStyle)),
              SizedBox(
                width: 130,
                child: Align(
                  alignment: Alignment.centerRight,
                  child: Text('AMOUNT', style: headerStyle),
                ),
              ),
              const SizedBox(width: 56),
            ],
          ),
        ),
        Container(height: 1, color: Ink.hairline),
        for (final transaction in transactions)
          _TransactionRow(transaction: transaction, categories: categories),
      ],
    );
  }
}

class _TransactionRow extends StatefulWidget {
  const _TransactionRow({
    required this.transaction,
    required this.categories,
  });

  final DashboardTransaction transaction;
  final List<DashboardCategory> categories;

  @override
  State<_TransactionRow> createState() => _TransactionRowState();
}

class _TransactionRowState extends State<_TransactionRow> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final tx = widget.transaction;
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: Container(
        decoration: BoxDecoration(
          color: _hover ? Ink.surfaceHi : Colors.transparent,
          border: const Border(
            bottom: BorderSide(color: Ink.hairline, width: 1),
          ),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 14),
        child: Row(
          children: [
            SizedBox(
              width: 130,
              child: Text(
                DateFormat('dd MMM yyyy').format(tx.timestamp),
                style: mono(12, color: Cream.secondary),
              ),
            ),
            Expanded(
              child: Text(
                tx.item,
                style: ui(13, weight: FontWeight.w500, color: Cream.primary, letterSpacing: 0.1),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            SizedBox(
              width: 160,
              child: _CategoryChip(name: tx.category),
            ),
            SizedBox(
              width: 130,
              child: Align(
                alignment: Alignment.centerRight,
                child: Text(
                  formatCurrency(tx.amount),
                  style: mono(14, weight: FontWeight.w500, color: Cream.primary),
                ),
              ),
            ),
            const SizedBox(width: 8),
            _IconAction(
              icon: Icons.edit_outlined,
              tooltip: 'Edit',
              onPressed: () => showTransactionEditor(
                context,
                transaction: tx,
                categories: widget.categories,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CategoryChip extends StatelessWidget {
  const _CategoryChip({required this.name});

  final String name;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: Ink.surfaceLo,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Ink.hairline),
      ),
      child: Text(
        name,
        style: ui(11, weight: FontWeight.w500, color: Cream.secondary, letterSpacing: 0.3),
        overflow: TextOverflow.ellipsis,
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
    return Container(
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Ink.hairline)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 14),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  transaction.item,
                  style: ui(14, weight: FontWeight.w500, color: Cream.primary, letterSpacing: 0.1),
                ),
                const SizedBox(height: 4),
                Text(
                  '${transaction.category.toUpperCase()} · ${DateFormat('dd MMM yyyy').format(transaction.timestamp)}',
                  style: eyebrow(color: Cream.tertiary),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Text(
            formatCurrency(transaction.amount),
            style: mono(15, weight: FontWeight.w500, color: Cream.primary),
          ),
          const SizedBox(width: 4),
          _IconAction(
            icon: Icons.edit_outlined,
            tooltip: 'Edit',
            onPressed: () => showTransactionEditor(
              context,
              transaction: transaction,
              categories: categories,
            ),
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
      width: 340,
      child: _PanelCard(
        eyebrow: title,
        title: describeDateRange(range),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              formatCurrency(total),
              style: display(40, weight: FontWeight.w400, color: Cream.primary, height: 1.0),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Container(
                  width: 6,
                  height: 6,
                  decoration: const BoxDecoration(
                    color: Accent.lime,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '${transactions.length} TRANSACTIONS',
                  style: eyebrow(color: Cream.tertiary),
                ),
              ],
            ),
          ],
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

        final total = transactions.fold<double>(0, (sum, tx) => sum + tx.amount);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              DateFormat('MMMM yyyy').format(range.start).toUpperCase(),
              style: eyebrow(color: Cream.tertiary),
            ),
            const SizedBox(height: 8),
            Text(
              formatCurrency(total),
              style: display(56, color: Cream.primary, height: 1.0),
            ),
            const SizedBox(height: 10),
            Text(
              '${transactions.length} TRANSACTIONS',
              style: eyebrow(color: Cream.tertiary),
            ),
            const SizedBox(height: 20),
            Container(height: 1, color: Ink.hairline),
            const SizedBox(height: 20),
            if (sortedEntries.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Text(
                  'NO SPENDING RECORDED',
                  style: eyebrow(color: Cream.tertiary),
                ),
              )
            else
              ...sortedEntries.map(
                (entry) {
                  final pct = total <= 0 ? 0.0 : (entry.value / total).clamp(0.0, 1.0);
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                entry.key,
                                style: ui(13, weight: FontWeight.w500, color: Cream.primary, letterSpacing: 0.2),
                              ),
                            ),
                            Text(
                              formatCurrency(entry.value),
                              style: mono(13, color: Cream.primary),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(2),
                          child: LinearProgressIndicator(
                            value: pct,
                            minHeight: 3,
                            color: Accent.lime,
                            backgroundColor: Ink.surfaceHi,
                          ),
                        ),
                      ],
                    ),
                  );
                },
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
    return _PanelCard(
      eyebrow: 'CHART',
      title: title,
      child: child,
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
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.show_chart, size: 32, color: Cream.tertiary.withOpacity(0.4)),
            const SizedBox(height: 12),
            Text(
              message.toUpperCase(),
              style: eyebrow(color: Cream.tertiary),
            ),
          ],
        ),
      ),
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

    if (rows.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 18),
        child: Text(
          'NO BUDGETS SET',
          style: eyebrow(color: Cream.tertiary),
        ),
      );
    }

    return Column(
      children: [
        for (var i = 0; i < rows.length; i++) ...[
          if (i > 0)
            Container(
              height: 1,
              color: Ink.hairline,
              margin: const EdgeInsets.symmetric(vertical: 14),
            ),
          _BudgetRow(
            name: rows[i].key,
            limit: rows[i].value,
            spent: categoryTotals[rows[i].key] ?? 0,
          ),
        ],
      ],
    );
  }
}

class _BudgetRow extends StatelessWidget {
  const _BudgetRow({
    required this.name,
    required this.spent,
    required this.limit,
  });

  final String name;
  final double spent;
  final double limit;

  @override
  Widget build(BuildContext context) {
    final clampedLimit = limit <= 0 ? 1.0 : limit;
    final progress = (spent / clampedLimit).clamp(0, 1).toDouble();
    final over = spent > limit;
    final accent = over ? Accent.terracotta : Accent.lime;
    final pct = (spent / clampedLimit * 100).clamp(0, 999).toStringAsFixed(0);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                name,
                style: ui(13, weight: FontWeight.w500, color: Cream.primary, letterSpacing: 0.2),
              ),
            ),
            Text(
              '$pct%',
              style: mono(11, color: accent),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(2),
          child: LinearProgressIndicator(
            value: progress,
            minHeight: 4,
            color: accent,
            backgroundColor: Ink.surfaceHi,
          ),
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            Text(
              formatCurrency(spent),
              style: mono(11, color: Cream.secondary),
            ),
            Text(
              ' / ${formatCurrency(limit)}',
              style: mono(11, color: Cream.tertiary),
            ),
          ],
        ),
      ],
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

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 14),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: Ink.surfaceHi,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Ink.hairline),
            ),
            alignment: Alignment.center,
            child: Text(category.emoji, style: const TextStyle(fontSize: 20)),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  category.name,
                  style: ui(14, weight: FontWeight.w500, color: Cream.primary, letterSpacing: 0.2),
                ),
                const SizedBox(height: 4),
                Text(
                  'ORDER · ${category.order.toString().padLeft(2, '0')}',
                  style: eyebrow(color: Cream.tertiary),
                ),
              ],
            ),
          ),
          _IconAction(
            icon: Icons.arrow_upward,
            tooltip: 'Move up',
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
          ),
          _IconAction(
            icon: Icons.arrow_downward,
            tooltip: 'Move down',
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
          ),
          _IconAction(
            icon: Icons.edit_outlined,
            tooltip: 'Edit',
            onPressed: () => showCategoryDialog(
              context,
              categories: categories,
              original: category,
            ),
          ),
          _IconAction(
            icon: Icons.delete_outline,
            tooltip: 'Delete',
            danger: true,
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
          ),
        ],
      ),
    );
  }
}

class _IconAction extends StatefulWidget {
  const _IconAction({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    this.danger = false,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback? onPressed;
  final bool danger;

  @override
  State<_IconAction> createState() => _IconActionState();
}

class _IconActionState extends State<_IconAction> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null;
    final base = enabled ? Cream.secondary : Cream.tertiary.withOpacity(0.4);
    final hover = widget.danger ? Accent.terracotta : Accent.lime;
    return Tooltip(
      message: widget.tooltip,
      child: MouseRegion(
        onEnter: (_) => setState(() => _hover = true),
        onExit: (_) => setState(() => _hover = false),
        child: GestureDetector(
          onTap: widget.onPressed,
          child: Container(
            width: 36,
            height: 36,
            margin: const EdgeInsets.symmetric(horizontal: 2),
            decoration: BoxDecoration(
              color: _hover && enabled ? Ink.surfaceHi : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
            ),
            alignment: Alignment.center,
            child: Icon(
              widget.icon,
              size: 18,
              color: _hover && enabled ? hover : base,
            ),
          ),
        ),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.title,
    required this.value,
    required this.subtitle,
    this.accent = Accent.lime,
  });

  final String title;
  final String value;
  final String subtitle;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Ink.surface,
        border: Border(
          top: BorderSide(color: accent, width: 2),
          left: const BorderSide(color: Ink.hairline),
          right: const BorderSide(color: Ink.hairline),
          bottom: const BorderSide(color: Ink.hairline),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(22, 20, 22, 22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(title.toUpperCase(), style: eyebrow()),
          const SizedBox(height: 18),
          Text(
            value,
            style: display(34, weight: FontWeight.w400, height: 1.0, letterSpacing: -1),
          ),
          const SizedBox(height: 10),
          Text(subtitle, style: ui(11, color: Cream.tertiary, letterSpacing: 0.3)),
        ],
      ),
    );
  }
}

enum _LandingTone { neutral, warning, error }

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
              'Sign in',
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              'Use your dashboard username and password.',
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
                label: Text(busy ? 'Signing in...' : 'Sign in'),
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

  factory DashboardCategory.fromDocument(dynamic document) {
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

/*
class LegacyDashboardRepository {
  static final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  static final http.Client _client = createDashboardHttpClient();
  static final StreamController<int> _refreshController =
      StreamController<int>.broadcast();
  static int _refreshTick = 0;
  static const String _prodApiBaseUrl =
      'https://finance-bot-jrpmzkxwoa-eu.a.run.app';
  static const String _devApiBaseUrl =
      'https://finance-bot-dev-jrpmzkxwoa-eu.a.run.app';
  static const String _configuredApiBaseUrl =
      String.fromEnvironment('DASHBOARD_API_BASE_URL');

  static String get _apiBaseUrl {
    if (_configuredApiBaseUrl.isNotEmpty) {
      return _configuredApiBaseUrl.replaceAll(RegExp(r'/$'), '');
    }

    final host = Uri.base.host.toLowerCase();
    if (host == 'budget-bot-123-dev.web.app' ||
        host == 'budget-bot-123-dev.firebaseapp.com') {
      return _devApiBaseUrl;
    }
    return _prodApiBaseUrl;
  }

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
*/

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
  static const String _prodApiBaseUrl =
      'https://finance-bot-jrpmzkxwoa-eu.a.run.app';
  static const String _devApiBaseUrl =
      'https://finance-bot-dev-jrpmzkxwoa-eu.a.run.app';
  static const String _configuredApiBaseUrl =
      String.fromEnvironment('DASHBOARD_API_BASE_URL');

  static String get _apiBaseUrl {
    if (_configuredApiBaseUrl.isNotEmpty) {
      return _configuredApiBaseUrl.replaceAll(RegExp(r'/$'), '');
    }

    final host = Uri.base.host.toLowerCase();
    if (host == 'budget-bot-123-dev.web.app' ||
        host == 'budget-bot-123-dev.firebaseapp.com') {
      return _devApiBaseUrl;
    }
    return _prodApiBaseUrl;
  }

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
                    initialValue: categories.any((entry) => entry.name == category)
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
                        } catch (_) {
                          setState(() => errorText = 'Something went wrong. Please try again.');
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
                      } catch (_) {
                        setState(() => errorText = 'Something went wrong. Please try again.');
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
  } catch (_) {
    if (!context.mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Something went wrong. Please try again.')),
    );
  }
}

enum AnalyticsRangePreset {
  currentMonth,
  last30Days,
  last90Days,
  yearToDate,
  custom,
}

String analyticsRangePresetLabel(AnalyticsRangePreset preset) {
  switch (preset) {
    case AnalyticsRangePreset.currentMonth:
      return 'Current month';
    case AnalyticsRangePreset.last30Days:
      return 'Last 30 days';
    case AnalyticsRangePreset.last90Days:
      return 'Last 90 days';
    case AnalyticsRangePreset.yearToDate:
      return 'Year to date';
    case AnalyticsRangePreset.custom:
      return 'Custom';
  }
}

DateTimeRange analyticsRangeForPreset(
  AnalyticsRangePreset preset, {
  DateTime? now,
}) {
  final reference = now ?? DateTime.now();
  final today = DateTime(reference.year, reference.month, reference.day);
  switch (preset) {
    case AnalyticsRangePreset.currentMonth:
      return monthRangeFor(reference);
    case AnalyticsRangePreset.last30Days:
      return DateTimeRange(
        start: today.subtract(const Duration(days: 29)),
        end: today,
      );
    case AnalyticsRangePreset.last90Days:
      return DateTimeRange(
        start: today.subtract(const Duration(days: 89)),
        end: today,
      );
    case AnalyticsRangePreset.yearToDate:
      return DateTimeRange(
        start: DateTime(reference.year, 1, 1),
        end: today,
      );
    case AnalyticsRangePreset.custom:
      return currentMonthRange();
  }
}

String analyticsCategorySelectionLabel(
  Set<String> selectedCategories,
  List<DashboardCategory> categories,
) {
  if (categories.isEmpty) {
    return 'All categories';
  }

  final orderedNames = categories.map((category) => category.name).toList();
  if (selectedCategories.length >= orderedNames.length &&
      selectedCategories.containsAll(orderedNames)) {
    return 'All categories';
  }

  if (selectedCategories.length == 1) {
    final only = selectedCategories.first;
    DashboardCategory? match;
    for (final category in categories) {
      if (category.name == only) {
        match = category;
        break;
      }
    }
    return match == null ? only : '${match.emoji} ${match.name}';
  }

  return '${selectedCategories.length} categories';
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

List<DashboardTransaction> filterTransactionsBySelectedCategories(
  List<DashboardTransaction> transactions,
  Set<String> selectedCategories,
) {
  if (selectedCategories.isEmpty) {
    return transactions;
  }

  return transactions
      .where((transaction) => selectedCategories.contains(transaction.category))
      .toList();
}

List<DashboardTransaction> applyAnalyticsFilters(
  List<DashboardTransaction> transactions, {
  required Map<String, double> budgets,
  required bool budgetedOnly,
  required bool overBudgetOnly,
}) {
  if (!budgetedOnly && !overBudgetOnly) {
    return transactions;
  }

  final categoryTotals = <String, double>{};
  for (final transaction in transactions) {
    categoryTotals.update(
      transaction.category,
      (value) => value + transaction.amount,
      ifAbsent: () => transaction.amount,
    );
  }

  return transactions.where((transaction) {
    final budget = budgets[transaction.category];
    final hasBudget = budget != null && budget > 0;
    if (budgetedOnly && !hasBudget) {
      return false;
    }
    if (overBudgetOnly) {
      if (!hasBudget) {
        return false;
      }
      final total = categoryTotals[transaction.category] ?? 0;
      if (total <= budget) {
        return false;
      }
    }
    return true;
  }).toList();
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

int countOverBudgetCategories(
  List<CategorySummary> summaries,
  Map<String, double> budgets,
) {
  return summaries.where((summary) {
    final budget = budgets[summary.name];
    return budget != null && budget > 0 && summary.total > budget;
  }).length;
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
        getTitlesWidget: (value, meta) => Padding(
          padding: const EdgeInsets.only(right: 8),
          child: Text(
            compactCurrency(value),
            style: mono(10, color: Cream.tertiary),
          ),
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
    Accent.lime,
    Accent.amber,
    Accent.sky,
    Accent.mauve,
    Accent.terracotta,
    Accent.sage,
    Accent.rose,
    Accent.limeDeep,
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
