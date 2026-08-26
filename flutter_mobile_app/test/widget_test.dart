import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:smart_parking_app/main.dart';

void main() {
  testWidgets('App loads and shows Login screen', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: SmartParkingApp()));
    await tester.pumpAndSettle();

    expect(find.text('Login'), findsWidgets);
    expect(find.text('Username'), findsWidgets);
    expect(find.text('Password'), findsWidgets);
  });
}
