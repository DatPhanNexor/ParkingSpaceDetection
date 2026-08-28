import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/slot_model.dart';
import '../providers/dashboard_provider.dart';

class SlotGrid extends ConsumerWidget {
  const SlotGrid({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final slotsAsyncValue = ref.watch(slotsProvider);

    return slotsAsyncValue.when(
      data: (slots) {
        return GridView.builder(
          padding: const EdgeInsets.all(16),
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 3,
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
          ),
          itemCount: 9,
          itemBuilder: (context, index) {
            final slotId = 'S0${index + 1}';
            final slotData = slots.firstWhere(
              (s) => s.id == slotId,
              orElse: () => Slot(id: slotId, status: 'UNKNOWN')
            );

            Color color = Colors.grey;
            if (slotData.status == 'EMPTY') color = Colors.green;
            if (slotData.status == 'OCCUPIED') color = Colors.red;

            return Card(
              color: color,
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(slotId, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Colors.white)),
                    Text(slotData.status, style: const TextStyle(color: Colors.white)),
                  ],
                ),
              ),
            );
          },
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (err, stack) => Center(child: Text('Error: $err')),
    );
  }
}
