import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/constants.dart';
import '../models/user_model.dart';
import '../services/api_client.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(ref.read(apiClientProvider));
});

final authStateProvider = AsyncNotifierProvider<AuthController, User?>(
  AuthController.new,
);

class AuthRepository {
  final ApiClient _client;

  AuthRepository(this._client);

  Future<User> login(String username, String password) async {
    try {
      final response = await _client.dio.post<Map<String, dynamic>>(
        AppConstants.loginUrl,
        data: {'username': username.trim(), 'password': password},
      );
      final data = response.data ?? <String, dynamic>{};
      final accessToken = data['access_token']?.toString();
      final refreshToken = data['refresh_token']?.toString();
      if (accessToken == null || accessToken.isEmpty) {
        throw const ApiFailure('Máy chủ không trả access token.');
      }
      await _client.saveTokens(
        accessToken: accessToken,
        refreshToken: refreshToken,
      );
      return getProfile();
    } on DioException catch (error) {
      throw ApiFailure.fromDio(error);
    }
  }

  Future<User> getProfile() async {
    try {
      final response = await _client.dio.get<Map<String, dynamic>>(
        AppConstants.profileUrl,
      );
      return User.fromJson(response.data ?? <String, dynamic>{});
    } on DioException catch (error) {
      throw ApiFailure.fromDio(error);
    }
  }

  Future<void> logout() async {
    final token = await _client.refreshToken;
    try {
      if (token != null && token.isNotEmpty) {
        await _client.dio.post<void>(
          AppConstants.logoutUrl,
          data: {'refresh_token': token},
        );
      }
    } on DioException {
      // Logout is best-effort; local tokens are cleared below.
    } finally {
      await _client.clearTokens();
    }
  }

  Future<bool> hasStoredToken() => _client.hasToken;

  Future<User?> tryRestoreSession() async {
    if (!await _client.hasToken) return null;
    try {
      return await getProfile();
    } on ApiFailure catch (error) {
      if (error.statusCode == 401) {
        final refreshed = await _client.refreshAccessToken();
        if (refreshed != null) {
          try {
            return await getProfile();
          } on ApiFailure {
            await _client.clearTokens();
            return null;
          }
        }
      }
      await _client.clearTokens();
      return null;
    }
  }

  Future<String?> getToken() => _client.accessToken;
}

class AuthController extends AsyncNotifier<User?> {
  @override
  Future<User?> build() {
    return ref.read(authRepositoryProvider).tryRestoreSession();
  }

  Future<void> login(String username, String password) async {
    state = const AsyncValue.loading();
    try {
      final user = await ref
          .read(authRepositoryProvider)
          .login(username, password);
      state = AsyncValue.data(user);
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
      Error.throwWithStackTrace(error, stackTrace);
    }
  }

  Future<void> logout() async {
    await ref.read(authRepositoryProvider).logout();
    state = const AsyncValue.data(null);
  }

  Future<void> retryRestore() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(
      () => ref.read(authRepositoryProvider).tryRestoreSession(),
    );
  }
}
