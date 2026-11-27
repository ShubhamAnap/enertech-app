-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }
-keep class com.enertech.enertech_customer.** { *; }
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod

# Firebase & Google Sign-In / Credential Manager
-keep class com.google.firebase.** { *; }
-keep class com.google.android.gms.** { *; }
-keep class androidx.credentials.** { *; }
-dontwarn com.google.errorprone.annotations.**
-dontwarn javax.annotation.**

# Android WebView bridges
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# Flutter embedding references Play Core deferred components optionally
-dontwarn com.google.android.play.core.**
