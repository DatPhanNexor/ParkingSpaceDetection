import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/constants.dart';
import '../core/theme.dart';
import '../models/session_model.dart';
import '../models/slot_model.dart';
import '../models/user_model.dart';
import '../providers/dashboard_provider.dart';
import '../services/websocket_service.dart';
import '../utils/helpers.dart';
import '../widgets/parking_brand.dart';
import '../widgets/slot_grid.dart';

class DashboardScreen extends ConsumerStatefulWidget {
  final User user;
  final Future<void> Function({bool silent}) onRefreshAll;
  final Future<void> Function() onLogout;

  const DashboardScreen({
    super.key,
    required this.user,
    required this.onRefreshAll,
    required this.onLogout,
  });

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  @override
  Widget build(BuildContext context) {
    final slots = ref.watch(slotsProvider);
    final sessions = ref.watch(activeSessionsProvider);
    final ws =
        ref.watch(wsConnectionProvider).value ?? WsConnectionState.disconnected;

    return Scaffold(
      backgroundColor: AppTheme.navy,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => widget.onRefreshAll(silent: false),
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(18, 16, 18, 0),
                  child: _HeroHeader(
                    user: widget.user,
                    connectionState: ws,
                    lastUpdated: slots.lastUpdated,
                    onRefresh: () => widget.onRefreshAll(silent: false),
                    onLogout: widget.onLogout,
                  ),
                ),
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(18, 18, 18, 0),
                sliver: SliverToBoxAdapter(child: _KpiGrid(slots: slots)),
              ),
              if (slots.error != null)
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(18, 14, 18, 0),
                    child: _InlineWarning(
                      message:
                          '${friendlyError(Exception(slots.error!))} Dữ liệu cũ vẫn được giữ nếu có.',
                    ),
                  ),
                ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(18, 22, 18, 10),
                  child: _SectionHeader(
                    title: 'LIVE PARKING MAP',
                    trailing: timeAgo(slots.lastUpdated),
                  ),
                ),
              ),
              SliverPadding(
                padding: const EdgeInsets.symmetric(horizontal: 18),
                sliver: SliverToBoxAdapter(
                  child: slots.isLoading && slots.lastUpdated == null
                      ? const SizedBox(
                          height: 300,
                          child: Center(child: CircularProgressIndicator()),
                        )
                      : slots.error != null &&
                            slots.slots.every((slot) => !slot.isKnown)
                      ? _ErrorPanel(
                          message: friendlyError(Exception(slots.error!)),
                          onRetry: () => widget.onRefreshAll(silent: false),
                        )
                      : SlotGrid(
                          slots: slots.slots,
                          stale: slots.isStale,
                          onTap: (slot) =>
                              _showSlotDetail(slot, sessions.sessions),
                        ),
                ),
              ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(18, 22, 18, 10),
                  child: _SectionHeader(
                    title: 'Xe đang đỗ',
                    trailing: '${sessions.sessions.length} phiên',
                  ),
                ),
              ),
              if (sessions.error != null)
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(18, 0, 18, 12),
                    child: _InlineWarning(
                      message: friendlyError(Exception(sessions.error!)),
                    ),
                  ),
                ),
              if (sessions.isLoading && sessions.sessions.isEmpty)
                const SliverToBoxAdapter(
                  child: Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(child: CircularProgressIndicator()),
                  ),
                )
              else if (sessions.sessions.isEmpty)
                const SliverPadding(
                  padding: EdgeInsets.symmetric(horizontal: 18),
                  sliver: SliverToBoxAdapter(
                    child: _EmptyPanel(
                      icon: Icons.local_parking_outlined,
                      title: 'Chưa có xe đang đỗ',
                      message:
                          'Phiên đỗ xe sẽ xuất hiện khi hệ thống ghi nhận OCCUPIED.',
                    ),
                  ),
                )
              else
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(18, 0, 18, 24),
                  sliver: SliverList.separated(
                    itemCount: sessions.sessions.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 10),
                    itemBuilder: (context, index) {
                      return _ActiveSessionCard(
                        session: sessions.sessions[index],
                      );
                    },
                  ),
                ),
              const SliverToBoxAdapter(child: SizedBox(height: 18)),
            ],
          ),
        ),
      ),
    );
  }

  void _showSlotDetail(Slot slot, List<ParkingSession> sessions) {
    final session = sessions.where((item) => item.slotId == slot.id).firstOrNull;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (context) => _SlotDetailSheet(slot: slot, session: session),
    );
  }
}

class _HeroHeader extends StatelessWidget {
  final User user;
  final WsConnectionState connectionState;
  final DateTime? lastUpdated;
  final Future<void> Function() onRefresh;
  final Future<void> Function() onLogout;

  const _HeroHeader({
    required this.user,
    required this.connectionState,
    required this.lastUpdated,
    required this.onRefresh,
    required this.onLogout,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
        border: Border.all(color: AppTheme.border),
        gradient: const LinearGradient(
          colors: [AppTheme.cardLight, AppTheme.surface],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Row(
        children: [
          const ParkingBrand(size: 54),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  AppConstants.appName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: AppTheme.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${user.nameForDisplay} • ${user.roleLabel}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: AppTheme.textSecondary),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    _ConnectionBadge(state: connectionState),
                    Text(
                      timeAgo(lastUpdated),
                      style: const TextStyle(
                        color: AppTheme.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          IconButton(
            tooltip: 'Làm mới',
            onPressed: onRefresh,
            icon: const Icon(Icons.refresh, color: AppTheme.cyan),
          ),
          IconButton(
            tooltip: 'Đăng xuất',
            onPressed: onLogout,
            icon: const Icon(Icons.logout, color: AppTheme.textSecondary),
          ),
        ],
      ),
    );
  }
}

class _ConnectionBadge extends StatelessWidget {
  final WsConnectionState state;

  const _ConnectionBadge({required this.state});

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (state) {
      WsConnectionState.connected => ('LIVE', AppTheme.green),
      WsConnectionState.connecting => ('Đang kết nối', AppTheme.yellow),
      WsConnectionState.reconnecting => ('Đang nối lại', AppTheme.orange),
      WsConnectionState.paused => ('Tạm dừng', AppTheme.textSecondary),
      WsConnectionState.disconnected => ('Offline', AppTheme.red),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.28)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.circle, color: color, size: 8),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _KpiGrid extends StatelessWidget {
  final SlotsState slots;

  const _KpiGrid({required this.slots});

  @override
  Widget build(BuildContext context) {
    final items = [
      _KpiItem(
        'Tổng vị trí',
        '${slots.totalCount}',
        Icons.grid_view,
        AppTheme.cyan,
      ),
      _KpiItem(
        'Trống',
        '${slots.emptyCount}',
        Icons.check_circle_outline,
        AppTheme.green,
      ),
      _KpiItem(
        'Có xe',
        '${slots.occupiedCount}',
        Icons.directions_car,
        AppTheme.orange,
      ),
      _KpiItem(
        'Tỷ lệ lấp đầy',
        '${slots.occupancyRate.round()}%',
        Icons.speed,
        AppTheme.accentLight,
      ),
    ];

    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth > 620 ? 4 : 2;
        return GridView.builder(
          itemCount: items.length,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            childAspectRatio: columns == 4 ? 1.35 : 1.6,
          ),
          itemBuilder: (context, index) => _KpiCard(item: items[index]),
        );
      },
    );
  }
}

class _KpiItem {
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  const _KpiItem(this.label, this.value, this.icon, this.color);
}

class _KpiCard extends StatelessWidget {
  final _KpiItem item;

  const _KpiCard({required this.item});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Icon(item.icon, color: item.color, size: 24),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(
                  item.value,
                  style: TextStyle(
                    color: item.color,
                    fontSize: 24,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                item.label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final String? trailing;

  const _SectionHeader({required this.title, this.trailing});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(
          title,
          style: const TextStyle(
            color: AppTheme.textPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w800,
          ),
        ),
        const Spacer(),
        if (trailing != null)
          Text(
            trailing!,
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
          ),
      ],
    );
  }
}

class _InlineWarning extends StatelessWidget {
  final String message;

  const _InlineWarning({required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.redBg,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        border: Border.all(color: AppTheme.red.withValues(alpha: 0.28)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.warning_amber_rounded, color: AppTheme.red, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: AppTheme.textPrimary, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  final String message;
  final Future<void> Function() onRetry;

  const _ErrorPanel({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return _EmptyPanel(
      icon: Icons.cloud_off_outlined,
      title: 'Chưa tải được dữ liệu',
      message: message,
      action: TextButton.icon(
        onPressed: onRetry,
        icon: const Icon(Icons.refresh),
        label: const Text('Thử lại'),
      ),
    );
  }
}

class _EmptyPanel extends StatelessWidget {
  final IconData icon;
  final String title;
  final String message;
  final Widget? action;

  const _EmptyPanel({
    required this.icon,
    required this.title,
    required this.message,
    this.action,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        children: [
          Icon(icon, color: AppTheme.textSecondary, size: 30),
          const SizedBox(height: 10),
          Text(
            title,
            style: const TextStyle(
              color: AppTheme.textPrimary,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppTheme.textSecondary),
          ),
          if (action != null) ...[const SizedBox(height: 10), action!],
        ],
      ),
    );
  }
}

class _ActiveSessionCard extends StatelessWidget {
  final ParkingSession session;

  const _ActiveSessionCard({required this.session});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppTheme.orange.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(AppTheme.radiusSm),
            ),
            child: Text(
              session.slotId,
              style: const TextStyle(
                color: AppTheme.orange,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Phiên ${session.shortId}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Vào lúc ${formatDateTime(session.startTime)}',
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
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                formatDurationFull(session.displayDuration),
                style: const TextStyle(
                  color: AppTheme.cyan,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                formatCurrency(session.feeVnd),
                style: const TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SlotDetailSheet extends StatelessWidget {
  final Slot slot;
  final ParkingSession? session;

  const _SlotDetailSheet({required this.slot, required this.session});

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.statusColor(slot.status);
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 24),
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 42,
                height: 4,
                decoration: BoxDecoration(
                  color: AppTheme.border,
                  borderRadius: BorderRadius.circular(99),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Icon(AppTheme.statusIcon(slot.status), color: color),
                const SizedBox(width: 10),
                Text(
                  slot.id,
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const Spacer(),
                Text(
                  AppTheme.statusLabel(slot.status),
                  style: TextStyle(color: color, fontWeight: FontWeight.w800),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _DetailRow('Cập nhật', formatDateTime(slot.updatedAt)),
            _DetailRow('Bắt đầu', formatDateTime(slot.startedAt)),
            if (session != null) ...[
              _DetailRow('Phiên', session!.shortId),
              _DetailRow('Thời gian', formatDurationFull(session!.displayDuration)),
              _DetailRow('Phí', formatCurrency(session!.feeVnd)),
            ],
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final String label;
  final String value;

  const _DetailRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        children: [
          Text(label, style: const TextStyle(color: AppTheme.textSecondary)),
          const Spacer(),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: const TextStyle(
                color: AppTheme.textPrimary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
