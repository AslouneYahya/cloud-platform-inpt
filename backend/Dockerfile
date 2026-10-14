# =============================================================================
# backend/Dockerfile — multi-stage build for Spring Boot application
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Build — compile and package the application with Maven
# -----------------------------------------------------------------------------
FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /app

# Copy the POM first to leverage Docker layer caching for dependencies.
COPY pom.xml .

# Pre-download all dependencies so subsequent builds are faster when only
# source files change.
RUN mvn dependency:go-offline -q

# Copy the rest of the source code and build the fat JAR.
COPY src ./src

RUN mvn package -DskipTests -q

# -----------------------------------------------------------------------------
# Stage 2: Runtime — minimal JRE image (no compiler or build tools)
# -----------------------------------------------------------------------------
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# Copy the fat JAR produced by the builder stage.
COPY --from=builder /app/target/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
