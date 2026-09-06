package com.missinglink.storage;

import com.missinglink.config.AppProperties;
import org.springframework.stereotype.Service;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;

/**
 * HMAC-signed expiring URLs for serving evidence files to authorized parties.
 * Composition: /api/v1/files/{key}?e={expiresEpochSec}&s={hmac}
 */
@Service
public class SignedUrlService {

    private final byte[] key;

    public SignedUrlService(AppProperties props) {
        this.key = props.getJwt().getSecret().getBytes(StandardCharsets.UTF_8);
    }

    public String create(String storageKey, long expireMinutes) {
        long expires = System.currentTimeMillis() / 1000 + expireMinutes * 60;
        return "/api/v1/files/" + encodeKey(storageKey) + "?e=" + expires + "&s=" + sign(storageKey, expires);
    }

    public boolean verify(String storageKey, long expiresEpochSec, String signature) {
        if (expiresEpochSec < System.currentTimeMillis() / 1000) {
            return false;
        }
        return signature != null && signature.equals(sign(storageKey, expiresEpochSec));
    }

    private String sign(String key, long expires) {
        String message = key + ":" + expires;
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(this.key, "HmacSHA256"));
            return HexFormat.of().formatHex(mac.doFinal(message.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException("HMAC unavailable", e);
        }
    }

    private static String encodeKey(String key) {
        return java.util.Base64.getUrlEncoder().withoutPadding()
                .encodeToString(key.getBytes(StandardCharsets.UTF_8));
    }

    public static String decodeKey(String encoded) {
        return new String(java.util.Base64.getUrlDecoder().decode(encoded), StandardCharsets.UTF_8);
    }
}