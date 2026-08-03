package com.agentforge;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * AgentForge 后端启动入口。
 * 扫描 com.agentforge 下全部组件；Mapper 按模块目录扫描。
 */
@SpringBootApplication(scanBasePackages = "com.agentforge")
@MapperScan("com.agentforge.**.mapper")
public class AgentForgeApplication {

    public static void main(String[] args) {
        SpringApplication.run(AgentForgeApplication.class, args);
    }
}
