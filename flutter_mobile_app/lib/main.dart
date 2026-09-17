import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/constants.dart';
import 'core/theme.dart';
import 'repositories/auth_repository.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'widgets/parking_brand.dart';
import 'widgets/ui_state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: AppTheme.navy,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  runApp(const ProviderScope(child: SmartParkingApp()));
}

class SmartParkingApp extends ConsumerWidget {
  const SmartParkingApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: AppConstants.appName,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const _AuthGate(),
    );
  }
}

class _AuthGate extends ConsumerWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authStateProvider);
    return auth.when(
      data: (user) =>
          user == null ? const LoginScreen() : HomeScreen(user: user),
      loading: () => const _StartupScreen(),
      error: (error, stackTrace) => UiState(
        loading: false,
        icon: Icons.lock_reset,
        title: 'Không khôi phục được phiên',
        message: 'Vui lòng đăng nhập lại để tiếp tục giám sát bãi xe.',
        onRetry: () => ref.read(authStateProvider.notifier).retryRestore(),
      ),
    );
  }
}

class _StartupScreen extends StatelessWidget {
  const _StartupScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: AppTheme.navy,
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ParkingBrand(size: 104),
              SizedBox(height: 28),
              CircularProgressIndicator(strokeWidth: 2.4),
              SizedBox(height: 16),
              Text(
                'Đang kiểm tra phiên đăng nhập',
                style: TextStyle(color: AppTheme.textSecondary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
