import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../core/constants.dart';

enum WsConnectionState {
  disconnected,
  connecting,
  connected,
  reconnecting,
  paused,
}

class WebSocketService {
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  Timer? _reconnectTimer;
  Timer? _pingTimer;
  int _attempts = 0;
  String? _token;
  bool _disposed = false;

  final _stateController = StreamController<WsConnectionState>.broadcast(
    sync: true,
  );
  final _messageController = StreamController<Map<String, dynamic>>.broadcast(
    sync: true,
  );

  WsConnectionState _currentState = WsConnectionState.disconnected;
  DateTime? lastMessageAt;
  DateTime? connectedAt;

  WsConnectionState get currentState => _currentState;
  Stream<WsConnectionState> get connectionState => _stateController.stream;
  Stream<Map<String, dynamic>> get messages => _messageController.stream;

  Future<void> connect(String token) async {
    _token = token;
    _disposed = false;
    await _open();
  }

  Future<void> _open() async {
    if (_disposed || _token == null || _token!.isEmpty) return;
    _setState(
      _attempts == 0
          ? WsConnectionState.connecting
          : WsConnectionState.reconnecting,
    );
    await _subscription?.cancel();
    await _closeChannel();

    try {
      final uri = Uri.parse(
        AppConstants.websocketUrl,
      ).replace(queryParameters: {'token': _token});
      _channel = WebSocketChannel.connect(uri);
      await _channel!.ready.timeout(AppConstants.httpTimeout);
      _attempts = 0;
      connectedAt = DateTime.now();
      _setState(WsConnectionState.connected);
      _startPing();
      _subscription = _channel!.stream.listen(
        _handleMessage,
        onDone: _scheduleReconnect,
        onError: (_) => _scheduleReconnect(),
        cancelOnError: true,
      );
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _handleMessage(dynamic data) {
    if (_messageController.isClosed) return;
    lastMessageAt = DateTime.now();
    if (data is String && data.trim().isNotEmpty) {
      try {
        final decoded = jsonDecode(data);
        if (decoded is Map<String, dynamic>) {
          _messageController.add(decoded);
        } else {
          _messageController.add({'type': 'message', 'payload': decoded});
        }
      } catch (_) {
        _messageController.add({'type': 'text', 'payload': data});
      }
    }
  }

  void _startPing() {
    _pingTimer?.cancel();
    _pingTimer = Timer.periodic(const Duration(seconds: 25), (_) {
      if (_currentState != WsConnectionState.connected) return;
      try {
        _channel?.sink.add(jsonEncode({'type': 'client_ping'}));
      } catch (_) {
        _scheduleReconnect();
      }
    });
  }

  void _scheduleReconnect() {
    if (_disposed || _token == null || _token!.isEmpty) return;
    _pingTimer?.cancel();
    _setState(WsConnectionState.reconnecting);
    _reconnectTimer?.cancel();
    final delay = _nextDelay();
    _attempts++;
    _reconnectTimer = Timer(delay, _open);
  }

  Duration _nextDelay() {
    final base = AppConstants.wsReconnectBase.inMilliseconds;
    final max = AppConstants.wsReconnectMax.inMilliseconds;
    final cappedPower = 1 << min(_attempts, 5);
    final backoff = min(base * cappedPower, max);
    final jitter = Random().nextInt(900);
    return Duration(milliseconds: backoff + jitter);
  }

  Future<void> disconnect({bool paused = false}) async {
    _disposed = true;
    _reconnectTimer?.cancel();
    _pingTimer?.cancel();
    await _subscription?.cancel();
    await _closeChannel();
    _setState(
      paused ? WsConnectionState.paused : WsConnectionState.disconnected,
    );
  }

  Future<void> _closeChannel() async {
    try {
      await _channel?.sink.close();
    } catch (_) {
      // Best effort close.
    } finally {
      _channel = null;
    }
  }

  Future<void> dispose() async {
    await disconnect();
    await _stateController.close();
    await _messageController.close();
  }

  void _setState(WsConnectionState state) {
    _currentState = state;
    if (!_stateController.isClosed) {
      _stateController.add(state);
    }
  }
}
