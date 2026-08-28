class Session {
  final String slotId;
  final String sessionId;
  final String startedAt;

  Session({required this.slotId, required this.sessionId, required this.startedAt});

  factory Session.fromJson(Map<String, dynamic> json) {
    return Session(
      slotId: json['slot_id'] ?? '',
      sessionId: json['session_id'] ?? '',
      startedAt: json['started_at'] ?? '',
    );
  }
}
