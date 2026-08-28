import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:async';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../core/constants.dart';
import '../repositories/auth_repository.dart';
import '../providers/dashboard_provider.dart';
import 'login_screen.dart';
import '../widgets/slot_grid.dart';
import '../repositories/reporting_repository.dart';
import '../models/session_model.dart';
import '../models/history_model.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  int _selectedIndex = 0;
  WebSocketChannel? _channel;
  Timer? _reconnectTimer;

  @override
  void initState() {
    super.initState();
    _connectWebSocket();
  }

  @override
  void dispose() {
    _channel?.sink.close();
    _reconnectTimer?.cancel();
    super.dispose();
  }

  Future<void> _connectWebSocket() async {
    final token = await ref.read(apiClientProvider).storage.read(key: 'access_token');
    if (token == null) return;

    final wsUrl = Uri.parse('${AppConstants.wsBaseUrl}?token=$token');

    try {
      _channel = WebSocketChannel.connect(wsUrl);
      _channel!.stream.listen(
        (message) {
          ref.refresh(slotsProvider);
          ref.refresh(summaryProvider);
        },
        onDone: _scheduleReconnect,
        onError: (error) => _scheduleReconnect(),
      );
    } catch (e) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 5), _connectWebSocket);
  }

  void _logout() async {
    await ref.read(authRepositoryProvider).logout();
    if (!mounted) return;
    Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const LoginScreen()));
  }

  Widget _buildActiveSessions() {
    return FutureBuilder<List<Session>>(
      future: ref.read(reportingRepositoryProvider).getActiveSessions(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) return const Center(child: CircularProgressIndicator());
        if (!snapshot.hasData || snapshot.data!.isEmpty) return const Center(child: Text("No active sessions"));

        return ListView.builder(
          itemCount: snapshot.data!.length,
          itemBuilder: (context, index) {
            final session = snapshot.data![index];
            return ListTile(
              title: Text('Slot: ${session.slotId}'),
              subtitle: Text('Started: ${session.startedAt}'),
            );
          },
        );
      },
    );
  }

  Widget _buildHistory() {
    return FutureBuilder<List<History>>(
      future: ref.read(reportingRepositoryProvider).getHistory(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) return const Center(child: CircularProgressIndicator());
        if (!snapshot.hasData || snapshot.data!.isEmpty) return const Center(child: Text("No history"));

        return ListView.builder(
          itemCount: snapshot.data!.length,
          itemBuilder: (context, index) {
            final history = snapshot.data![index];
            return ListTile(
              title: Text('Slot: ${history.slotId}'),
              subtitle: Text('Fee: ${history.fee} VND'),
              trailing: Text(history.endedAt),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final List<Widget> pages = [
      RefreshIndicator(
        onRefresh: () async {
          ref.refresh(slotsProvider);
          ref.refresh(summaryProvider);
        },
        child: Column(
          children: [
            Consumer(
              builder: (context, ref, child) {
                final summary = ref.watch(summaryProvider);
                return summary.when(
                  data: (data) => Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Text('Revenue: ${data["total_revenue"]} VND | Active: ${data["active_sessions"]}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  ),
                  loading: () => const SizedBox.shrink(),
                  error: (_, __) => const SizedBox.shrink(),
                );
              },
            ),
            const Expanded(child: SlotGrid()),
          ],
        ),
      ),
      _buildActiveSessions(),
      _buildHistory(),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Smart Parking'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: () {
            ref.refresh(slotsProvider);
            ref.refresh(summaryProvider);
            setState(() {});
          }),
          IconButton(icon: const Icon(Icons.logout), onPressed: _logout),
        ],
      ),
      body: pages[_selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (index) => setState(() => _selectedIndex = index),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard), label: 'Dashboard'),
          BottomNavigationBarItem(icon: Icon(Icons.car_rental), label: 'Active'),
          BottomNavigationBarItem(icon: Icon(Icons.history), label: 'History'),
        ],
      ),
    );
  }
}
