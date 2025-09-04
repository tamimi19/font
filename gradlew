#!/bin/sh
#
# Gradle start up script for UN*X
#
##############################################################################
# Locate a Java installation.
##############################################################################
if [ -n "$JAVA_HOME" ] ; then
    JAVA_EXEC="$JAVA_HOME/bin/java"
else
    JAVA_EXEC="$(which java)"
fi

if [ ! -x "$JAVA_EXEC" ] ; then
    echo "ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH." >&2
    exit 1
fi

##############################################################################
# Locate the Gradle wrapper JAR and properties.
##############################################################################
PRG="$0"
while [ -h "$PRG" ] ; do
    ls=$(ls -ld "$PRG")
    link=$(expr "$ls" : '.*-> \(.*\)$')
    if expr "$link" : '/.*' > /dev/null; then
        PRG="$link"
    else
        PRG=$(dirname "$PRG")"/$link"
    fi
done
SAVED="$(pwd)"
cd "$(dirname \"$PRG\")" >/dev/null
APP_HOME="$(pwd -P)"
cd "$SAVED" >/dev/null

WRAPPER_JAR="$APP_HOME/gradle/wrapper/gradle-wrapper.jar"

if [ ! -f "$WRAPPER_JAR" ]; then
    echo "ERROR: $WRAPPER_JAR not found." >&2
    echo "Please run 'gradle wrapper' to generate the wrapper files." >&2
    exit 1
fi

##############################################################################
# Execute Gradle.
##############################################################################
exec "$JAVA_EXEC" -Xmx64m -Xms64m -cp "$WRAPPER_JAR" org.gradle.wrapper.GradleWrapperMain "$@"
