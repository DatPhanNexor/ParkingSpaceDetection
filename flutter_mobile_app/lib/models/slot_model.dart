class Slot {
  final String id;
  final String status;

  Slot({required this.id, required this.status});

  factory Slot.fromJson(Map<String, dynamic> json) {
    return Slot(
      id: json['slot_id'] ?? '',
      status: json['status'] ?? 'UNKNOWN',
    );
  }
}
