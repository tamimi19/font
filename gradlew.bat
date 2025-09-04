@echo off
setlocal
set GRADLE_WRAPPER_JAR=gradle/wrapper/gradle-wrapper.jar
if not exist "%GRADLE_WRAPPER_JAR%" (
    echo Gradle wrapper jar not found at %GRADLE_WRAPPER_JAR%
    exit /b 1
)
java -jar "%GRADLE_WRAPPER_JAR%" %*