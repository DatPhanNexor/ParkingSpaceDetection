import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:smart_parking_app/main.dart';
import 'package:smart_parking_app/models/slot_model.dart';
import 'package:smart_parking_app/models/user_model.dart';
import 'package:smart_parking_app/repositories/auth_repository.dart';
import 'package:smart_parking_app/widgets/slot_grid.dart';

class FakeAuthRepository implements AuthRepository {
  final User? restoredUser;

  FakeAuthRepository({this.restoredUser});

  @override
  Future<User?> tryRestoreSession() async => restoredUser;

  @override
  Future<User> login(String username, String password) async {
    return User(
      id: 1,
      username: username,
      displayName: 'Demo User',
      role: 'staff',
      isActive: true,
    );
  }

  @override
  Future<void> logout() async {}

  @override
  Future<User> getProfile() async => restoredUser!;

  @override
  Future<bool> hasStoredToken() async => restoredUser != null;

  @override
  Future<String?> getToken() async => 'test-token';
}

void main() {
  testWidgets('shows polished login when no saved session', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authRepositoryProvider.overrideWithValue(FakeAuthRepository()),
        ],
        child: const SmartParkingApp(),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('Smart Parking AI'), findsOneWidget);
    expect(find.text('Đăng nhập hệ thống'), findsOneWidget);
    expect(find.text('Tên đăng nhập'), findsOneWidget);
    expect(find.text('Mật khẩu'), findsOneWidget);
  });

  testWidgets('slot grid renders all 9 canonical parking slots', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Padding(
            padding: const EdgeInsets.all(16),
            child: SlotGrid(
              slots: [
                const Slot(id: 'S01', status: 'EMPTY'),
                const Slot(id: 'S05', status: 'OCCUPIED'),
              ],
            ),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('S01'), findsWidgets);
    expect(find.text('S09'), findsWidgets);
    expect(find.text('Đang có xe'), findsOneWidget);
  });
}
