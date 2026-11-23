# Notes

A native Android plain-text notes app built with Kotlin and Jetpack Compose. It provides a dark editor, multiple tabs, local drafts that survive closing and reopening the app, and explicit `.txt` import and export.

## Requirements

- JDK 17
- Android SDK platform and build tools 35
- Android platform tools and emulator
- Android 29 x86_64 system image
- Linux KVM access for managed-device tests

## Installation

Configure the Android and Java environment:

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_SDK_ROOT=/usr/lib/android-sdk
export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:$PATH"
```

Build the debug APK:

```bash
./gradlew assembleDebug
```

The APK is generated at `app/build/outputs/apk/debug/app-debug.apk`.

## Run

Install the APK on a connected Android device or emulator:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Use the overflow menu beside the tab actions to import one UTF-8 `.txt` file or export the selected draft. Import accepts files up to 1 MiB. Transfers use Android's system document picker and require no storage permission.

## Tests

Run the unit tests:

```bash
./gradlew testDebugUnitTest
```

Run the API 29 managed-device tests:

```bash
./gradlew pixel2Api29DebugAndroidTest
```

Run the complete quality gate:

```bash
./gradlew testDebugUnitTest pixel2Api29DebugAndroidTest lintDebug assembleDebug
```

Product specifications are under `specs/`. Engineering decisions and implementation records are under `.spec-driven/`.
