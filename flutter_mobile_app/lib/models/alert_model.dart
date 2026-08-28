class Alert {
  final int id;
  final String level;
  final String source;
  final String message;
  final String createdAt;

  Alert({required this.id, required this.level, required this.source, required this.message, required this.createdAt});

  factory Alert.fromJson(Map<String, dynamic> json) {
    return Alert(
      id: json['id'] ?? 0,
      level: json['level'] ?? '',
      source: json['source'] ?? '',
      message: json['message'] ?? '',
      createdAt: json['created_at'] ?? '',
    );
  }
}
