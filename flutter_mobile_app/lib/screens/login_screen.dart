import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/constants.dart';
import '../core/theme.dart';
import '../repositories/auth_repository.dart';
import '../services/api_client.dart';
import '../widgets/parking_brand.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen>
    with SingleTickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  late final AnimationController _fadeController;
  late final Animation<double> _fade;
  bool _obscurePassword = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 520),
    )..forward();
    _fade = CurvedAnimation(parent: _fadeController, curve: Curves.easeOut);
    _usernameController.addListener(_refreshButton);
    _passwordController.addListener(_refreshButton);
  }

  void _refreshButton() => setState(() {});

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _fadeController.dispose();
    super.dispose();
  }

  bool get _canSubmit =>
      _usernameController.text.trim().isNotEmpty &&
      _passwordController.text.isNotEmpty &&
      !ref.watch(authStateProvider).isLoading;

  Future<void> _login() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _errorMessage = null);
    try {
      await ref
          .read(authStateProvider.notifier)
          .login(_usernameController.text.trim(), _passwordController.text);
    } on ApiFailure catch (error) {
      if (mounted) setState(() => _errorMessage = _messageFor(error));
    } catch (_) {
      if (mounted) {
        setState(
          () => _errorMessage =
              'Không thể đăng nhập. Kiểm tra backend hoặc kết nối mạng.',
        );
      }
    }
  }

  String _messageFor(ApiFailure error) {
    if (error.statusCode == 401) {
      return 'Tên đăng nhập hoặc mật khẩu không đúng.';
    }
    if (error.statusCode == 403) {
      return 'Tài khoản đã bị vô hiệu hóa hoặc không có quyền truy cập.';
    }
    return error.message;
  }

  @override
  Widget build(BuildContext context) {
    final loading = ref.watch(authStateProvider).isLoading;
    return Scaffold(
      backgroundColor: AppTheme.navy,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
            child: FadeTransition(
              opacity: _fade,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 460),
                child: Form(
                  key: _formKey,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Center(child: ParkingBrand(size: 116)),
                      const SizedBox(height: 18),
                      const Text(
                        AppConstants.appName,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: AppTheme.textPrimary,
                          fontSize: 28,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        AppConstants.appSubtitle,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: AppTheme.textSecondary,
                          fontSize: 14,
                          height: 1.35,
                        ),
                      ),
                      const SizedBox(height: 28),
                      _buildPanel(loading),
                      const SizedBox(height: 18),
                      Text(
                        'REST + WebSocket qua backend microservices',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: AppTheme.textSecondary.withValues(alpha: 0.72),
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildPanel(bool loading) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.card.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
        border: Border.all(color: AppTheme.border),
        boxShadow: [
          BoxShadow(
            color: AppTheme.cyan.withValues(alpha: 0.08),
            blurRadius: 28,
            offset: const Offset(0, 16),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Đăng nhập hệ thống',
            style: TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Dùng tài khoản admin hoặc staff từ Auth Service.',
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 13),
          ),
          if (_errorMessage != null) ...[
            const SizedBox(height: 16),
            _ErrorBanner(message: _errorMessage!),
          ],
          const SizedBox(height: 18),
          TextFormField(
            controller: _usernameController,
            enabled: !loading,
            style: const TextStyle(color: AppTheme.textPrimary),
            decoration: const InputDecoration(
              labelText: 'Tên đăng nhập',
              prefixIcon: Icon(Icons.person_outline),
            ),
            textInputAction: TextInputAction.next,
            validator: (value) => value == null || value.trim().isEmpty
                ? 'Nhập tên đăng nhập'
                : null,
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _passwordController,
            enabled: !loading,
            obscureText: _obscurePassword,
            style: const TextStyle(color: AppTheme.textPrimary),
            decoration: InputDecoration(
              labelText: 'Mật khẩu',
              prefixIcon: const Icon(Icons.lock_outline),
              suffixIcon: IconButton(
                tooltip: _obscurePassword ? 'Hiện mật khẩu' : 'Ẩn mật khẩu',
                onPressed: loading
                    ? null
                    : () =>
                          setState(() => _obscurePassword = !_obscurePassword),
                icon: Icon(
                  _obscurePassword ? Icons.visibility_off : Icons.visibility,
                ),
              ),
            ),
            onFieldSubmitted: (_) {
              if (_canSubmit) _login();
            },
            validator: (value) =>
                value == null || value.isEmpty ? 'Nhập mật khẩu' : null,
          ),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: _canSubmit ? _login : null,
            icon: loading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.login),
            label: Text(loading ? 'Đang đăng nhập' : 'Đăng nhập'),
          ),
        ],
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  final String message;

  const _ErrorBanner({required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.redBg,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        border: Border.all(color: AppTheme.red.withValues(alpha: 0.35)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline, color: AppTheme.red, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: AppTheme.textPrimary, height: 1.3),
            ),
          ),
        ],
      ),
    );
  }
}
