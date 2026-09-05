package com.missinglink.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Typed application configuration bound from application.yml / environment. */
@Data
@Configuration
@ConfigurationProperties(prefix = "missinglink")
public class AppProperties {

    private Jwt jwt = new Jwt();
    private Cors cors = new Cors();
    private Ai ai = new Ai();
    private Storage storage = new Storage();
    private Crypto crypto = new Crypto();
    private Email email = new Email();
    private Notifications notifications = new Notifications();
    private RateLimit rateLimit = new RateLimit();
    private Retention retention = new Retention();
    private Mfa mfa = new Mfa();
    private Matching matching = new Matching();

    @Data
    public static class Jwt {
        private String secret;
        private long accessTokenTtlMs = 900_000;
        private long refreshTokenTtlMs = 7 * 24 * 3600_000L;
    }

    @Data
    public static class Cors {
        private List<String> allowedOrigins = new ArrayList<>();
    }

    @Data
    public static class Ai {
        private String serviceUrl;
        private String apiKey;
        private boolean fallbackAllowed = true;
    }

    @Data
    public static class Storage {
        private String provider = "local";
        private String root = "./storage";
        private S3 s3 = new S3();
        private long signedUrlExpireMinutes = 15;

        @Data
        public static class S3 {
            private String endpoint;
            private String bucket;
            private String accessKey;
            private String secretKey;
        }
    }

    @Data
    public static class Crypto {
        private String encryptionKey;
    }

    @Data
    public static class Email {
        private String provider = "console";
        private Smtp smtp = new Smtp();

        @Data
        public static class Smtp {
            private String host;
            private int port = 587;
            private String username;
            private String password;
            private String from;
        }
    }

    @Data
    public static class Notifications {
        private String publicBaseUrl;
    }

    @Data
    public static class RateLimit {
        private int perMinute = 60;
        private int loginPerMinute = 5;
        private int sightingPerMinute = 10;
    }

    @Data
    public static class Retention {
        private int retentionDays = 365;
    }

    @Data
    public static class Mfa {
        private boolean required = false;
    }

    @Data
    public static class Matching {
        private Map<String, Double> weights = new HashMap<>();
        private double geoRadiusKm = 25.0;
        private double timeDecayHours = 24.0;
        private double minOverallScore = 0.55;
    }
}
