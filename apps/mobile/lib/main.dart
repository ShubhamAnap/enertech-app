import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:material_ui/material_ui.dart';

import 'app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: '.env');
  final apiKey = dotenv.env['FIREBASE_API_KEY'] ?? '';
  final appId = dotenv.env['FIREBASE_APP_ID'] ?? '';
  final projectId = dotenv.env['FIREBASE_PROJECT_ID'] ?? '';
  final senderId = dotenv.env['FIREBASE_MESSAGING_SENDER_ID'] ?? '';
  if ([apiKey, appId, projectId, senderId].every((value) => value.isNotEmpty)) {
    await Firebase.initializeApp(options: FirebaseOptions(apiKey: apiKey, appId: appId, projectId: projectId, messagingSenderId: senderId));
  }
  runApp(const EnerTechApp());
}
