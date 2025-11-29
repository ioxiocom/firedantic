#!/usr/bin/env sh
export GOOGLE_CLOUD_PROJECT=test-project

exec firebase -P firedantic-test emulators:start --only firestore
