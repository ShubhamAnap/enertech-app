import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:material_ui/material_ui.dart';

import 'app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await dotenv.load(fileName: '.env');
  } catch (e) {
    debugPrint('dotenv.load warning: $e');
  }

  try {
    final apiKey = dotenv.env['FIREBASE_API_KEY']?.trim() ?? '';
    final appId = dotenv.env['FIREBASE_APP_ID']?.trim() ?? '';
    final projectId = dotenv.env['FIREBASE_PROJECT_ID']?.trim() ?? '';
    final senderId = dotenv.env['FIREBASE_MESSAGING_SENDER_ID']?.trim() ?? '';

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
