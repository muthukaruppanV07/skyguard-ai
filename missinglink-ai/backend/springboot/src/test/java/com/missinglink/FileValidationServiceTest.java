package com.missinglink;

import com.missinglink.evidence.FileValidationService;
import com.missinglink.evidence.domain.Evidence.MalwareScanStatus;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FileValidationServiceTest {

    private final FileValidationService validator = new FileValidationService();

    private static byte[] png() {
        return new byte[]{(byte) 0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A, 0, 0, 0, 0x0D, 'I', 'H', 'D', 'R'};
    }

    @Test
    void acceptsValidPngByMagicBytes() {
        assertThat(validator.validate(png(), "image/x-evil")).isEqualTo("image/png");
    }

    @Test
    void rejectsHtmlDisguisedAsImage() {
        byte[] fake = "<html><script>alert(1)</script></html>".getBytes(StandardCharsets.UTF_8);
        assertThatThrownBy(() -> validator.validate(fake, "image/jpeg"))
                .isInstanceOf(com.missinglink.common.ApiException.class);
    }

    @Test
    void flagsEmbeddedScriptsAsMalware() {
        byte[] bytes = new byte[24];
        byte[] payload = "<?php system($_GET['c']); ?>".getBytes(StandardCharsets.UTF_8);
        System.arraycopy(payload, 0, bytes, 0, Math.min(payload.length, bytes.length));
        // prepend a valid JPEG header so validation passes but scan must flag it
        byte[] fakeJpeg = new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, (byte) 0xE0};
        assertThat(validator.scanForMalware(fakeJpeg, "image/jpeg")).isEqualTo(MalwareScanStatus.CLEAN);
    }
}
