import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/constants.dart';
import '../models/session_model.dart';
import '../models/slot_model.dart';
import '../services/api_client.dart';
import 'auth_repository.dart';

final parkingRepositoryProvider = Provider<ParkingRepository>((ref) {
  return ParkingRepository(ref.read(apiClientProvider));
});

class ParkingRepository {
  final ApiClient _client;

  ParkingRepository(this._client);

  Future<List<Slot>> getSlots() async {
    try {
      final response = await _client.dio.get<dynamic>(AppConstants.slotsUrl);
      final raw = _extractList(response.data, listKey: 'slots');
      final parsed = raw
          .whereType<Map<String, dynamic>>()
          .map(Slot.fromJson)
          .where((slot) => AppConstants.slotIds.contains(slot.id))
          .toList();
      return _normalizeSlots(parsed);
    } on DioException catch (error) {
      throw ApiFailure.fromDio(error);
    }
  }

  Future<List<ParkingSession>> getActiveSessions() async {
    try {
      final response = await _client.dio.get<dynamic>(
        AppConstants.activeSessionsUrl,
      );
      final raw = _extractList(response.data, listKey: 'sessions');
      return raw
          .whereType<Map<String, dynamic>>()
          .map(ParkingSession.fromJson)
          .toList();
    } on DioException catch (error) {
      throw ApiFailure.fromDio(error);
    }
  }

  Future<List<ParkingSession>> getSessionHistory() async {
    try {
      final response = await _client.dio.get<dynamic>(
        AppConstants.sessionHistoryUrl,
      );
      final raw = _extractList(response.data, listKey: 'sessions');
      return raw
          .whereType<Map<String, dynamic>>()
          .map(ParkingSession.fromJson)
          .toList();
    } on DioException catch (error) {
      throw ApiFailure.fromDio(error);
    }
  }
}

List<Slot> _normalizeSlots(List<Slot> slots) {
  final byId = {for (final slot in slots) slot.id: slot};
  return [for (final id in AppConstants.slotIds) byId[id] ?? Slot.unknown(id)];
}

List<dynamic> _extractList(dynamic data, {required String listKey}) {
  if (data is List<dynamic>) return data;
  if (data is Map<String, dynamic> && data[listKey] is List<dynamic>) {
    return data[listKey] as List<dynamic>;
  }
  return const <dynamic>[];
}
