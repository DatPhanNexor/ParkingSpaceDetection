import '../utils/helpers.dart';

class ParkingSession {
  final String id;
  final String slotId;
  final DateTime? startTime;
  final DateTime? endTime;
  final int? durationSeconds;
  final num? feeVnd;
  final String status;

  const ParkingSession({
    required this.id,
    required this.slotId,
    this.startTime,
    this.endTime,
    this.durationSeconds,
    this.feeVnd,
    required this.status,
  });

  factory ParkingSession.fromJson(Map<String, dynamic> json) {
    final start = tryParseDate(json['started_at'] ?? json['gio_vao']);
    final end = tryParseDate(json['ended_at'] ?? json['gio_ra']);
    final computedDuration = start != null && end != null
        ? end.difference(start).inSeconds
        : null;
    return ParkingSession(
      id: (json['session_id'] ?? json['transaction_id'] ?? json['id'] ?? '')
          .toString(),
      slotId: json['slot_id']?.toString() ?? '',
      startTime: start,
      endTime: end,
      durationSeconds:
          _asNullableInt(json['duration_seconds']) ??
          _asNullableInt(json['duration']) ??
          computedDuration,
      feeVnd: _asNullableNum(
        json['thanh_tien'] ?? json['fee_vnd'] ?? json['fee'],
      ),
      status:
          (json['status']?.toString() ?? (end == null ? 'active' : 'completed'))
              .toLowerCase(),
    );
  }

  bool get isActive => endTime == null;
  bool get isCompleted => endTime != null;

  Duration get liveDuration {
    if (startTime == null) return Duration.zero;
    return DateTime.now().difference(startTime!.toLocal());
  }

  Duration get displayDuration {
    if (durationSeconds != null) return Duration(seconds: durationSeconds!);
    if (startTime != null && endTime != null) {
      return endTime!.difference(startTime!);
    }
    return liveDuration;
  }

  String get shortId {
    if (id.length <= 12) return id;
    return '${id.substring(0, 12)}...';
  }
}

int? _asNullableInt(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value.toString());
}

num? _asNullableNum(dynamic value) {
  if (value == null) return null;
  if (value is num) return value;
  return num.tryParse(value.toString());
}
