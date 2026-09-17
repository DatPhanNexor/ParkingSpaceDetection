import '../utils/helpers.dart';

class Alert {
  final int id;
  final String level;
  final String source;
  final String message;
  final DateTime? createdAt;

  const Alert({
    required this.id,
    required this.level,
    required this.source,
    required this.message,
    this.createdAt,
  });

  factory Alert.fromJson(Map<String, dynamic> json) {
    return Alert(
      id: asInt(json['id']),
      level: (json['level']?.toString() ?? 'info').toUpperCase(),
      source: json['source']?.toString() ?? 'system',
      message: json['message']?.toString() ?? '',
      createdAt: tryParseDate(json['created_at']),
    );
  }
}
