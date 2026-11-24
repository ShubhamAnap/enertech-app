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
  final apiKey = environment['FIREBASE_API_KEY']?.trim() ?? '';
  final appId = environment['FIREBASE_APP_ID']?.trim() ?? '';
  final projectId = environment['FIREBASE_PROJECT_ID']?.trim() ?? '';
  final senderId = environment['FIREBASE_MESSAGING_SENDER_ID']?.trim() ?? '';

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
