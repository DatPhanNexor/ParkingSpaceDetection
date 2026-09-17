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
  return DateTime.tryParse(text);
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
