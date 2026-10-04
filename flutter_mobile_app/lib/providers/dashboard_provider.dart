import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/constants.dart';
import '../models/alert_model.dart';
import '../models/session_model.dart';
import '../models/slot_model.dart';
import '../repositories/parking_repository.dart';
import '../repositories/reporting_repository.dart';
import '../services/websocket_service.dart';

const Object _unset = Object();

final wsServiceProvider = Provider<WebSocketService>((ref) {
  final service = WebSocketService();
  ref.onDispose(() {
    unawaited(service.dispose());
  });
  return service;
});

final wsConnectionProvider = StreamProvider<WsConnectionState>((ref) async* {
  final service = ref.watch(wsServiceProvider);
  yield service.currentState;
  yield* service.connectionState;
});

class SlotsState {
  final List<Slot> slots;
  final bool isLoading;
  final String? error;
  final DateTime? lastUpdated;
  final bool isStale;

  const SlotsState({
    this.slots = const <Slot>[],
    this.isLoading = false,
    this.error,
    this.lastUpdated,
    this.isStale = false,
  });

  int get totalCount => AppConstants.totalSlots;
  int get knownCount => slots.where((slot) => slot.isKnown).length;
  int get emptyCount => slots.where((slot) => slot.isEmpty).length;
  int get occupiedCount => slots.where((slot) => slot.isOccupied).length;
  int get unknownCount => totalCount - knownCount;
  double get occupancyRate =>
      totalCount == 0 ? 0 : (occupiedCount / totalCount) * 100;

  SlotsState copyWith({
    List<Slot>? slots,
    bool? isLoading,
    Object? error = _unset,
    DateTime? lastUpdated,
    bool? isStale,
  }) {
    return SlotsState(
      slots: slots ?? this.slots,
      isLoading: isLoading ?? this.isLoading,
      error: identical(error, _unset) ? this.error : error as String?,
      lastUpdated: lastUpdated ?? this.lastUpdated,
      isStale: isStale ?? this.isStale,
    );
  }
}

class SlotsNotifier extends Notifier<SlotsState> {
  StreamSubscription<Map<String, dynamic>>? _wsSub;
  StreamSubscription<WsConnectionState>? _connectionSub;
  int _revision = 0;
  int _fetchRequest = 0;

  @override
  SlotsState build() {
    ref.onDispose(() {
      final sub = _wsSub;
      if (sub != null) unawaited(sub.cancel());
      final connectionSub = _connectionSub;
      if (connectionSub != null) unawaited(connectionSub.cancel());
    });
    final service = ref.read(wsServiceProvider);
    _wsSub = service.messages.listen(applyRealtimeMessage);
    _connectionSub = service.connectionState.listen((connection) {
      if (connection == WsConnectionState.disconnected ||
          connection == WsConnectionState.reconnecting ||
          connection == WsConnectionState.paused) {
        state = state.copyWith(slots: _unknownSlots(), isStale: true);
      } else if (connection == WsConnectionState.connected && state.isStale) {
        unawaited(fetch(silent: true));
      }
    });
    return SlotsState(slots: _unknownSlots());
  }

  Future<void> fetch({bool silent = false}) async {
    if (!silent) {
      state = state.copyWith(isLoading: true, error: null);
    }
    final requestRevision = _revision;
    final requestId = ++_fetchRequest;
    try {
      final slots = await ref.read(parkingRepositoryProvider).getSlots();
      // A REST response started before a newer realtime snapshot must not win.
      if (requestRevision != _revision || requestId != _fetchRequest) return;
      _revision++;
      state = SlotsState(slots: slots, lastUpdated: DateTime.now());
    } catch (error) {
      state = state.copyWith(
        isLoading: false,
        error: error.toString(),
        isStale: state.lastUpdated != null,
      );
    }
  }

  void applyRealtimeMessage(Map<String, dynamic> message) {
    final type = message['type']?.toString();
    if (type == 'parking.snapshot' && message['slots'] is List<dynamic>) {
      final slots = ref
          .read(parkingRepositoryProvider)
          .parseSlotsSnapshot(message);
      _revision++;
      state = SlotsState(
        slots: slots,
        lastUpdated: DateTime.now(),
        error: null,
        isStale: false,
      );
      return;
    }

    // Keep compatibility with a single-slot event while snapshots remain the
    // authoritative resync mechanism.
    final raw = message['payload'] is Map<String, dynamic>
        ? message['payload'] as Map<String, dynamic>
        : message;
    if (raw['slot_id'] == null || raw['status'] == null) return;
    final changed = Slot.fromJson(raw);
    if (!AppConstants.slotIds.contains(changed.id)) return;
    final byId = {for (final slot in state.slots) slot.id: slot};
    byId[changed.id] = changed;
    _revision++;
    state = SlotsState(
      slots: [
        for (final id in AppConstants.slotIds) byId[id] ?? Slot.unknown(id),
      ],
      lastUpdated: DateTime.now(),
      isStale: false,
    );
  }
}

final slotsProvider = NotifierProvider<SlotsNotifier, SlotsState>(
  SlotsNotifier.new,
);

class SessionsState {
  final List<ParkingSession> sessions;
  final bool isLoading;
  final String? error;
  final DateTime? lastUpdated;

  const SessionsState({
    this.sessions = const <ParkingSession>[],
    this.isLoading = false,
    this.error,
    this.lastUpdated,
  });

  SessionsState copyWith({
    List<ParkingSession>? sessions,
    bool? isLoading,
    Object? error = _unset,
    DateTime? lastUpdated,
  }) {
    return SessionsState(
      sessions: sessions ?? this.sessions,
      isLoading: isLoading ?? this.isLoading,
      error: identical(error, _unset) ? this.error : error as String?,
      lastUpdated: lastUpdated ?? this.lastUpdated,
    );
  }
}

class ActiveSessionsNotifier extends Notifier<SessionsState> {
  StreamSubscription<Map<String, dynamic>>? _wsSub;

  @override
  SessionsState build() {
    _wsSub = ref.read(wsServiceProvider).messages.listen(applyRealtimeMessage);
    ref.onDispose(() {
      final sub = _wsSub;
      if (sub != null) unawaited(sub.cancel());
    });
    return const SessionsState();
  }

  Future<void> fetch({bool silent = false}) async {
    if (!silent) state = state.copyWith(isLoading: true, error: null);
    try {
      final sessions = await ref
          .read(parkingRepositoryProvider)
          .getActiveSessions();
      state = SessionsState(sessions: sessions, lastUpdated: DateTime.now());
    } catch (error) {
      state = state.copyWith(isLoading: false, error: error.toString());
    }
  }

  void applyRealtimeMessage(Map<String, dynamic> message) {
    if (message['type'] != 'parking.snapshot' ||
        message['active_sessions'] is! List<dynamic>) {
      return;
    }
    final sessions = (message['active_sessions'] as List<dynamic>)
        .whereType<Map<String, dynamic>>()
        .map(ParkingSession.fromJson)
        .toList();
    state = SessionsState(sessions: sessions, lastUpdated: DateTime.now());
  }

  Future<void> deleteSession(String sessionId) async {
    await ref.read(parkingRepositoryProvider).deleteActiveSession(sessionId);
    await fetch(silent: true);
  }

  Future<void> clearAllSessions() async {
    await ref.read(parkingRepositoryProvider).clearAllActiveSessions();
    await fetch(silent: true);
  }
}

final activeSessionsProvider =
    NotifierProvider<ActiveSessionsNotifier, SessionsState>(
      ActiveSessionsNotifier.new,
    );

class HistoryNotifier extends Notifier<SessionsState> {
  @override
  SessionsState build() => const SessionsState();

  Future<void> fetch({bool silent = false}) async {
    if (!silent) state = state.copyWith(isLoading: true, error: null);
    try {
      final sessions = await ref
          .read(parkingRepositoryProvider)
          .getSessionHistory();
      state = SessionsState(sessions: sessions, lastUpdated: DateTime.now());
    } catch (error) {
      state = state.copyWith(isLoading: false, error: error.toString());
    }
  }

  Future<void> deleteSession(String transactionId) async {
    await ref
        .read(parkingRepositoryProvider)
        .deleteHistorySession(transactionId);
    await fetch(silent: true);
  }

  Future<void> deleteBatchSessions(List<String> transactionIds) async {
    await ref
        .read(parkingRepositoryProvider)
        .deleteBatchHistorySessions(transactionIds);
    await fetch(silent: true);
  }
}

final historyProvider = NotifierProvider<HistoryNotifier, SessionsState>(
  HistoryNotifier.new,
);

class AlertsState {
  final List<Alert> alerts;
  final bool isLoading;
  final String? error;
  final DateTime? lastUpdated;

  const AlertsState({
    this.alerts = const <Alert>[],
    this.isLoading = false,
    this.error,
    this.lastUpdated,
  });

  AlertsState copyWith({
    List<Alert>? alerts,
    bool? isLoading,
    Object? error = _unset,
    DateTime? lastUpdated,
  }) {
    return AlertsState(
      alerts: alerts ?? this.alerts,
      isLoading: isLoading ?? this.isLoading,
      error: identical(error, _unset) ? this.error : error as String?,
      lastUpdated: lastUpdated ?? this.lastUpdated,
    );
  }
}

class AlertsNotifier extends Notifier<AlertsState> {
  @override
  AlertsState build() => const AlertsState();

  Future<void> fetch({bool silent = false}) async {
    if (!silent) state = state.copyWith(isLoading: true, error: null);
    try {
      final alerts = await ref.read(reportingRepositoryProvider).getAlerts();
      state = AlertsState(alerts: alerts, lastUpdated: DateTime.now());
    } catch (error) {
      state = state.copyWith(isLoading: false, error: error.toString());
    }
  }
}

final alertsProvider = NotifierProvider<AlertsNotifier, AlertsState>(
  AlertsNotifier.new,
);

class ReportState {
  final Map<String, dynamic>? summary;
  final List<Map<String, dynamic>> revenue;
  final List<Map<String, dynamic>> frequency;
  final bool isLoading;
  final String? error;
  final DateTime? lastUpdated;
  final DateTime? shiftStart;

  const ReportState({
    this.summary,
    this.revenue = const <Map<String, dynamic>>[],
    this.frequency = const <Map<String, dynamic>>[],
    this.isLoading = false,
    this.error,
    this.lastUpdated,
    this.shiftStart,
  });

  ReportState copyWith({
    Map<String, dynamic>? summary,
    List<Map<String, dynamic>>? revenue,
    List<Map<String, dynamic>>? frequency,
    bool? isLoading,
    Object? error = _unset,
    DateTime? lastUpdated,
    DateTime? shiftStart,
  }) {
    return ReportState(
      summary: summary ?? this.summary,
      revenue: revenue ?? this.revenue,
      frequency: frequency ?? this.frequency,
      isLoading: isLoading ?? this.isLoading,
      error: identical(error, _unset) ? this.error : error as String?,
      lastUpdated: lastUpdated ?? this.lastUpdated,
      shiftStart: shiftStart ?? this.shiftStart,
    );
  }
}

class ReportNotifier extends Notifier<ReportState> {
  static const _shiftStartKey = 'report_shift_start';
  final _storage = const FlutterSecureStorage();

  @override
  ReportState build() {
    _initShiftStart();
    return const ReportState();
  }

  bool _isShiftStartInitialized = false;

  Future<void> _initShiftStart() async {
    if (_isShiftStartInitialized) return;
    final val = await _storage.read(key: _shiftStartKey);
    if (val != null) {
      final dt = DateTime.tryParse(val);
      if (dt != null) {
        state = state.copyWith(shiftStart: dt);
      }
    }
    _isShiftStartInitialized = true;
  }

  Future<void> resetShift() async {
    final nowUtc = DateTime.now().toUtc();
    await _storage.write(key: _shiftStartKey, value: nowUtc.toIso8601String());
    state = state.copyWith(shiftStart: nowUtc);
    await fetchAll();
  }

  Future<void> fetchAll({bool silent = false}) async {
    if (!silent) state = state.copyWith(isLoading: true, error: null);
    try {
      if (!_isShiftStartInitialized) {
        await _initShiftStart();
      }
      final repo = ref.read(reportingRepositoryProvider);
      final since = state.shiftStart;
      final results = await Future.wait<dynamic>([
        repo.getSummary(since: since),
        repo.getRevenue(since: since),
        repo.getFrequency(since: since),
      ]);
      state = state.copyWith(
        summary: results[0] as Map<String, dynamic>,
        revenue: results[1] as List<Map<String, dynamic>>,
        frequency: results[2] as List<Map<String, dynamic>>,
        lastUpdated: DateTime.now(),
        isLoading: false,
      );
    } catch (error) {
      state = state.copyWith(isLoading: false, error: error.toString());
    }
  }
}

final reportProvider = NotifierProvider<ReportNotifier, ReportState>(
  ReportNotifier.new,
);

List<Slot> _unknownSlots() {
  return [for (final id in AppConstants.slotIds) Slot.unknown(id)];
}

final filteredActiveSessionsProvider = Provider<SessionsState>((ref) {
  final activeSessionsState = ref.watch(activeSessionsProvider);
  final slotsState = ref.watch(slotsProvider);

  final sessionsMap = {
    for (final s in activeSessionsState.sessions) s.slotId: s,
  };

  final List<ParkingSession> combined = [];
  for (final slot in slotsState.slots) {
    if (slot.isOccupied) {
      if (sessionsMap.containsKey(slot.id)) {
        combined.add(sessionsMap[slot.id]!);
      } else {
        combined.add(
          ParkingSession(
            id: 'pending_${slot.id}',
            slotId: slot.id,
            status: 'pending',
            startTime: DateTime.now(),
          ),
        );
      }
    }
  }

  return activeSessionsState.copyWith(sessions: combined);
});
