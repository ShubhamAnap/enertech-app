import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:google_sign_in/google_sign_in.dart';

class CustomerAuthService {
  static Future<void>? _googleInitialization;

  Future<UserCredential?> signInWithGoogle() async {
    // Strategy 1: Attempt native GoogleSignIn (Credential Manager / One-Tap)
    try {
      final clientId = (dotenv.isInitialized ? dotenv.env['GOOGLE_SERVER_CLIENT_ID'] : null)?.trim();
      final effectiveClientId = (clientId != null && clientId.isNotEmpty)
          ? clientId
          : '423316048940-e0915dl09gcg428dhffek68o87f5djvt.apps.googleusercontent.com';

      final google = GoogleSignIn.instance;
      _googleInitialization ??= google.initialize(
        serverClientId: effectiveClientId.isNotEmpty ? effectiveClientId : null,
      );
      await _googleInitialization;

      if (google.supportsAuthenticate()) {
        final account = await google.authenticate();
        final idToken = account.authentication.idToken;
        if (idToken != null && idToken.isNotEmpty) {
          final credential = GoogleAuthProvider.credential(idToken: idToken);
          return await FirebaseAuth.instance.signInWithCredential(credential);
        }
      }
    } catch (nativeError) {
      debugPrint('Native GoogleSignIn note: $nativeError. Attempting Firebase Auth Provider fallback...');
    }

    // Strategy 2: Resilient Web/OAuth Provider flow via Firebase Auth
    // This uses Chrome Custom Tabs / web redirect on Android, which works even if SHA-1 is not yet registered in Firebase Console
    try {
      final provider = GoogleAuthProvider();
      provider.addScope('email');
      provider.addScope('profile');
      return await FirebaseAuth.instance.signInWithProvider(provider);
    } on FirebaseAuthException catch (authError) {
      if (authError.code == 'popup-closed-by-user' ||
          authError.code == 'canceled' ||
          authError.code == 'web-context-cancelled') {
        return null; // User cancelled without error
      }
      rethrow;
    } catch (error) {
      debugPrint('Firebase provider sign-in error: $error');
      rethrow;
    }
  }

  Future<void> signOut() async {
    try {
      await FirebaseAuth.instance.signOut();
    } catch (_) {}
    try {
      await GoogleSignIn.instance.signOut();
    } catch (_) {}
  }
}
