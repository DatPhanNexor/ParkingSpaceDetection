import 'slot_model.dart';

/// Dashboard summary from reporting service.
class DashboardData {
  final int totalSlots;
  final int emptySlots;
  final int occupiedSlots;
  final double occupancyRate;
  final int activeSessions;
  final int todaySessions;
  final double todayRevenue;
  final List<Slot> slots;

  const DashboardData({
    required this.totalSlots,
    required this.emptySlots,
    required this.occupiedSlots,
    required this.occupancyRate,
    required this.activeSessions,
    required this.todaySessions,
    required this.todayRevenue,
    required this.slots,
  });

  factory DashboardData.fromJson(Map<String, dynamic> json) {
    final slotList =
        (json['slots'] as List<dynamic>?)
            ?.map((e) => Slot.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [];
    return DashboardData(
      totalSlots: json['total_slots'] as int? ?? 9,
      emptySlots: json['empty_slots'] as int? ?? 0,
      occupiedSlots: json['occupied_slots'] as int? ?? 0,
      occupancyRate: (json['occupancy_rate'] as num?)?.toDouble() ?? 0,
      activeSessions: json['active_sessions'] as int? ?? 0,
      todaySessions: json['today_sessions'] as int? ?? 0,
      todayRevenue: (json['today_revenue'] as num?)?.toDouble() ?? 0,
      slots: slotList,
    );
  }
}
