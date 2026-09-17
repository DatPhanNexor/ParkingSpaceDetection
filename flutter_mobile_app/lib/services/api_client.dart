import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../core/constants.dart';

class ApiFailure implements Exception {
  final String message;
  final int? statusCode;

  const ApiFailure(this.message, {this.statusCode});

  factory ApiFailure.fromDio(DioException error) {
    final status = error.response?.statusCode;
    final detail = _serverDetail(error.response?.data);
    if (status == 401) {
      return const ApiFailure('Phiên đăng nhập đã hết hạn.', statusCode: 401);
    }
    if (status == 403) {
      return const ApiFailure(
        'Tài khoản không có quyền xem dữ liệu này.',
        statusCode: 403,
      );
    }
    if (status == 429) {
      return ApiFailure(
        detail ?? 'Có quá nhiều lần thử. Vui lòng chờ rồi thử lại.',
        statusCode: 429,
      );
    }
    if (detail != null && detail.isNotEmpty) {
      return ApiFailure(detail, statusCode: status);
    }
    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.receiveTimeout ||
        error.type == DioExceptionType.sendTimeout) {
      return const ApiFailure('Máy chủ phản hồi quá lâu.');
    }
    if (error.type == DioExceptionType.connectionError) {
      return const ApiFailure('Không kết nối được máy chủ.');
    }
    return const ApiFailure('Không thể tải dữ liệu. Vui lòng thử lại.');
  }

  @override
  String toString() => message;
}

class ApiClient {
  final Dio dio;
  final FlutterSecureStorage storage;
  Future<String?>? _refreshFuture;

  ApiClient({Dio? dio, FlutterSecureStorage? storage})
    : dio =
          dio ??
          Dio(
            BaseOptions(
              connectTimeout: AppConstants.httpTimeout,
              receiveTimeout: AppConstants.httpTimeout,
              sendTimeout: AppConstants.httpTimeout,
            ),
          ),
      storage = storage ?? const FlutterSecureStorage() {
    this.dio.interceptors.add(_AuthInterceptor(this));
  }

  Future<String?> get accessToken => storage.read(key: 'access_token');
  Future<String?> get refreshToken => storage.read(key: 'refresh_token');
  Future<bool> get hasToken async => (await accessToken) != null;

  Future<void> saveTokens({
    required String accessToken,
    String? refreshToken,
  }) async {
    await storage.write(key: 'access_token', value: accessToken);
    if (refreshToken != null && refreshToken.isNotEmpty) {
      await storage.write(key: 'refresh_token', value: refreshToken);
    }
  }

  Future<void> clearTokens() async {
    await storage.delete(key: 'access_token');
    await storage.delete(key: 'refresh_token');
  }

  Future<String?> refreshAccessToken() {
    final current = _refreshFuture;
    if (current != null) return current;

    final future = _refreshAccessToken();
    _refreshFuture = future.whenComplete(() => _refreshFuture = null);
    return _refreshFuture!;
  }

  Future<String?> _refreshAccessToken() async {
    final token = await refreshToken;
    if (token == null || token.isEmpty) {
      await clearTokens();
      return null;
    }

    try {
      final refreshDio = Dio(
        BaseOptions(
          connectTimeout: AppConstants.httpTimeout,
          receiveTimeout: AppConstants.httpTimeout,
          sendTimeout: AppConstants.httpTimeout,
        ),
      );
      final response = await refreshDio.post<Map<String, dynamic>>(
        AppConstants.refreshUrl,
        data: {'refresh_token': token},
      );
      final data = response.data ?? <String, dynamic>{};
      final newAccess = data['access_token']?.toString();
      final newRefresh = data['refresh_token']?.toString();
      if (newAccess == null || newAccess.isEmpty) {
        await clearTokens();
        return null;
      }
      await saveTokens(accessToken: newAccess, refreshToken: newRefresh);
      return newAccess;
    } on DioException {
      await clearTokens();
      return null;
    }
  }
}

class _AuthInterceptor extends Interceptor {
  final ApiClient _client;

  _AuthInterceptor(this._client);

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    _attachToken(options).then((_) => handler.next(options));
  }

  Future<void> _attachToken(RequestOptions options) async {
    final token = await _client.accessToken;
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    _handleError(err, handler);
  }

  Future<void> _handleError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final alreadyRetried = err.requestOptions.extra['authRetry'] == true;
    final isAuthCall = err.requestOptions.uri.toString().contains('/auth/');
    if (err.response?.statusCode != 401 || alreadyRetried || isAuthCall) {
      handler.next(err);
      return;
    }

    final token = await _client.refreshAccessToken();
    if (token == null) {
      handler.next(err);
      return;
    }

    try {
      final request = err.requestOptions;
      request.extra['authRetry'] = true;
      request.headers['Authorization'] = 'Bearer $token';
      final response = await _client.dio.fetch<dynamic>(request);
      handler.resolve(response);
    } on DioException catch (retryError) {
      handler.next(retryError);
    }
  }
}

String? _serverDetail(dynamic data) {
  if (data is Map<String, dynamic>) {
    final detail = data['detail'];
    if (detail != null) return detail.toString();
  }
  return null;
}
