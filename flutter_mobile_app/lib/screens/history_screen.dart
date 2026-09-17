import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/constants.dart';
import '../core/theme.dart';
import '../models/session_model.dart';
import '../providers/dashboard_provider.dart';
import '../utils/helpers.dart';

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  int _filter = 0;
  String? _slotId;

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(historyProvider.notifier).fetch());
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(historyProvider);
    final sessions = _filtered(state.sessions);

    return Scaffold(
      backgroundColor: AppTheme.navy,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => ref.read(historyProvider.notifier).fetch(),
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
                  child: _Header(count: sessions.length),
                ),
              ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
                  child: _buildFilters(),
                ),
              ),
              if (state.isLoading && state.sessions.isEmpty)
                const SliverFillRemaining(
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (state.error != null && state.sessions.isEmpty)
                SliverFillRemaining(
                  child: _ErrorPanel(
                    message: friendlyError(Exception(state.error!)),
                    onRetry: () => ref.read(historyProvider.notifier).fetch(),
                  ),
                )
              else if (sessions.isEmpty)
                const SliverFillRemaining(
                  hasScrollBody: false,
                  child: _EmptyPanel(),
                )
              else
                SliverList.builder(
                  itemCount: sessions.length,
                  itemBuilder: (context, index) => Padding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                    child: _HistoryCard(session: sessions[index]),
                  ),
                ),
              const SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.fromLTRB(20, 8, 20, 24),
                  child: Text(
                    'Bộ lọc được áp dụng trên 50 giao dịch mới nhất do backend trả về.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: AppTheme.textSecondary,
                      fontSize: 11,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  List<ParkingSession> _filtered(List<ParkingSession> input) {
    final now = DateTime.now();
    Iterable<ParkingSession> result = input;
    if (_filter == 1) {
      result = result.where((item) {
        final start = item.startTime;
        return start != null &&
            start.year == now.year &&
            start.month == now.month &&
            start.day == now.day;
      });
    } else if (_filter == 2) {
      final sevenDaysAgo = now.subtract(const Duration(days: 7));
      result = result.where((item) {
        final start = item.startTime;
        return start != null && start.isAfter(sevenDaysAgo);
      });
    }
    if (_slotId != null) {
      result = result.where((item) => item.slotId == _slotId);
    }
    return result.toList();
  }

  Widget _buildFilters() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              _FilterChip(
                label: 'Tất cả',
                selected: _filter == 0,
                onTap: () => setState(() => _filter = 0),
              ),
              const SizedBox(width: 8),
              _FilterChip(
                label: 'Hôm nay',
                selected: _filter == 1,
                onTap: () => setState(() => _filter = 1),
              ),
              const SizedBox(width: 8),
              _FilterChip(
                label: '7 ngày',
                selected: _filter == 2,
                onTap: () => setState(() => _filter = 2),
              ),
              const SizedBox(width: 8),
              PopupMenuButton<String?>(
                tooltip: 'Lọc theo vị trí',
                color: AppTheme.cardLight,
                onSelected: (value) => setState(() => _slotId = value),
                itemBuilder: (context) => [
                  const PopupMenuItem<String?>(
                    value: null,
                    child: Text('Tất cả vị trí'),
                  ),
                  for (final id in AppConstants.slotIds)
                    PopupMenuItem<String?>(value: id, child: Text(id)),
                ],
                child: _FilterChip(
                  label: _slotId == null ? 'Vị trí' : _slotId!,
                  selected: _slotId != null,
                  onTap: () {},
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Header extends StatelessWidget {
  final int count;

  const _Header({required this.count});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Icon(Icons.history, color: AppTheme.cyan, size: 24),
        const SizedBox(width: 10),
        const Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Lịch sử đỗ xe',
                style: TextStyle(
                  color: AppTheme.textPrimary,
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                ),
              ),
              SizedBox(height: 3),
              Text(
                'Giao dịch đã hoàn tất',
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 12),
              ),
            ],
          ),
        ),
        Text(
          '$count phiên',
          style: const TextStyle(
            color: AppTheme.textSecondary,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppTheme.radiusSm),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? AppTheme.accent : AppTheme.card,
          borderRadius: BorderRadius.circular(AppTheme.radiusSm),
          border: Border.all(
            color: selected ? AppTheme.accent : AppTheme.border,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? Colors.white : AppTheme.textSecondary,
            fontSize: 12,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}

class _HistoryCard extends StatelessWidget {
  final ParkingSession session;

  const _HistoryCard({required this.session});

  @override
  Widget build(BuildContext context) {
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
            width: 44,
            height: 44,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppTheme.accent.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(11),
              border: Border.all(
                color: AppTheme.accent.withValues(alpha: 0.32),
              ),
            ),
            child: Text(
              session.slotId,
              style: const TextStyle(
                color: AppTheme.cyan,
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
                  'Vào: ${formatDateTime(session.startTime)}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Ra: ${formatDateTime(session.endTime)}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.textSecondary,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Thời lượng: ${formatDuration(session.displayDuration)}',
                  style: const TextStyle(
                    color: AppTheme.textSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 96),
            child: Text(
              formatCurrency(session.feeVnd),
              textAlign: TextAlign.right,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppTheme.green,
                fontWeight: FontWeight.w800,
              ),
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
            Icon(Icons.inbox_outlined, color: AppTheme.textSecondary, size: 48),
            SizedBox(height: 12),
            Text(
              'Chưa có lịch sử đỗ xe',
              style: TextStyle(
                color: AppTheme.textPrimary,
                fontWeight: FontWeight.w800,
              ),
            ),
            SizedBox(height: 6),
            Text(
              'Giao dịch sẽ xuất hiện khi backend ghi nhận xe rời bãi.',
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
