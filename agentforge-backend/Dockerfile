# AgentForge 后端镜像：多阶段 Maven 构建 → JRE 运行
# 构建：docker build -t agentforge-backend .
FROM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /build

# 先复制 POM 与源码，利用 Docker 层缓存加速依赖下载
COPY pom.xml .
COPY agentforge-common/pom.xml agentforge-common/
COPY agentforge-framework/pom.xml agentforge-framework/
COPY agentforge-system/pom.xml agentforge-system/
COPY agentforge-module-agent/pom.xml agentforge-module-agent/
COPY agentforge-module-conversation/pom.xml agentforge-module-conversation/
COPY agentforge-module-file/pom.xml agentforge-module-file/
COPY agentforge-module-ai-gateway/pom.xml agentforge-module-ai-gateway/
COPY agentforge-start/pom.xml agentforge-start/
RUN mvn -q -B -Dmaven.wagon.http.retryHandler.count=5 -Dmaven.wagon.http.connectionTimeout=60000 \
    dependency:go-offline || true

COPY . .
RUN mvn -q -B -pl agentforge-start -am -Dmaven.wagon.http.retryHandler.count=5 \
    -Dmaven.wagon.http.connectionTimeout=60000 package -DskipTests

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=builder /build/agentforge-start/target/*.jar app.jar
ENV TZ=Asia/Shanghai
EXPOSE 8080
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "app.jar"]
