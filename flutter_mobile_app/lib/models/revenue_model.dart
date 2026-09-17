/// Revenue analytics from reporting service.
class RevenueData {
  final double totalRevenue;
  final int totalSessions;
  final double avgDurationMinutes;
  final List<DailyRevenue> dailyRevenue;
  final List<SlotUtilization> slotUtilization;

  const RevenueData({
    required this.totalRevenue,
    required this.totalSessions,
    required this.avgDurationMinutes,
    required this.dailyRevenue,
    required this.slotUtilization,
  });

  factory RevenueData.fromJson(Map<String, dynamic> json) {
    return RevenueData(
      totalRevenue: (json['total_revenue'] as num?)?.toDouble() ?? 0,
      totalSessions: json['total_sessions'] as int? ?? 0,
      avgDurationMinutes:
          (json['average_duration_minutes'] as num?)?.toDouble() ?? 0,
      dailyRevenue:
          (json['daily_revenue'] as List<dynamic>?)
              ?.map((e) => DailyRevenue.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      slotUtilization:
          (json['slot_utilization'] as List<dynamic>?)
              ?.map((e) => SlotUtilization.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

class DailyRevenue {
  final String date;
  final double revenue;
  final int sessions;

  const DailyRevenue({
    required this.date,
    required this.revenue,
    required this.sessions,
  });

  factory DailyRevenue.fromJson(Map<String, dynamic> json) {
    return DailyRevenue(
      date: json['date'] as String? ?? '',
      revenue: (json['revenue'] as num?)?.toDouble() ?? 0,
      sessions: json['sessions'] as int? ?? 0,
    );
  }
}

class SlotUtilization {
  final String slotId;
  final int totalSessions;
  final double totalDurationMinutes;
  final double totalRevenue;

  const SlotUtilization({
    required this.slotId,
    required this.totalSessions,
    required this.totalDurationMinutes,
    required this.totalRevenue,
  });

  factory SlotUtilization.fromJson(Map<String, dynamic> json) {
    return SlotUtilization(
      slotId: json['slot_id'] as String? ?? '',
      totalSessions: json['total_sessions'] as int? ?? 0,
      totalDurationMinutes:
          (json['total_duration_minutes'] as num?)?.toDouble() ?? 0,
      totalRevenue: (json['total_revenue'] as num?)?.toDouble() ?? 0,
    );
  }
}
