import 'package:flutter/material.dart';

class AppTheme {
  AppTheme._();

  static const Color navy = Color(0xFF07111F);
  static const Color surface = Color(0xFF0E1A2D);
  static const Color card = Color(0xFF13213A);
  static const Color cardLight = Color(0xFF1A2B49);
  static const Color border = Color(0xFF28405F);
  static const Color textPrimary = Color(0xFFF8FBFF);
  static const Color textSecondary = Color(0xFF9FB0C8);
  static const Color accent = Color(0xFF2F8EE8);
  static const Color accentLight = Color(0xFF65B8FF);
  static const Color cyan = Color(0xFF23D3EE);
  static const Color green = Color(0xFF39D98A);
  static const Color greenBg = Color(0xFF102D22);
  static const Color orange = Color(0xFFFF9F43);
  static const Color red = Color(0xFFFF5C75);
  static const Color redBg = Color(0xFF32151F);
  static const Color yellow = Color(0xFFFFD166);

  static const double radiusSm = 8;
  static const double radiusMd = 12;
  static const double radiusLg = 16;

  static Color statusColor(String status) {
    switch (status.toUpperCase()) {
      case 'EMPTY':
        return green;
      case 'OCCUPIED':
        return orange;
      default:
        return textSecondary;
    }
  }

  static Color statusBg(String status) {
    switch (status.toUpperCase()) {
      case 'EMPTY':
        return greenBg;
      case 'OCCUPIED':
        return redBg;
      default:
        return cardLight;
    }
  }

  static String statusLabel(String status) {
    switch (status.toUpperCase()) {
      case 'EMPTY':
        return 'Trống';
      case 'OCCUPIED':
        return 'Đang có xe';
      default:
        return 'Chưa rõ';
    }
  }

  static IconData statusIcon(String status) {
    switch (status.toUpperCase()) {
      case 'EMPTY':
        return Icons.check_circle_outline;
      case 'OCCUPIED':
        return Icons.directions_car_filled_outlined;
      default:
        return Icons.help_outline;
    }
  }

  static ThemeData get darkTheme {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: navy,
      colorScheme: const ColorScheme.dark(
        primary: accent,
        secondary: cyan,
        surface: surface,
        error: red,
        onPrimary: Colors.white,
        onSecondary: navy,
        onSurface: textPrimary,
        onError: Colors.white,
      ),
    );

    return base.copyWith(
      textTheme: base.textTheme.apply(
        bodyColor: textPrimary,
        displayColor: textPrimary,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: navy,
        elevation: 0,
        scrolledUnderElevation: 0,
        titleTextStyle: TextStyle(
          color: textPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w700,
        ),
        iconTheme: IconThemeData(color: textPrimary),
      ),
      cardTheme: CardThemeData(
        color: card,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          side: const BorderSide(color: border),
        ),
        margin: EdgeInsets.zero,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: cyan, width: 1.4),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: red),
        ),
        labelStyle: const TextStyle(color: textSecondary),
        hintStyle: const TextStyle(color: textSecondary),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusMd),
          ),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: navy,
        selectedItemColor: cyan,
        unselectedItemColor: textSecondary,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
      ),
      dividerTheme: const DividerThemeData(color: border),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: cardLight,
        contentTextStyle: const TextStyle(color: textPrimary),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusMd),
        ),
      ),
    );
  }
}
