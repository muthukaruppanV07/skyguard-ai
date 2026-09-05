package com.missinglink.storage;

import java.io.InputStream;
import java.util.Optional;

/**
 * Uniform storage abstraction. Implementations: local filesystem, S3-compatible.
 * A demo provider can be swapped without changing callers.
 */
public interface StorageService {

    /**
     * Store the stream under the given key; returns the storage key.
     * Keys are caller-generated (usually "folder/uuid.ext").
     */
    String store(String key, InputStream content, String contentType);

    /** Stream contents back for the key, if it exists. */
    Optional<InputStream> load(String key);

    /** Delete a stored object. */
    void delete(String key);

    /** Whether a key exists. */
    boolean exists(String key);
}