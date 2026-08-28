import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/slot_model.dart';
import '../repositories/reporting_repository.dart';

final slotsProvider = FutureProvider<List<Slot>>((ref) async {
  final repository = ref.read(reportingRepositoryProvider);
  return repository.getSlots();
});

final summaryProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final repository = ref.read(reportingRepositoryProvider);
  return repository.getSummary();
});
