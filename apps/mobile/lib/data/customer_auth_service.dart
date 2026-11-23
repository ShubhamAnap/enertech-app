import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:google_sign_in/google_sign_in.dart';

class CustomerAuthService {
  static Future<void>? _googleInitialization;

  Future<UserCredential> signInWithGoogle() async {
    final clientId = (dotenv.isInitialized ? dotenv.env['GOOGLE_SERVER_CLIENT_ID'] : null)?.trim() ?? '423316048940-e0915dl09gcg428dhffek68o87f5djvt.apps.googleusercontent.com';
    if (clientId.isEmpty) {
      throw FirebaseAuthException(code: 'google-not-configured', message: 'Google sign-in is not configured for this Firebase app yet.');
    }
    final google = GoogleSignIn.instance;
    _googleInitialization ??= google.initialize(serverClientId: clientId);
    await _googleInitialization;
    if (!google.supportsAuthenticate()) {
      throw FirebaseAuthException(code: 'google-platform-not-supported', message: 'Google sign-in is not supported by this app build.');
    }
    final account = await google.authenticate();
    final idToken = account.authentication.idToken;
    if (idToken == null || idToken.isEmpty) {
      throw FirebaseAuthException(code: 'google-token-missing', message: 'Google sign-in did not return an ID token. Check the Firebase OAuth configuration.');
    }
    final credential = GoogleAuthProvider.credential(idToken: idToken);
    return FirebaseAuth.instance.signInWithCredential(credential);
  }

  Future<void> signOut() async {
    await FirebaseAuth.instance.signOut();
    await GoogleSignIn.instance.signOut();
  }
}
