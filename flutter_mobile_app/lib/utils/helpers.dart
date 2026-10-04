import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

String formatDuration(Duration duration) {
  final hours = duration.inHours;
  final minutes = duration.inMinutes.remainder(60);
  final seconds = duration.inSeconds.remainder(60);
  if (hours > 0) {
    return '${hours}g ${minutes.toString().padLeft(2, '0')}p';
  }
  if (minutes > 0) {
    return '${minutes}p ${seconds.toString().padLeft(2, '0')}s';
  }
  return '${seconds}s';
}

String formatDurationFull(Duration duration) {
  final hours = duration.inHours.toString().padLeft(2, '0');
  final minutes = duration.inMinutes.remainder(60).toString().padLeft(2, '0');
  final seconds = duration.inSeconds.remainder(60).toString().padLeft(2, '0');
  return '$hours:$minutes:$seconds';
}

String formatCurrency(num? amount) {
  if (amount == null) return 'Chưa có';
  final value = amount.round();
  final raw = value.abs().toString();
  final parts = <String>[];
  for (var i = raw.length; i > 0; i -= 3) {
    final start = i - 3 < 0 ? 0 : i - 3;
    parts.insert(0, raw.substring(start, i));
  }
  final sign = value < 0 ? '-' : '';
  return '$sign${parts.join('.')}₫';
}

String formatDateTime(DateTime? value) {
  if (value == null) return 'Chưa có';
  final d = value.toLocal();
  return '${d.day.toString().padLeft(2, '0')}/'
      '${d.month.toString().padLeft(2, '0')}/${d.year} '
      '${d.hour.toString().padLeft(2, '0')}:'
      '${d.minute.toString().padLeft(2, '0')}';
}

String formatDate(DateTime? value) {
  if (value == null) return 'Chưa có';
  final d = value.toLocal();
  return '${d.day.toString().padLeft(2, '0')}/'
      '${d.month.toString().padLeft(2, '0')}/${d.year}';
}

DateTime? tryParseDate(dynamic value) {
  if (value == null) return null;
  if (value is DateTime) return value;

  final text = value.toString().trim();
  if (text.isEmpty) return null;
  if (text == '0' || text == '0.0') return null;

  // Try parsing as integer (Unix timestamp)
  final asInt = int.tryParse(text);
  if (asInt != null) {
    // If it's smaller than 10 billion, it's likely seconds.
    // If it's around 1.7 billion, it's 2024.
    // If it's less than 31536000 (1 year), it's probably wrong or just very early 1970.
    if (asInt < 31536000) return null; // Reject early 1970s as likely errors

    if (asInt < 10000000000) {
      return DateTime.fromMillisecondsSinceEpoch(
        asInt * 1000,
        isUtc: true,
      ).toLocal();
    }
    return DateTime.fromMillisecondsSinceEpoch(asInt, isUtc: true).toLocal();
  }

  // Try parsing as double
  final asDouble = double.tryParse(text);
  if (asDouble != null) {
    if (asDouble < 31536000) return null;
    if (asDouble < 10000000000) {
      return DateTime.fromMillisecondsSinceEpoch(
        (asDouble * 1000).toInt(),
        isUtc: true,
      ).toLocal();
    }
    return DateTime.fromMillisecondsSinceEpoch(
      asDouble.toInt(),
      isUtc: true,
    ).toLocal();
  }

  final parsed = DateTime.tryParse(text);
  if (parsed != null) {
    // If the parsed date is before 2000, it's likely an error (like 1970)
    if (parsed.year < 2000) return null;
    return parsed.toLocal();
  }

  return null;
}

String timeAgo(DateTime? value) {
  if (value == null) return 'Chưa cập nhật';
  final diff = DateTime.now().difference(value.toLocal());
  if (diff.inSeconds < 10) return 'Vừa cập nhật';
  if (diff.inSeconds < 60) return '${diff.inSeconds} giây trước';
  if (diff.inMinutes < 60) return '${diff.inMinutes} phút trước';
  if (diff.inHours < 24) return '${diff.inHours} giờ trước';
  return '${diff.inDays} ngày trước';
}

String friendlyError(Object error) {
  final text = error.toString();
  if (error is DioException) {
    final status = error.response?.statusCode;
    if (status == 401) {
      return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
    }
    if (status == 403) {
      return 'Tài khoản không có quyền xem dữ liệu này.';
    }
    if (status == 429) {
      return 'Có quá nhiều lần thử. Vui lòng chờ một chút rồi thử lại.';
    }
    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.receiveTimeout ||
        error.type == DioExceptionType.sendTimeout) {
      return 'Máy chủ phản hồi quá lâu. Vui lòng thử lại.';
    }
    if (error.type == DioExceptionType.connectionError) {
      return 'Không kết nối được máy chủ. Kiểm tra backend hoặc cấu hình mạng.';
    }
  }
  if (text.contains('SocketException') || text.contains('Connection refused')) {
    return 'Không kết nối được máy chủ. Kiểm tra backend hoặc cấu hình mạng.';
  }
  if (text.contains('401')) {
    return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
  }
  if (text.contains('403')) {
    return 'Tài khoản không có quyền xem dữ liệu này.';
  }
  return 'Đã xảy ra lỗi. Vui lòng thử lại.';
}

void showAppSnackBar(
  BuildContext context,
  String message, {
  bool isError = false,
}) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Text(message),
      backgroundColor: isError ? Colors.red.shade800 : null,
      duration: const Duration(seconds: 3),
    ),
  );
}

int asInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

double asDouble(dynamic value) {
  if (value is double) return value;
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? 0;
}
