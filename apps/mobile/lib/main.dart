import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:material_ui/material_ui.dart';

import 'app.dart';

const String _embeddedEnv = '''
API_BASE_URL=http://10.0.2.2:8000/api/v1
FIREBASE_API_KEY=AIzaSyAUbtbOGwZwjLLAacs5VZtJKwSZfyNAxW4
FIREBASE_APP_ID=1:423316048940:android:405f584a1724eadcea1589
FIREBASE_PROJECT_ID=enertech-ups
FIREBASE_MESSAGING_SENDER_ID=423316048940
GOOGLE_SERVER_CLIENT_ID=423316048940-e0915dl09gcg428dhffek68o87f5djvt.apps.googleusercontent.com
''';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Safely initialize dotenv with layered fallbacks:
  // 1. Try .env
  // 2. Try assets/app.env
  // 3. Fallback to embedded config string
  try {
    await dotenv.load(fileName: '.env');
  } catch (_) {
    try {
      await dotenv.load(fileName: 'assets/app.env');
    } catch (_) {
      try {
        dotenv.loadFromString(envString: _embeddedEnv);
      } catch (e) {
        debugPrint('dotenv.loadFromString warning: $e');
      }
    }
  }

  // Absolute safety guarantee: DotEnv is always initialized
  if (!dotenv.isInitialized) {
    try {
      dotenv.loadFromString(envString: _embeddedEnv);
    } catch (_) {}
  }

  try {
    final apiKey = (dotenv.isInitialized ? dotenv.env['FIREBASE_API_KEY'] : null)?.trim() ?? 'AIzaSyAUbtbOGwZwjLLAacs5VZtJKwSZfyNAxW4';
    final appId = (dotenv.isInitialized ? dotenv.env['FIREBASE_APP_ID'] : null)?.trim() ?? '1:423316048940:android:405f584a1724eadcea1589';
    final projectId = (dotenv.isInitialized ? dotenv.env['FIREBASE_PROJECT_ID'] : null)?.trim() ?? 'enertech-ups';
    final senderId = (dotenv.isInitialized ? dotenv.env['FIREBASE_MESSAGING_SENDER_ID'] : null)?.trim() ?? '423316048940';

    if (Firebase.apps.isEmpty) {
      if ([apiKey, appId, projectId, senderId].every((value) => value.isNotEmpty)) {
        await Firebase.initializeApp(
          options: FirebaseOptions(
            apiKey: apiKey,
            appId: appId,
            projectId: projectId,
            messagingSenderId: senderId,
          ),
        );
      } else {
        await Firebase.initializeApp();
      }
    }
  } catch (e) {
    debugPrint('Firebase.initializeApp warning: $e');
  }

  runApp(const EnerTechApp());
}
