package com.missinglink.config;

import com.missinglink.common.ApiException;
import org.springframework.stereotype.Service;

import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * AES-256-GCM field encryption for sensitive data at rest.
 * Key is a 64-hex-character string provided via ENCRYPTION_KEY.
 */
@Service
public class CryptoService {

    private static final int GCM_TAG_BITS = 128;
    private static final int IV_BYTES = 12;
    private static final String PREFIX = "enc:";

    private final SecretKey key;
    private final SecureRandom random = new SecureRandom();

    public CryptoService(AppProperties props) {
        String hex = props.getCrypto().getEncryptionKey();
        if (hex == null || hex.isBlank()) {
            throw new IllegalStateException("ENCRYPTION_KEY is not configured. Provide a 64-char hex key.");
        }
        byte[] raw = hexToBytes(hex);
        if (raw.length != 32) {
            throw new IllegalStateException("ENCRYPTION_KEY must decode to 32 bytes (AES-256).");
        }
        this.key = new SecretKeySpec(raw, "AES");
    }

    public String encrypt(String plaintext) {
        if (plaintext == null) {
            return null;
        }
        if (plaintext.startsWith(PREFIX)) {
            return plaintext;
        }
        try {
            byte[] iv = new byte[IV_BYTES];
            random.nextBytes(iv);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(GCM_TAG_BITS, iv));
            byte[] encrypted = cipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));
            byte[] combined = new byte[iv.length + encrypted.length];
            System.arraycopy(iv, 0, combined, 0, iv.length);
            System.arraycopy(encrypted, 0, combined, iv.length, encrypted.length);
            return PREFIX + Base64.getEncoder().encodeToString(combined);
        } catch (Exception e) {
            throw ApiException.internal("Encryption failed: " + e.getMessage());
        }
    }

    public String decrypt(String ciphertext) {
        if (ciphertext == null) {
            return null;
        }
        if (!ciphertext.startsWith(PREFIX)) {
            return ciphertext;
        }
        try {
            byte[] combined = Base64.getDecoder().decode(ciphertext.substring(PREFIX.length()));
            byte[] iv = new byte[IV_BYTES];
            byte[] body = new byte[combined.length - IV_BYTES];
            System.arraycopy(combined, 0, iv, 0, IV_BYTES);
            System.arraycopy(combined, IV_BYTES, body, 0, body.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(GCM_TAG_BITS, iv));
            return new String(cipher.doFinal(body), StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw ApiException.internal("Decryption failed: " + e.getMessage());
        }
    }

    private static byte[] hexToBytes(String hex) {
        byte[] out = new byte[hex.length() / 2];
        for (int i = 0; i < out.length; i++) {
            int index = i * 2;
            out[i] = (byte) Integer.parseInt(hex.substring(index, index + 2), 16);
        }
        return out;
    }
}
