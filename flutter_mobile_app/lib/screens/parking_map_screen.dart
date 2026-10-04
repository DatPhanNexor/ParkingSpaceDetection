import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme.dart';
import '../models/session_model.dart';
import '../providers/dashboard_provider.dart';
import '../utils/helpers.dart';
import '../repositories/auth_repository.dart';
import '../widgets/slot_grid.dart';

class ParkingMapScreen extends ConsumerWidget {
  const ParkingMapScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authStateProvider).value;
    final isAdmin = user?.isAdmin == true;

    final sessions = ref.watch(filteredActiveSessionsProvider);
    final slots = ref.watch(slotsProvider);
    return Scaffold(
      backgroundColor: AppTheme.navy,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            await ref.read(slotsProvider.notifier).fetch();
            await ref.read(activeSessionsProvider.notifier).fetch();
          },
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              const SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.fromLTRB(20, 16, 20, 0),
                  child: _ScreenTitle(
                    icon: Icons.local_parking,
                    title: 'Đang đỗ',
                    subtitle: 'Phiên đỗ đang hoạt động từ reporting service',
                  ),
                ),
              ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 18, 20, 16),
                  child: SlotGrid(slots: slots.slots, stale: slots.isStale),
                ),
              ),
              if (sessions.isLoading && sessions.sessions.isEmpty)
                const SliverFillRemaining(
                  hasScrollBody: false,
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (sessions.error != null && sessions.sessions.isEmpty)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: _ErrorPanel(
                    message: friendlyError(Exception(sessions.error!)),
                    onRetry: () =>
                        ref.read(activeSessionsProvider.notifier).fetch(),
                  ),
                )
              else if (sessions.sessions.isEmpty)
                const SliverFillRemaining(
                  hasScrollBody: false,
                  child: _EmptyPanel(),
                )
              else
                SliverList.builder(
                  itemCount: sessions.sessions.length,
                  itemBuilder: (context, index) {
                    final session = sessions.sessions[index];
                    final card = Padding(
                      padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                      child: _SessionCard(session: session),
                    );
                    if (isAdmin) {
                      return Dismissible(
                        key: Key(session.id),
                        direction: DismissDirection.endToStart,
                        background: Container(
                          margin: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                          alignment: Alignment.centerRight,
                          padding: const EdgeInsets.only(right: 20),
                          decoration: BoxDecoration(
                            color: AppTheme.red,
                            borderRadius: BorderRadius.circular(
                              AppTheme.radiusMd,
                            ),
                          ),
                          child: const Icon(
                            Icons.delete_outline,
                            color: Colors.white,
                          ),
                        ),
                        confirmDismiss: (direction) async {
                          return await showDialog<bool>(
                            context: context,
                            builder: (ctx) => AlertDialog(
                              title: const Text('Xóa phiên đang đỗ?'),
                              content: const Text(
                                'Bạn có chắc muốn xóa phiên này? Lịch sử đã hoàn tất không bị ảnh hưởng.',
                              ),
                              actions: [
                                TextButton(
                                  onPressed: () => Navigator.pop(ctx, false),
                                  child: const Text('Hủy'),
                                ),
                                TextButton(
                                  onPressed: () => Navigator.pop(ctx, true),
                                  style: TextButton.styleFrom(
                                    foregroundColor: AppTheme.red,
                                  ),
                                  child: const Text('Xóa'),
                                ),
                              ],
                            ),
                          );
                        },
                        onDismissed: (direction) async {
                          try {
                            await ref
                                .read(activeSessionsProvider.notifier)
                                .deleteSession(session.id);
                            if (context.mounted)
                              ref
                                  .read(activeSessionsProvider.notifier)
                                  .fetch(silent: true);
                          } catch (e) {
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(
                                    e.toString().replaceAll('Exception: ', ''),
                                  ),
                                ),
                              );
                              ref
                                  .read(activeSessionsProvider.notifier)
                                  .fetch(silent: true);
                            }
                          }
                        },
                        child: card,
                      );
                    }
                    return card;
                  },
                ),
              const SliverToBoxAdapter(child: SizedBox(height: 22)),
            ],
          ),
        ),
      ),
    );
  }
}

class _ScreenTitle extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;

  const _ScreenTitle({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: AppTheme.cyan, size: 24),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  color: AppTheme.textPrimary,
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                subtitle,
                style: const TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 12,
                  height: 1.3,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SessionCard extends StatefulWidget {
  final ParkingSession session;

  const _SessionCard({required this.session});

  @override
  State<_SessionCard> createState() => _SessionCardState();
}

class _SessionCardState extends State<_SessionCard> {
  late final Timer _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 20), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _timer.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final session = widget.session;
    final isPending = session.status == 'pending';
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: AppTheme.orange.withValues(alpha: 0.13),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: AppTheme.orange.withValues(alpha: 0.34),
                  ),
                ),
                child: Text(
                  session.slotId,
                  style: const TextStyle(
                    color: AppTheme.orange,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isPending ? 'Đang tạo phiên...' : 'Xe đang đỗ',
                      style: const TextStyle(
                        color: AppTheme.textPrimary,
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      isPending
                          ? 'Đang đồng bộ từ máy chủ'
                          : 'Bắt đầu: ${formatDateTime(session.startTime)}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppTheme.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              if (!isPending)
                Text(
                  formatDurationFull(session.liveDuration),
                  style: const TextStyle(
                    color: AppTheme.cyan,
                    fontWeight: FontWeight.w800,
                  ),
                )
              else
                const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2.5),
                ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _InfoTile(
                  label: 'Phí tạm tính',
                  value: formatCurrency(session.displayFeeVnd),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _InfoTile(
                  label: 'Mã phiên',
                  value: session.shortId.isEmpty ? 'Chưa có' : session.shortId,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _InfoTile extends StatelessWidget {
  final String label;
  final String value;

  const _InfoTile({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusSm),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 11),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 13,
              fontWeight: FontWeight.w700,
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
        padding: EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.event_available, color: AppTheme.green, size: 46),
            SizedBox(height: 12),
            Text(
              'Chưa có xe đang đỗ',
              style: TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w800,
              ),
            ),
            SizedBox(height: 6),
            Text(
              'Dữ liệu sẽ tự cập nhật khi có phiên active.',
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
        padding: const EdgeInsets.all(28),
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
