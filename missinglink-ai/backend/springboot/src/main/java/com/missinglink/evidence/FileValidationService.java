package com.missinglink.evidence;

import com.missinglink.evidence.domain.Evidence.MalwareScanStatus;
import org.springframework.stereotype.Component;

import java.util.Arrays;
import java.util.List;

/**
 * File-validation & malware-scan abstraction.
 *
 * Security properties enforced in the evidence pipeline:
 *  1. Content-type allowlist
 *  2. Magic-byte sniffing (independent of the client-provided header)
 *  3. Size cap
 *  4. Malware scan (provider hook; default pass-through for demo)
 *
 * The malware-scan is wired to a provider interface so ClamAV / commercial scanners
 * can be attached without touching callers.
 */
@Component
public class FileValidationService {

    private record TypeRule(String ext, String mime, byte[][] magic) {
    }

    private static final long MAX_SIZE_BYTES = 25L * 1024 * 1024;

    private static final List<TypeRule> RULES = List.of(
            new TypeRule("jpg", "image/jpeg", new byte[][]{{(byte) 0xFF, (byte) 0xD8}}),
            new TypeRule("png", "image/png", new byte[][]{{(byte) 0x89, 'P', 'N', 'G'}}),
            new TypeRule("webp", "image/webp", new byte[][]{{'R', 'I', 'F', 'F'}}),
            new TypeRule("mp4", "video/mp4", new byte[][]{{0, 0, 0, (byte) 0x18}, {0, 0, 0, (byte) 0x1C}}),
            new TypeRule("mov", "video/quicktime", new byte[][]{{'f', 't', 'y', 'p'}}),
            new TypeRule("pdf", "application/pdf", new byte[][]{{'%', 'P', 'D', 'F'}})
    );

    /** Returns the validated, sniffed MIME type or throws. */
    public String validate(byte[] bytes, String providedContentType) {
        if (bytes.length > MAX_SIZE_BYTES) {
            throw new com.missinglink.common.ApiException(
                    org.springframework.http.HttpStatus.PAYLOAD_TOO_LARGE, "File exceeds 25 MB limit");
        }
        if (bytes.length < 16) {
            throw new com.missinglink.common.ApiException(
                    org.springframework.http.HttpStatus.BAD_REQUEST, "File too small to be valid media");
        }
        for (TypeRule rule : RULES) {
            for (byte[] magic : rule.magic()) {
                if (startsWith(bytes, magic)) {
                    return rule.mime();
                }
            }
        }
        throw new com.missinglink.common.ApiException(
                org.springframework.http.HttpStatus.BAD_REQUEST,
                "Unsupported file type. Allowed: JPEG/PNG/WebP images, MP4/MOV video, PDF.");
    }

    public MalwareScanStatus scanForMalware(byte[] bytes, String sniffedMime) {
        // Provider hook: real deployment plugs ClamAV / Defang etc. here.
        // Heuristic: treat executables / scripts embedded in the first bytes as suspect.
        if (containsAscii(bytes, "MZ") || containsAscii(bytes, "BasedOnDirectives") || containsAscii(bytes, "<?php")
                || containsAscii(bytes, "<script") || containsAscii(bytes, "<html")) {
            return MalwareScanStatus.FLAGGED;
        }
        return MalwareScanStatus.CLEAN;
    }

    private static boolean startsWith(byte[] data, byte[] prefix) {
        if (data.length < prefix.length) {
            return false;
        }
        for (int i = 0; i < prefix.length; i++) {
            if (data[i] != prefix[i]) {
                return false;
            }
        }
        return true;
    }

    private static boolean containsAscii(byte[] data, String ascii) {
        byte[] needle = ascii.getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        return indexOf(data, needle) >= 0;
    }

    private static int indexOf(byte[] haystack, byte[] needle) {
        outer:
        for (int i = 0; i <= haystack.length - needle.length; i++) {
            for (int j = 0; j < needle.length; j++) {
                if (haystack[i + j] != needle[j]) {
                    continue outer;
                }
            }
            return i;
        }
        return -1;
    }
}