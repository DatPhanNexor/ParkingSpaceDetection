import '../utils/helpers.dart';

class Slot {
  final String id;
  final String status;
  final String? sessionId;
  final DateTime? startedAt;
  final DateTime? updatedAt;

  const Slot({
    required this.id,
    required this.status,
    this.sessionId,
    this.startedAt,
    this.updatedAt,
  });

  factory Slot.unknown(String id) => Slot(id: id, status: 'UNKNOWN');

  factory Slot.fromJson(Map<String, dynamic> json) {
    final rawStatus = (json['status']?.toString() ?? 'UNKNOWN').toUpperCase();
    final status = switch (rawStatus) {
      'EMPTY' => 'EMPTY',
      'OCCUPIED' => 'OCCUPIED',
      _ => 'UNKNOWN',
    };
    return Slot(
      id: json['slot_id']?.toString() ?? json['id']?.toString() ?? '',
      status: status,
      sessionId: _optionalText(json['session_id']),
      startedAt: tryParseDate(json['started_at']),
      updatedAt: tryParseDate(json['updated_at']),
    );
  }

  bool get isOccupied => status == 'OCCUPIED';
  bool get isEmpty => status == 'EMPTY';
  bool get isKnown => isOccupied || isEmpty;

  Slot copyWith({
    String? id,
    String? status,
    String? sessionId,
    DateTime? startedAt,
    DateTime? updatedAt,
  }) {
    return Slot(
      id: id ?? this.id,
      status: status ?? this.status,
      sessionId: sessionId ?? this.sessionId,
      startedAt: startedAt ?? this.startedAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}

String? _optionalText(dynamic value) {
  final text = value?.toString().trim();
  if (text == null || text.isEmpty) return null;
  return text;
}
