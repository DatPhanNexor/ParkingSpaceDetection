import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme.dart';
import '../providers/dashboard_provider.dart';
import '../utils/helpers.dart';

class ReportScreen extends ConsumerStatefulWidget {
  final bool isAdmin;

  const ReportScreen({super.key, required this.isAdmin});

  @override
  ConsumerState<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends ConsumerState<ReportScreen> {
  @override
  void initState() {
    super.initState();
    if (widget.isAdmin) {
      Future.microtask(() => ref.read(reportProvider.notifier).fetchAll());
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.isAdmin) {
      return const _AdminOnly();
    }

    final state = ref.watch(reportProvider);
    return Scaffold(
      backgroundColor: AppTheme.navy,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => ref.read(reportProvider.notifier).fetchAll(),
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              const SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.fromLTRB(20, 16, 20, 0),
                  child: _Title(),
                ),
              ),
              if (state.isLoading && state.summary == null)
                const SliverFillRemaining(
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (state.error != null && state.summary == null)
                SliverFillRemaining(
                  child: _ErrorPanel(
                    message: friendlyError(Exception(state.error!)),
                    onRetry: () => ref.read(reportProvider.notifier).fetchAll(),
                  ),
                )
              else ...[
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 18, 20, 0),
                    child: _SummaryGrid(summary: state.summary ?? const {}),
                  ),
                ),
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 22, 20, 10),
                    child: _SectionHeader(
                      title: 'Doanh thu theo vị trí',
                      subtitle: 'Từ reporting service',
                    ),
                  ),
                ),
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: state.revenue.isEmpty
                        ? const _EmptyCard(
                            message: 'Chưa có dữ liệu doanh thu.',
                          )
                        : _RevenueChart(items: state.revenue),
                  ),
                ),
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 22, 20, 10),
                    child: _SectionHeader(
                      title: 'Tần suất sử dụng',
                      subtitle: 'Số phiên theo từng slot',
                    ),
                  ),
                ),
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: state.frequency.isEmpty
                        ? const _EmptyCard(message: 'Chưa có dữ liệu tần suất.')
                        : _FrequencyList(items: state.frequency),
                  ),
                ),
              ],
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
        Icon(Icons.bar_chart, color: AppTheme.cyan, size: 24),
        SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Báo cáo & phân tích',
                style: TextStyle(
                  color: AppTheme.textPrimary,
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                ),
              ),
              SizedBox(height: 3),
              Text(
                'Dành cho tài khoản admin',
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 12),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SummaryGrid extends StatelessWidget {
  final Map<String, dynamic> summary;

  const _SummaryGrid({required this.summary});

  @override
  Widget build(BuildContext context) {
    final items = [
      _SummaryItem(
        label: 'Tổng phiên',
        value: '${asInt(summary['total_sessions'])}',
        icon: Icons.receipt_long,
        color: AppTheme.accent,
      ),
      _SummaryItem(
        label: 'Đang hoạt động',
        value: '${asInt(summary['active_sessions'])}',
        icon: Icons.directions_car,
        color: AppTheme.orange,
      ),
      _SummaryItem(
        label: 'Tổng doanh thu',
        value: formatCurrency(asDouble(summary['total_revenue'])),
        icon: Icons.payments_outlined,
        color: AppTheme.green,
      ),
    ];

    return Column(
      children: [
        Row(
          children: [
            Expanded(child: _SummaryCard(item: items[0])),
            const SizedBox(width: 10),
            Expanded(child: _SummaryCard(item: items[1])),
          ],
        ),
        const SizedBox(height: 10),
        _SummaryCard(item: items[2], wide: true),
      ],
    );
  }
}

class _SummaryItem {
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  const _SummaryItem({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });
}

class _SummaryCard extends StatelessWidget {
  final _SummaryItem item;
  final bool wide;

  const _SummaryCard({required this.item, this.wide = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        children: [
          Icon(item.icon, color: item.color, size: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    item.value,
                    style: TextStyle(
                      color: item.color,
                      fontSize: wide ? 22 : 18,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  item.label,
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

class _RevenueChart extends StatelessWidget {
  final List<Map<String, dynamic>> items;

  const _RevenueChart({required this.items});

  @override
  Widget build(BuildContext context) {
    final maxRevenue = _maxValue(items, 'revenue');
    final safeMax = maxRevenue <= 0 ? 1.0 : maxRevenue * 1.18;
    return Container(
      height: 230,
      padding: const EdgeInsets.fromLTRB(12, 16, 12, 8),
      decoration: _panelDecoration(),
      child: BarChart(
        BarChartData(
          maxY: safeMax,
          alignment: BarChartAlignment.spaceAround,
          barTouchData: BarTouchData(
            touchTooltipData: BarTouchTooltipData(
              getTooltipColor: (_) => AppTheme.cardLight,
              getTooltipItem: (group, groupIndex, rod, rodIndex) {
                final item = items[group.x.toInt()];
                return BarTooltipItem(
                  '${item['slot_id']}\n${formatCurrency(asDouble(item['revenue']))}',
                  const TextStyle(color: AppTheme.textPrimary, fontSize: 11),
                );
              },
            ),
          ),
          gridData: FlGridData(
            drawVerticalLine: false,
            horizontalInterval: safeMax / 4,
            getDrawingHorizontalLine: (value) =>
                FlLine(color: AppTheme.border, strokeWidth: 0.6),
          ),
          borderData: FlBorderData(show: false),
          titlesData: FlTitlesData(
            leftTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            rightTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            topTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 28,
                getTitlesWidget: (value, meta) {
                  final index = value.toInt();
                  if (index < 0 || index >= items.length) {
                    return const SizedBox.shrink();
                  }
                  return Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      items[index]['slot_id']?.toString() ?? '',
                      style: const TextStyle(
                        color: AppTheme.textSecondary,
                        fontSize: 10,
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
          barGroups: [
            for (var i = 0; i < items.length; i++)
              BarChartGroupData(
                x: i,
                barRods: [
                  BarChartRodData(
                    toY: asDouble(items[i]['revenue']),
                    width: 16,
                    color: AppTheme.accent,
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(4),
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _FrequencyList extends StatelessWidget {
  final List<Map<String, dynamic>> items;

  const _FrequencyList({required this.items});

  @override
  Widget build(BuildContext context) {
    final maxSessions = _maxValue(items, 'sessions');
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _panelDecoration(),
      child: Column(
        children: [
          for (final item in items)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 5),
              child: Row(
                children: [
                  SizedBox(
                    width: 42,
                    child: Text(
                      item['slot_id']?.toString() ?? '',
                      style: const TextStyle(
                        color: AppTheme.textPrimary,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  Expanded(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(5),
                      child: LinearProgressIndicator(
                        value: maxSessions == 0
                            ? 0
                            : asDouble(item['sessions']) / maxSessions,
                        minHeight: 14,
                        backgroundColor: AppTheme.surface,
                        valueColor: const AlwaysStoppedAnimation<Color>(
                          AppTheme.cyan,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  SizedBox(
                    width: 34,
                    child: Text(
                      '${asInt(item['sessions'])}',
                      textAlign: TextAlign.right,
                      style: const TextStyle(color: AppTheme.textSecondary),
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

class _SectionHeader extends StatelessWidget {
  final String title;
  final String subtitle;

  const _SectionHeader({required this.title, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(
            color: AppTheme.textPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          subtitle,
          style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
        ),
      ],
    );
  }
}

class _AdminOnly extends StatelessWidget {
  const _AdminOnly();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: AppTheme.navy,
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.lock_outline,
                  color: AppTheme.textSecondary,
                  size: 48,
                ),
                SizedBox(height: 14),
                Text(
                  'Chỉ dành cho quản trị viên',
                  style: TextStyle(
                    color: AppTheme.textPrimary,
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                SizedBox(height: 6),
                Text(
                  'Backend chỉ cho role admin xem báo cáo doanh thu và tần suất.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppTheme.textSecondary),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _EmptyCard extends StatelessWidget {
  final String message;

  const _EmptyCard({required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: _panelDecoration(),
      child: Text(
        message,
        textAlign: TextAlign.center,
        style: const TextStyle(color: AppTheme.textSecondary),
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

BoxDecoration _panelDecoration() {
  return BoxDecoration(
    color: AppTheme.card,
    borderRadius: BorderRadius.circular(AppTheme.radiusMd),
    border: Border.all(color: AppTheme.border),
  );
}

double _maxValue(List<Map<String, dynamic>> items, String key) {
  if (items.isEmpty) return 0;
  return items
      .map((item) => asDouble(item[key]))
      .fold<double>(0, (a, b) => a > b ? a : b);
}
