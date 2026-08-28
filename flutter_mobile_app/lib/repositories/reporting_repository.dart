import '../services/api_client.dart';
import '../core/constants.dart';
import '../models/slot_model.dart';
import '../models/session_model.dart';
import '../models/history_model.dart';
import '../models/alert_model.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'auth_repository.dart';

final reportingRepositoryProvider = Provider((ref) => ReportingRepository(ref.read(apiClientProvider)));

class ReportingRepository {
  final ApiClient _apiClient;

  ReportingRepository(this._apiClient);

  Future<List<Slot>> getSlots() async {
    final response = await _apiClient.dio.get('${AppConstants.reportingBaseUrl}/slots');
    return (response.data as List).map((e) => Slot.fromJson(e)).toList();
  }

  Future<List<Session>> getActiveSessions() async {
    final response = await _apiClient.dio.get('${AppConstants.reportingBaseUrl}/sessions/active');
    return (response.data as List).map((e) => Session.fromJson(e)).toList();
  }

  Future<List<History>> getHistory() async {
    final response = await _apiClient.dio.get('${AppConstants.reportingBaseUrl}/sessions/history');
    return (response.data as List).map((e) => History.fromJson(e)).toList();
  }

  Future<List<Alert>> getAlerts() async {
    final response = await _apiClient.dio.get('${AppConstants.reportingBaseUrl}/alerts');
    return (response.data as List).map((e) => Alert.fromJson(e)).toList();
  }

  Future<Map<String, dynamic>> getSummary() async {
    final response = await _apiClient.dio.get('${AppConstants.reportingBaseUrl}/reports/summary');
    return response.data;
  }
}
