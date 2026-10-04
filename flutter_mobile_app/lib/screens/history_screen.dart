import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme.dart';
import '../models/session_model.dart';
import '../providers/dashboard_provider.dart';
import '../utils/helpers.dart';
import '../repositories/auth_repository.dart';

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  int _filter = 0;
  bool _selectionMode = false;
  final Set<String> _selectedIds = {};

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(historyProvider.notifier).fetch());
  }

  List<ParkingSession> _filtered(List<ParkingSession> raw) {
    if (_filter == 0) return raw;
    final now = DateTime.now();
    return raw.where((s) {
      if (s.endTime == null) return false;
      final diff = now.difference(s.endTime!);
      if (_filter == 1) return diff.inDays == 0 && now.day == s.endTime!.day;
      if (_filter == 2) return diff.inDays <= 7;
      return true;
    }).toList();
  }

  void _toggleSelection(String id) {
    setState(() {
      if (_selectedIds.contains(id)) {
        _selectedIds.remove(id);
      } else {
        _selectedIds.add(id);
      }
    });
  }

  void _selectAll(List<ParkingSession> visibleSessions) {
    setState(() {
      if (_selectedIds.length == visibleSessions.length) {
        _selectedIds.clear();
      } else {
        _selectedIds.addAll(visibleSessions.map((e) => e.id));
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(historyProvider);
    final sessions = _filtered(state.sessions);
    final user = ref.watch(authStateProvider).value;
    final isAdmin = user?.isAdmin == true;

    // Filter out selections that are no longer visible
    if (_selectionMode) {
      final visibleIds = sessions.map((e) => e.id).toSet();
      _selectedIds.retainWhere((id) => visibleIds.contains(id));
    }

    return Scaffold(
      backgroundColor: AppTheme.navy,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            setState(() {
              _selectionMode = false;
              _selectedIds.clear();
            });
            await ref.read(historyProvider.notifier).fetch();
          },
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
                  child: _Header(
                    count: sessions.length,
                    isAdmin: isAdmin,
                    selectionMode: _selectionMode,
                    allSelected:
                        _selectedIds.length == sessions.length &&
                        sessions.isNotEmpty,
                    onToggleSelectionMode: () {
                      setState(() {
                        _selectionMode = !_selectionMode;
                        _selectedIds.clear();
                      });
                    },
                    onSelectAll: () => _selectAll(sessions),
                  ),
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
                  hasScrollBody: false,
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (state.error != null && state.sessions.isEmpty)
                SliverFillRemaining(
                  hasScrollBody: false,
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
                  itemBuilder: (context, index) {
                    final session = sessions[index];
                    final isSelected = _selectedIds.contains(session.id);

                    Widget cardWidget = Padding(
                      padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                      child: Row(
                        children: [
                          if (_selectionMode) ...[
                            Checkbox(
                              value: isSelected,
                              onChanged: (_) => _toggleSelection(session.id),
                              activeColor: AppTheme.red,
                            ),
                            const SizedBox(width: 8),
                          ],
                          Expanded(
                            child: GestureDetector(
                              onTap: _selectionMode
                                  ? () => _toggleSelection(session.id)
                                  : null,
                              child: _HistoryCard(session: session),
                            ),
                          ),
                        ],
                      ),
                    );

                    if (isAdmin && !_selectionMode) {
                      cardWidget = Dismissible(
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
                          child: const Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.delete_outline, color: Colors.white),
                              SizedBox(width: 8),
                              Text(
                                'Xóa',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ),
                        confirmDismiss: (direction) async {
                          return await showDialog<bool>(
                            context: context,
                            builder: (ctx) => AlertDialog(
                              title: const Text('Xóa lịch sử đỗ xe?'),
                              content: Text(
                                'Bạn có chắc muốn xóa phiên ${session.slotId} này? Thao tác này không thể hoàn tác.',
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
                                .read(historyProvider.notifier)
                                .deleteSession(session.id);
                          } catch (e) {
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text(
                                    'Không thể xóa dữ liệu. Vui lòng thử lại.',
                                  ),
                                ),
                              );
                              ref
                                  .read(historyProvider.notifier)
                                  .fetch(silent: true);
                            }
                          }
                        },
                        child: cardWidget,
                      );
                    }
                    return cardWidget;
                  },
                ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: _selectionMode
          ? SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: ElevatedButton.icon(
                  onPressed: _selectedIds.isEmpty
                      ? null
                      : () async {
                          final confirm = await showDialog<bool>(
                            context: context,
                            builder: (ctx) => AlertDialog(
                              title: Text(
                                'Xóa ${_selectedIds.length} lịch sử đã chọn?',
                              ),
                              content: const Text(
                                'Bạn có chắc muốn xóa các phiên đã chọn? Thao tác này không thể hoàn tác.',
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
                                  child: Text('Xóa ${_selectedIds.length}'),
                                ),
                              ],
                            ),
                          );
                          if (confirm == true) {
                            try {
                              await ref
                                  .read(historyProvider.notifier)
                                  .deleteBatchSessions(_selectedIds.toList());
                              if (context.mounted) {
                                setState(() {
                                  _selectionMode = false;
                                  _selectedIds.clear();
                                });
                              }
                            } catch (e) {
                              if (context.mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text(
                                      'Không thể xóa dữ liệu. Vui lòng thử lại.',
                                    ),
                                  ),
                                );
                              }
                            }
                          }
                        },
                  icon: const Icon(Icons.delete_outline),
                  label: Text('Xóa ${_selectedIds.length}'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.red,
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: AppTheme.red.withValues(
                      alpha: 0.3,
                    ),
                    minimumSize: const Size.fromHeight(50),
                  ),
                ),
              ),
            )
          : null,
    );
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
                onTap: () {
                  setState(() => _filter = 0);
                },
              ),
              const SizedBox(width: 8),
              _FilterChip(
                label: 'Hôm nay',
                selected: _filter == 1,
                onTap: () {
                  setState(() => _filter = 1);
                },
              ),
              const SizedBox(width: 8),
              _FilterChip(
                label: '7 ngày',
                selected: _filter == 2,
                onTap: () {
                  setState(() => _filter = 2);
                },
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
  final bool isAdmin;
  final bool selectionMode;
  final bool allSelected;
  final VoidCallback onToggleSelectionMode;
  final VoidCallback onSelectAll;

  const _Header({
    required this.count,
    required this.isAdmin,
    required this.selectionMode,
    required this.allSelected,
    required this.onToggleSelectionMode,
    required this.onSelectAll,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Icon(Icons.history, color: AppTheme.cyan, size: 24),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Lịch sử đỗ xe',
                style: TextStyle(
                  color: AppTheme.textPrimary,
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                'Giao dịch đã hoàn tất',
                style: const TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
        if (selectionMode) ...[
          TextButton(
            onPressed: onSelectAll,
            child: Text(
              allSelected ? 'Bỏ chọn' : 'Chọn tất cả',
              style: const TextStyle(color: AppTheme.accent),
            ),
          ),
          TextButton(
            onPressed: onToggleSelectionMode,
            child: const Text(
              'Hủy',
              style: TextStyle(color: AppTheme.textSecondary),
            ),
          ),
        ] else if (isAdmin && count > 0) ...[
          TextButton(
            onPressed: onToggleSelectionMode,
            child: const Text('Chọn', style: TextStyle(color: AppTheme.accent)),
          ),
          const SizedBox(width: 8),
          Text(
            '$count phiên',
            style: const TextStyle(
              color: AppTheme.textSecondary,
              fontWeight: FontWeight.w700,
            ),
          ),
        ] else ...[
          Text(
            '$count phiên',
            style: const TextStyle(
              color: AppTheme.textSecondary,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
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
