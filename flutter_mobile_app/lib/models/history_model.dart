class History {
  final String transactionId;
  final String slotId;
  final String startedAt;
  final String endedAt;
  final int fee;

  History({required this.transactionId, required this.slotId, required this.startedAt, required this.endedAt, required this.fee});

  factory History.fromJson(Map<String, dynamic> json) {
    return History(
      transactionId: json['transaction_id'] ?? '',
      slotId: json['slot_id'] ?? '',
      startedAt: json['gio_vao'] ?? '',
      endedAt: json['gio_ra'] ?? '',
      fee: json['thanh_tien'] ?? 0,
    );
  }
}
