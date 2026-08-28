import '../services/api_client.dart';
import '../core/constants.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final apiClientProvider = Provider((ref) => ApiClient());
final authRepositoryProvider = Provider((ref) => AuthRepository(ref.read(apiClientProvider)));

class AuthRepository {
  final ApiClient _apiClient;

  AuthRepository(this._apiClient);

  Future<bool> login(String username, String password) async {
    try {
      final response = await _apiClient.dio.post('${AppConstants.authBaseUrl}/auth/login', data: {
        'username': username,
        'password': password,
      });
      if (response.statusCode == 200) {
        await _apiClient.storage.write(key: 'access_token', value: response.data['access_token']);
        await _apiClient.storage.write(key: 'refresh_token', value: response.data['refresh_token']);
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  Future<void> logout() async {
    final refreshToken = await _apiClient.storage.read(key: 'refresh_token');
    if (refreshToken != null) {
      try {
        await _apiClient.dio.post('${AppConstants.authBaseUrl}/auth/logout', data: {'refresh_token': refreshToken});
      } catch (_) {}
    }
    await _apiClient.storage.delete(key: 'access_token');
    await _apiClient.storage.delete(key: 'refresh_token');
  }
}
