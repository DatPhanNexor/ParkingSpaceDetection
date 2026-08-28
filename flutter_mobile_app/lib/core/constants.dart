class AppConstants {
  static const String authBaseUrl = String.fromEnvironment('AUTH_BASE_URL', defaultValue: 'http://10.0.2.2:8001/api/v1');
  static const String reportingBaseUrl = String.fromEnvironment('REPORTING_BASE_URL', defaultValue: 'http://10.0.2.2:8004/api/v1');
  static const String wsBaseUrl = String.fromEnvironment('WS_BASE_URL', defaultValue: 'ws://10.0.2.2:8004/ws/parking');
}
