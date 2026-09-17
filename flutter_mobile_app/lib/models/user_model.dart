class User {
  final int id;
  final String username;
  final String displayName;
  final String role;
  final bool isActive;

  const User({
    required this.id,
    required this.username,
    required this.displayName,
    required this.role,
    required this.isActive,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: _asInt(json['id']),
      username: json['username']?.toString() ?? '',
      displayName:
          json['ho_ten']?.toString() ?? json['display_name']?.toString() ?? '',
      role: (json['role']?.toString() ?? 'staff').toLowerCase(),
      isActive: json['is_active'] == true || json['is_active'] == 1,
    );
  }

  bool get isAdmin => role == 'admin';
  bool get isStaff => role == 'staff';

  String get roleLabel => isAdmin ? 'Quản trị viên' : 'Nhân viên';

  String get nameForDisplay {
    if (displayName.trim().isNotEmpty) return displayName.trim();
    return username;
  }

  String get initials {
    final source = nameForDisplay.trim();
    if (source.isEmpty) return 'U';
    final parts = source.split(RegExp(r'\s+'));
    if (parts.length >= 2) {
      return '${parts.first.substring(0, 1)}${parts.last.substring(0, 1)}'
          .toUpperCase();
    }
    return source.substring(0, 1).toUpperCase();
  }
}

int _asInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}
