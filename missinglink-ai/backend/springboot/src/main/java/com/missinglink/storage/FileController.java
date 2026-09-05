package com.missinglink.storage;

import com.missinglink.common.ApiException;
import org.springframework.core.io.InputStreamResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.*;

import java.io.InputStream;
import java.util.Optional;

/**
 * Serves evidence files through expiring HMAC-signed URLs.
 * Pattern: /api/v1/files/{encodedKey}?e={expiresEpochSec}&s={signature}
 */
@Controller
@RequestMapping("/api/v1/files")
public class FileController {

    private final SignedUrlService signedUrls;
    private final StorageService storage;

    public FileController(SignedUrlService signedUrls, StorageService storage) {
        this.signedUrls = signedUrls;
        this.storage = storage;
    }

    @GetMapping("/{encodedKey}")
    public ResponseEntity<?> file(@PathVariable String encodedKey,
                                  @RequestParam long e,
                                  @RequestParam String s) {
        String key;
        try {
            key = SignedUrlService.decodeKey(encodedKey);
        } catch (Exception ex) {
            throw ApiException.badRequest("Invalid file reference");
        }
        if (!signedUrls.verify(key, e, s)) {
            throw ApiException.unauthorized("Signed URL is invalid or expired");
        }
        Optional<InputStream> stream = storage.load(key);
        if (stream.isEmpty()) {
            throw ApiException.notFound("File not found");
        }
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        "inline; filename=\"" + key.substring(key.lastIndexOf('/') + 1) + "\"")
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .body(new InputStreamResource(stream.get()));
    }
}