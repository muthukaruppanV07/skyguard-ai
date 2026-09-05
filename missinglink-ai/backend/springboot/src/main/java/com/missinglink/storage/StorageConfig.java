package com.missinglink.storage;

import com.missinglink.config.AppProperties;
import org.springframework.context.annotation.Primary;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** Selects the storage provider based on configuration (STORAGE_PROVIDER). */
@Configuration
public class StorageConfig {

    @Bean
    @Primary
    public StorageService storageService(LocalStorageService local, MockStorageService mock,
                                         AppProperties props) {
        return switch (props.getStorage().getProvider().toLowerCase()) {
            case "mock" -> mock;
            default -> local;
        };
    }
}