class AppConstants {
  AppConstants._();

  static const String appName = 'Smart Parking AI';
  static const String appSubtitle = 'Giám sát bãi đỗ xe theo thời gian thực';
  static const int totalSlots = 9;
  static const List<String> slotIds = <String>[
    'S01',
    'S02',
    'S03',
    'S04',
    'S05',
    'S06',
    'S07',
    'S08',
    'S09',
  ];

  static const String authBaseUrl = String.fromEnvironment(
    'AUTH_BASE_URL',
    defaultValue: 'http://10.0.2.2:8001/api/v1',
  );

  static const String reportingBaseUrl = String.fromEnvironment(
    'REPORTING_BASE_URL',
    defaultValue: 'http://10.0.2.2:8004/api/v1',
  );

  static const String websocketUrl = String.fromEnvironment(
    'WEBSOCKET_URL',
    defaultValue: 'ws://10.0.2.2:8004/ws/parking',
  );

  static String get loginUrl => '$authBaseUrl/auth/login';
  static String get refreshUrl => '$authBaseUrl/auth/refresh';
  static String get logoutUrl => '$authBaseUrl/auth/logout';
  static String get profileUrl => '$authBaseUrl/auth/me';

  static String get slotsUrl => '$reportingBaseUrl/slots';
  static String get activeSessionsUrl => '$reportingBaseUrl/sessions/active';
  static String get sessionHistoryUrl => '$reportingBaseUrl/sessions/history';
  static String get alertsUrl => '$reportingBaseUrl/alerts';

  static String get reportSummaryUrl => '$reportingBaseUrl/reports/summary';
  static String get reportRevenueUrl => '$reportingBaseUrl/reports/revenue';
  static String get reportFrequencyUrl => '$reportingBaseUrl/reports/frequency';

  static const Duration httpTimeout = Duration(seconds: 15);
  static const Duration restSnapshotInterval = Duration(seconds: 15);
  static const Duration wsReconnectBase = Duration(seconds: 2);
  static const Duration wsReconnectMax = Duration(seconds: 30);
}
