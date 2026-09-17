import 'package:flutter_test/flutter_test.dart';
import 'package:smart_parking_app/models/slot_model.dart';
import 'package:smart_parking_app/models/session_model.dart';
import 'package:smart_parking_app/utils/helpers.dart';

void main() {
  test('slot parser preserves UNKNOWN instead of inventing EMPTY', () {
    final slot = Slot.fromJson({'slot_id': 'S01', 'status': 'UNKNOWN'});

    expect(slot.id, 'S01');
    expect(slot.status, 'UNKNOWN');
    expect(slot.isKnown, isFalse);
  });

  test('history parser reads backend gio_vao gio_ra and decimal fee', () {
    final session = ParkingSession.fromJson({
      'transaction_id': 'tx-1',
      'slot_id': 'S03',
      'gio_vao': '2026-09-09T07:00:00',
      'gio_ra': '2026-09-09T08:15:00',
      'thanh_tien': '25000.00',
    });

    expect(session.id, 'tx-1');
    expect(session.slotId, 'S03');
    expect(session.displayDuration.inMinutes, 75);
    expect(session.feeVnd, 25000);
  });

  test('Vietnamese currency format is compact', () {
    expect(formatCurrency(450000), '450.000₫');
    expect(formatCurrency(null), 'Chưa có');
  });
}
