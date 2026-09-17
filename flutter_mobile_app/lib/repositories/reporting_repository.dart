import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/constants.dart';
import '../models/alert_model.dart';
import '../services/api_client.dart';
import 'auth_repository.dart';

final reportingRepositoryProvider = Provider<ReportingRepository>((ref) {
  return ReportingRepository(ref.read(apiClientProvider));
});

class ReportingRepository {
  final ApiClient _client;

  ReportingRepository(this._client);

  Future<Map<String, dynamic>> getSummary() async {
    try {
      final response = await _client.dio.get<Map<String, dynamic>>(
        AppConstants.reportSummaryUrl,
      );
      return response.data ?? <String, dynamic>{};
    } on DioException catch (error) {
      throw ApiFailure.fromDio(error);
    }
  }

  Future<List<Map<String, dynamic>>> getRevenue() async {
    return _getMapList(AppConstants.reportRevenueUrl);
  }

  Future<List<Map<String, dynamic>>> getFrequency() async {
    return _getMapList(AppConstants.reportFrequencyUrl);
  }

  Future<List<Alert>> getAlerts() async {
    try {
      final response = await _client.dio.get<dynamic>(AppConstants.alertsUrl);
      final data = response.data;
      if (data is List<dynamic>) {
        return data
            .whereType<Map<String, dynamic>>()
            .map(Alert.fromJson)
            .toList();
      }
      return const <Alert>[];
    } on DioException catch (error) {
      throw ApiFailure.fromDio(error);
    }
  }

  Future<List<Map<String, dynamic>>> _getMapList(String url) async {
    try {
      final response = await _client.dio.get<dynamic>(url);
      final data = response.data;
      if (data is List<dynamic>) {
        return data.whereType<Map<String, dynamic>>().toList();
      }
      return const <Map<String, dynamic>>[];
    } on DioException catch (error) {
      throw ApiFailure.fromDio(error);
    }
  }
}
