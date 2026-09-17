import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme.dart';
import '../models/alert_model.dart';
import '../providers/dashboard_provider.dart';
import '../utils/helpers.dart';

class AlertsScreen extends ConsumerStatefulWidget {
  const AlertsScreen({super.key});

  @override
  ConsumerState<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends ConsumerState<AlertsScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(alertsProvider.notifier).fetch());
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(alertsProvider);
    return Scaffold(
      backgroundColor: AppTheme.navy,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => ref.read(alertsProvider.notifier).fetch(),
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              const SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.fromLTRB(20, 16, 20, 0),
                  child: _Title(),
                ),
              ),
              if (state.isLoading && state.alerts.isEmpty)
                const SliverFillRemaining(
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (state.error != null && state.alerts.isEmpty)
                SliverFillRemaining(
                  child: _ErrorPanel(
                    message: friendlyError(Exception(state.error!)),
                    onRetry: () => ref.read(alertsProvider.notifier).fetch(),
                  ),
                )
              else if (state.alerts.isEmpty)
                const SliverFillRemaining(
                  hasScrollBody: false,
                  child: _EmptyPanel(),
                )
              else
                SliverList.builder(
                  itemCount: state.alerts.length,
                  itemBuilder: (context, index) => Padding(
                    padding: const EdgeInsets.fromLTRB(20, 14, 20, 0),
                    child: _AlertCard(alert: state.alerts[index]),
                  ),
                ),
              const SliverToBoxAdapter(child: SizedBox(height: 24)),
            ],
          ),
        ),
      ),
    );
  }
}

class _Title extends StatelessWidget {
  const _Title();

  @override
  Widget build(BuildContext context) {
    return const Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.notifications, color: AppTheme.cyan, size: 24),
        SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Cảnh báo hệ thống',
                style: TextStyle(
                  color: AppTheme.textPrimary,
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                ),
              ),
              SizedBox(height: 3),
              Text(
                '50 cảnh báo mới nhất từ reporting service',
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 12),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _AlertCard extends StatelessWidget {
  final Alert alert;

  const _AlertCard({required this.alert});

  @override
  Widget build(BuildContext context) {
    final color = _levelColor(alert.level);
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(_levelIcon(alert.level), color: color, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  alert.message.isEmpty
                      ? 'Không có nội dung cảnh báo'
                      : alert.message,
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    fontWeight: FontWeight.w700,
                    height: 1.3,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  '${alert.source} • ${formatDateTime(alert.createdAt)}',
                  style: const TextStyle(
                    color: AppTheme.textSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyPanel extends StatelessWidget {
  const _EmptyPanel();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(30),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.task_alt, color: AppTheme.green, size: 46),
            SizedBox(height: 12),
            Text(
              'Chưa có cảnh báo',
              style: TextStyle(
                color: AppTheme.textPrimary,
                fontWeight: FontWeight.w800,
              ),
            ),
            SizedBox(height: 6),
            Text(
              'Reporting service chưa trả cảnh báo nào.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppTheme.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorPanel({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(30),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.cloud_off,
              color: AppTheme.textSecondary,
              size: 44,
            ),
            const SizedBox(height: 12),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Thử lại'),
            ),
          ],
        ),
      ),
    );
  }
}

Color _levelColor(String level) {
  final normalized = level.toUpperCase();
  if (normalized.contains('ERROR') || normalized.contains('CRITICAL')) {
    return AppTheme.red;
  }
  if (normalized.contains('WARN')) return AppTheme.yellow;
  return AppTheme.cyan;
}

IconData _levelIcon(String level) {
  final normalized = level.toUpperCase();
  if (normalized.contains('ERROR') || normalized.contains('CRITICAL')) {
    return Icons.error_outline;
  }
  if (normalized.contains('WARN')) return Icons.warning_amber_outlined;
  return Icons.info_outline;
}
