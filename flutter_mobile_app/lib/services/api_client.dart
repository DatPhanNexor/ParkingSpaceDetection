import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../core/constants.dart';

class ApiClient {
  final Dio dio = Dio();
  final FlutterSecureStorage storage = const FlutterSecureStorage();

  ApiClient() {
    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await storage.read(key: 'access_token');
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        return handler.next(options);
      },
      onError: (DioException e, handler) async {
        if (e.response?.statusCode == 401) {
          final refreshToken = await storage.read(key: 'refresh_token');
          if (refreshToken != null) {
            try {
              final response = await Dio().post(
                '${AppConstants.authBaseUrl}/auth/refresh',
                data: {'refresh_token': refreshToken},
              );
              if (response.statusCode == 200) {
                final newAccessToken = response.data['access_token'];
                final newRefreshToken = response.data['refresh_token'];
                await storage.write(key: 'access_token', value: newAccessToken);
                await storage.write(key: 'refresh_token', value: newRefreshToken);

                e.requestOptions.headers['Authorization'] = 'Bearer $newAccessToken';
                final cloneReq = await Dio().fetch(e.requestOptions);
                return handler.resolve(cloneReq);
              }
            } catch (err) {
              await storage.deleteAll();
            }
          }
        }
        return handler.next(e);
      }
    ));
  }
}
