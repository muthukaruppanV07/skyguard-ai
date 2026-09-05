package com.missinglink;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class MissinglinkApplication {

    public static void main(String[] args) {
        SpringApplication.run(MissinglinkApplication.class, args);
    }
}
