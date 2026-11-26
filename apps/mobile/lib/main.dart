import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:material_ui/material_ui.dart';

import 'app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await dotenv.load(fileName: '.env');
  } catch (error) {
    debugPrint('Mobile environment is not configured: $error');
  }

  final environment = dotenv.isInitialized ? dotenv.env : const <String, String>{};
  String configuredValue(String key, String compiledValue) {
    final compiled = compiledValue.trim();
    if (compiled.isNotEmpty) return compiled;
    return environment[key]?.trim() ?? '';
  }

  final apiKey = configuredValue(
    'FIREBASE_API_KEY',
    const String.fromEnvironment('FIREBASE_API_KEY'),
  );
  final appId = configuredValue(
    'FIREBASE_APP_ID',
    const String.fromEnvironment('FIREBASE_APP_ID'),
  );
  final projectId = configuredValue(
    'FIREBASE_PROJECT_ID',
    const String.fromEnvironment('FIREBASE_PROJECT_ID'),
  );
  final senderId = configuredValue(
    'FIREBASE_MESSAGING_SENDER_ID',
    const String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID'),
  );

  if ([apiKey, appId, projectId, senderId].every((value) => value.isNotEmpty)) {
    try {
      await Firebase.initializeApp(options: FirebaseOptions(
        apiKey: apiKey,
        appId: appId,
        projectId: projectId,
        messagingSenderId: senderId,
      ));
    } catch (error) {
      debugPrint('Firebase.initializeApp failed: $error');
    }
  }

  runApp(const EnerTechApp());
}
