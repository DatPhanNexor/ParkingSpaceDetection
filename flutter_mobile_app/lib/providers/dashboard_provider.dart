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
      knownCount == 0 ? 0 : (occupiedCount / knownCount) * 100;

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

  @override
  SlotsState build() {
    ref.onDispose(() {
      final sub = _wsSub;
      if (sub != null) unawaited(sub.cancel());
    });
    return SlotsState(slots: _unknownSlots());
  }

  Future<void> fetch({bool silent = false}) async {
    if (!silent) {
      state = state.copyWith(isLoading: true, error: null);
    }
    try {
      final slots = await ref.read(parkingRepositoryProvider).getSlots();
      state = SlotsState(slots: slots, lastUpdated: DateTime.now());
    } catch (error) {
      state = state.copyWith(
        isLoading: false,
        error: error.toString(),
        isStale: state.lastUpdated != null,
      );
    }
  }

  void listenToWebSocket() {
    _wsSub?.cancel();
    _wsSub = ref.read(wsServiceProvider).messages.listen((_) {
      unawaited(fetch(silent: true));
    });
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
  @override
  SessionsState build() => const SessionsState();

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

  const ReportState({
    this.summary,
    this.revenue = const <Map<String, dynamic>>[],
    this.frequency = const <Map<String, dynamic>>[],
    this.isLoading = false,
    this.error,
    this.lastUpdated,
  });

  ReportState copyWith({
    Map<String, dynamic>? summary,
    List<Map<String, dynamic>>? revenue,
    List<Map<String, dynamic>>? frequency,
    bool? isLoading,
    Object? error = _unset,
    DateTime? lastUpdated,
  }) {
    return ReportState(
      summary: summary ?? this.summary,
      revenue: revenue ?? this.revenue,
      frequency: frequency ?? this.frequency,
      isLoading: isLoading ?? this.isLoading,
      error: identical(error, _unset) ? this.error : error as String?,
      lastUpdated: lastUpdated ?? this.lastUpdated,
    );
  }
}

class ReportNotifier extends Notifier<ReportState> {
  @override
  ReportState build() => const ReportState();

  Future<void> fetchAll({bool silent = false}) async {
    if (!silent) state = state.copyWith(isLoading: true, error: null);
    try {
      final repo = ref.read(reportingRepositoryProvider);
      final results = await Future.wait<dynamic>([
        repo.getSummary(),
        repo.getRevenue(),
        repo.getFrequency(),
      ]);
      state = ReportState(
        summary: results[0] as Map<String, dynamic>,
        revenue: results[1] as List<Map<String, dynamic>>,
        frequency: results[2] as List<Map<String, dynamic>>,
        lastUpdated: DateTime.now(),
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
