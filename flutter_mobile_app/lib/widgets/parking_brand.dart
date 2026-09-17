import 'package:flutter/material.dart';

import '../core/theme.dart';

class ParkingBrand extends StatelessWidget {
  final double size;

  const ParkingBrand({super.key, this.size = 64});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Logo Smart Parking AI',
      child: SizedBox(
        width: size,
        height: size,
        child: DecoratedBox(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(size * 0.24),
            boxShadow: [
              BoxShadow(
                color: AppTheme.cyan.withValues(alpha: 0.18),
                blurRadius: size * 0.16,
                offset: Offset(0, size * 0.06),
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(size * 0.24),
            child: Image.asset(
              'branding/parking_logo_3d.png',
              width: size,
              height: size,
              fit: BoxFit.contain,
              filterQuality: FilterQuality.high,
              errorBuilder: (context, error, stackTrace) {
                return CustomPaint(painter: _ParkingBrandPainter());
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _ParkingBrandPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final radius = Radius.circular(size.width * 0.22);
    final background = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [AppTheme.cardLight, AppTheme.surface],
      ).createShader(rect);

    canvas.drawRRect(RRect.fromRectAndRadius(rect, radius), background);

    final glow = Paint()
      ..color = AppTheme.cyan.withValues(alpha: 0.22)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * 0.10);
    canvas.drawCircle(
      Offset(size.width * 0.70, size.height * 0.28),
      size.width * 0.28,
      glow,
    );

    final border = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.width * 0.035
      ..color = AppTheme.cyan.withValues(alpha: 0.75);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        rect.deflate(size.width * 0.045),
        Radius.circular(size.width * 0.18),
      ),
      border,
    );

    final pPaint = Paint()
      ..shader = const LinearGradient(
        colors: [AppTheme.cyan, AppTheme.accentLight],
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
      ).createShader(rect)
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.width * 0.115;

    final path = Path()
      ..moveTo(size.width * 0.32, size.height * 0.72)
      ..lineTo(size.width * 0.32, size.height * 0.28)
      ..quadraticBezierTo(
        size.width * 0.61,
        size.height * 0.20,
        size.width * 0.67,
        size.height * 0.38,
      )
      ..quadraticBezierTo(
        size.width * 0.73,
        size.height * 0.56,
        size.width * 0.45,
        size.height * 0.55,
      );
    canvas.drawPath(path, pPaint);

    final slotPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.78)
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.width * 0.025
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(
      Offset(size.width * 0.55, size.height * 0.68),
      Offset(size.width * 0.76, size.height * 0.68),
      slotPaint,
    );
    canvas.drawLine(
      Offset(size.width * 0.55, size.height * 0.78),
      Offset(size.width * 0.76, size.height * 0.78),
      slotPaint,
    );

    final car = RRect.fromRectAndRadius(
      Rect.fromCenter(
        center: Offset(size.width * 0.66, size.height * 0.73),
        width: size.width * 0.18,
        height: size.height * 0.10,
      ),
      Radius.circular(size.width * 0.05),
    );
    canvas.drawRRect(
      car,
      Paint()
        ..shader = const LinearGradient(
          colors: [Colors.white, AppTheme.cyan],
        ).createShader(car.outerRect),
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
