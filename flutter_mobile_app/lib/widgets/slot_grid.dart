import 'package:flutter/material.dart';

import '../core/constants.dart';
import '../core/theme.dart';
import '../models/slot_model.dart';

class SlotGrid extends StatelessWidget {
  final List<Slot> slots;
  final ValueChanged<Slot>? onTap;
  final bool stale;

  const SlotGrid({
    super.key,
    required this.slots,
    this.onTap,
    this.stale = false,
  });

  @override
  Widget build(BuildContext context) {
    final byId = {for (final slot in slots) slot.id: slot};
    final normalized = [
      for (final id in AppConstants.slotIds) byId[id] ?? Slot.unknown(id),
    ];

    return LayoutBuilder(
      builder: (context, constraints) {
        final gap = constraints.maxWidth < 380 ? 8.0 : 10.0;
        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          padding: EdgeInsets.zero,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 3,
            crossAxisSpacing: gap,
            mainAxisSpacing: gap,
            childAspectRatio: 0.88,
          ),
          itemCount: normalized.length,
          itemBuilder: (context, index) {
            final slot = normalized[index];
            return _SlotCard(
              slot: slot,
              stale: stale,
              onTap: onTap == null ? null : () => onTap!(slot),
            );
          },
        );
      },
    );
  }
}

class _SlotCard extends StatelessWidget {
  final Slot slot;
  final bool stale;
  final VoidCallback? onTap;

  const _SlotCard({
    required this.slot,
    required this.stale,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.statusColor(slot.status);
    final bg = AppTheme.statusBg(slot.status);
    final occupied = slot.isOccupied;

    return Semantics(
      button: onTap != null,
      label: '${slot.id} ${AppTheme.statusLabel(slot.status)}',
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOut,
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: stale ? AppTheme.cardLight : bg,
            borderRadius: BorderRadius.circular(AppTheme.radiusMd),
            border: Border.all(
              color: color.withValues(alpha: 0.45),
              width: 1.4,
            ),
            boxShadow: [
              if (occupied)
                BoxShadow(
                  color: color.withValues(alpha: 0.18),
                  blurRadius: 14,
                  offset: const Offset(0, 6),
                ),
            ],
          ),
          child: CustomPaint(
            painter: _ParkingBayPainter(color: color, occupied: occupied),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(AppTheme.statusIcon(slot.status), color: color, size: 24),
                const SizedBox(height: 8),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(
                    slot.id,
                    style: const TextStyle(
                      color: AppTheme.textPrimary,
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(height: 5),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 7,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.14),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      AppTheme.statusLabel(slot.status),
                      style: TextStyle(
                        color: color,
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ParkingBayPainter extends CustomPainter {
  final Color color;
  final bool occupied;

  _ParkingBayPainter({required this.color, required this.occupied});

  @override
  void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = color.withValues(alpha: 0.16)
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;
    final rect = Rect.fromLTWH(7, 7, size.width - 14, size.height - 14);
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(9)),
      line,
    );
    canvas.drawLine(
      Offset(rect.left + rect.width * 0.20, rect.bottom),
      Offset(rect.left + rect.width * 0.20, rect.top + rect.height * 0.62),
      line,
    );
    canvas.drawLine(
      Offset(rect.right - rect.width * 0.20, rect.bottom),
      Offset(rect.right - rect.width * 0.20, rect.top + rect.height * 0.62),
      line,
    );
    if (!occupied) return;

    final carRect = Rect.fromCenter(
      center: Offset(size.width / 2, size.height * 0.44),
      width: size.width * 0.32,
      height: size.height * 0.20,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(carRect, Radius.circular(size.width * 0.07)),
      Paint()..color = Colors.white.withValues(alpha: 0.10),
    );
  }

  @override
  bool shouldRepaint(covariant _ParkingBayPainter oldDelegate) {
    return oldDelegate.color != color || oldDelegate.occupied != occupied;
  }
}
