import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/constants.dart';
import '../core/theme.dart';
import '../models/user_model.dart';
import '../providers/dashboard_provider.dart';
import '../repositories/auth_repository.dart';
import 'alerts_screen.dart';
import 'dashboard_screen.dart';
import 'history_screen.dart';
import 'parking_map_screen.dart';
import 'report_screen.dart';

class HomeScreen extends ConsumerStatefulWidget {
  final User user;

  const HomeScreen({super.key, required this.user});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen>
    with WidgetsBindingObserver {
  int _currentIndex = 0;
  Timer? _pollTimer;
  StreamSubscription<Map<String, dynamic>>? _wsSub;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _startLiveMonitoring();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pollTimer?.cancel();
    unawaited(_wsSub?.cancel());
    unawaited(ref.read(wsServiceProvider).disconnect(paused: true));
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _startLiveMonitoring();
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive) {
      _pollTimer?.cancel();
      unawaited(ref.read(wsServiceProvider).disconnect(paused: true));
    }
  }

  Future<void> _startLiveMonitoring() async {
    if (!mounted) return;
    await _refreshOperationalData();
    await _connectWebSocket();
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(AppConstants.restSnapshotInterval, (_) {
      unawaited(_refreshOperationalData(silent: true));
    });
  }

  Future<void> _connectWebSocket() async {
    final token = await ref.read(authRepositoryProvider).getToken();
    if (!mounted || token == null || token.isEmpty) return;
    final service = ref.read(wsServiceProvider);
    await service.connect(token);
    await _wsSub?.cancel();
    _wsSub = service.messages.listen((_) {
      unawaited(_refreshOperationalData(silent: true));
    });
  }

  Future<void> _refreshOperationalData({bool silent = false}) async {
    await Future.wait([
      ref.read(slotsProvider.notifier).fetch(silent: silent),
      ref.read(activeSessionsProvider.notifier).fetch(silent: silent),
      ref.read(alertsProvider.notifier).fetch(silent: silent),
      if (widget.user.isAdmin)
        ref.read(reportProvider.notifier).fetchAll(silent: silent),
    ]);
  }

  Future<void> _logout() async {
    _pollTimer?.cancel();
    await _wsSub?.cancel();
    await ref.read(wsServiceProvider).disconnect();
    await ref.read(authStateProvider.notifier).logout();
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      DashboardScreen(
        user: widget.user,
        onLogout: _logout,
        onRefreshAll: _refreshOperationalData,
      ),
      const ParkingMapScreen(),
      const HistoryScreen(),
      widget.user.isAdmin
          ? const ReportScreen(isAdmin: true)
          : const AlertsScreen(),
    ];

    return Scaffold(
      backgroundColor: AppTheme.navy,
      body: IndexedStack(index: _currentIndex, children: pages),
      bottomNavigationBar: DecoratedBox(
        decoration: const BoxDecoration(
          color: AppTheme.navy,
          border: Border(top: BorderSide(color: AppTheme.border)),
        ),
        child: SafeArea(
          top: false,
          child: BottomNavigationBar(
            currentIndex: _currentIndex,
            onTap: (index) => setState(() => _currentIndex = index),
            selectedFontSize: 12,
            unselectedFontSize: 11,
            items: [
              const BottomNavigationBarItem(
                icon: Icon(Icons.dashboard_outlined),
                activeIcon: Icon(Icons.dashboard),
                label: 'Tổng quan',
              ),
              const BottomNavigationBarItem(
                icon: Icon(Icons.local_parking_outlined),
                activeIcon: Icon(Icons.local_parking),
                label: 'Đang đỗ',
              ),
              const BottomNavigationBarItem(
                icon: Icon(Icons.history_outlined),
                activeIcon: Icon(Icons.history),
                label: 'Lịch sử',
              ),
              BottomNavigationBarItem(
                icon: Icon(
                  widget.user.isAdmin
                      ? Icons.bar_chart_outlined
                      : Icons.notifications_outlined,
                ),
                activeIcon: Icon(
                  widget.user.isAdmin ? Icons.bar_chart : Icons.notifications,
                ),
                label: widget.user.isAdmin ? 'Báo cáo' : 'Cảnh báo',
              ),
            ],
          ),
        ),
      ),
    );
  }
}
