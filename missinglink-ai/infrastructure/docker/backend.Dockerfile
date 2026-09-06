# syntax=docker/dockerfile:1

# ---- build stage -------------------------------------------------------------
FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /workspace
COPY backend/springboot/pom.xml pom.xml
RUN mvn -q -B dependency:go-offline
COPY backend/springboot/src ./src
RUN mvn -q -B -DskipTests package

# ---- run stage ---------------------------------------------------------------
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /workspace/target/missinglink-backend-0.1.0.jar app.jar
RUN mkdir -p /app/storage
EXPOSE 8080
ENV SPRING_PROFILES_ACTIVE=docker \
    JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75"
ENTRYPOINT ["java", "-jar", "app.jar"]
