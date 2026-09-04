package com.missinglink.storage;

import com.missinglink.common.ApiException;
import com.missinglink.config.AppProperties;
import org.springframework.stereotype.Service;

import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/**
 * In-memory demo/stub storage used for local development or when object storage
 * is unavailable. Replace with the S3 provider in production (see Docker docs).
 */
@Service("mockStorageService")
public class MockStorageService implements StorageService {

    private final Map<String, byte[]> blobs = new HashMap<>();

    public MockStorageService(AppProperties props) {
        // no-op
    }

    @Override
    public String store(String key, InputStream content, String contentType) {
        try {
            blobs.put(key, content.readAllBytes());
            return key;
        } catch (Exception e) {
            throw ApiException.internal("Failed to store file in memory");
        }
    }

    @Override
    public Optional<InputStream> load(String key) {
        byte[] data = blobs.get(key);
        return data == null ? Optional.empty() : Optional.of(new java.io.ByteArrayInputStream(data));
    }

    @Override
    public void delete(String key) {
        blobs.remove(key);
    }

    @Override
    public boolean exists(String key) {
        return blobs.containsKey(key);
    }
}