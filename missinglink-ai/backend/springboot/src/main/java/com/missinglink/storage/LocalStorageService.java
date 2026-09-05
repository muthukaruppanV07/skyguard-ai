package com.missinglink.storage;

import com.missinglink.common.ApiException;
import com.missinglink.config.AppProperties;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.Optional;

/** Filesystem-backed storage. Production image mounts ./storage as a volume. */
@Service("localStorageService")
public class LocalStorageService implements StorageService {

    private final Path root;

    public LocalStorageService(AppProperties props) {
        this.root = Paths.get(props.getStorage().getRoot()).toAbsolutePath().normalize();
        try {
            Files.createDirectories(root);
        } catch (IOException e) {
            throw new IllegalStateException("Cannot create storage root", e);
        }
    }

    @Override
    public String store(String key, InputStream content, String contentType) {
        Path target = resolveSafe(key);
        try {
            Files.createDirectories(target.getParent());
            Files.copy(content, target, StandardCopyOption.REPLACE_EXISTING);
            return key;
        } catch (IOException e) {
            throw ApiException.internal("Failed to store file: " + e.getMessage());
        }
    }

    @Override
    public Optional<InputStream> load(String key) {
        Path target = resolveSafe(key);
        if (!Files.exists(target)) {
            return Optional.empty();
        }
        try {
            return Optional.of(Files.newInputStream(target));
        } catch (IOException e) {
            throw ApiException.internal("Failed to read file: " + e.getMessage());
        }
    }

    @Override
    public void delete(String key) {
        Path target = resolveSafe(key);
        try {
            Files.deleteIfExists(target);
        } catch (IOException e) {
            throw ApiException.internal("Failed to delete file: " + e.getMessage());
        }
    }

    @Override
    public boolean exists(String key) {
        return Files.exists(resolveSafe(key));
    }

    /** Defends against path traversal in user-supplied keys. */
    private Path resolveSafe(String key) {
        Path normalized = root.resolve(key).normalize();
        if (!normalized.startsWith(root)) {
            throw ApiException.badRequest("Invalid storage key");
        }
        return normalized;
    }
}