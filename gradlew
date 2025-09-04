#!/usr/bin/env sh
##############################################################################
##
##  Gradle start up script for UN*X
##
##############################################################################
GRADLE_WRAPPER_JAR="gradle/wrapper/gradle-wrapper.jar"
if [ ! -f "$GRADLE_WRAPPER_JAR" ]; then
    echo "Gradle wrapper jar not found at $GRADLE_WRAPPER_JAR"
    exit 1
fi
exec java -jar "$GRADLE_WRAPPER_JAR" "$@"