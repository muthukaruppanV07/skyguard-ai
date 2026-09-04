package com.missinglink;

import com.missinglink.config.AppProperties;
import com.missinglink.config.CryptoService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class CryptoServiceTest {

    private CryptoService crypto;

    @BeforeEach
    void setUp() {
        AppProperties props = new AppProperties();
        props.getCrypto().setEncryptionKey(
                "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef");
        crypto = new CryptoService(props);
    }

    @Test
    void roundTripEncryptsAndDecrypts() {
        String plain = "identification mark: scar on right knee; phone 555-0100";
        String encrypted = crypto.encrypt(plain);
        assertThat(encrypted).startsWith("enc:");
        assertThat(encrypted).doesNotContain(plain);
        assertThat(crypto.decrypt(encrypted)).isEqualTo(plain);
    }

    @Test
    void nullAndUnencryptedPassThrough() {
        assertThat(crypto.encrypt(null)).isNull();
        assertThat(crypto.decrypt("plain-text")).isEqualTo("plain-text");
    }

    @Test
    void ciphertextsAreUniquePerCall() {
        String a = crypto.encrypt("same");
        String b = crypto.encrypt("same");
        assertThat(a).isNotEqualTo(b);
        assertThat(crypto.decrypt(a)).isEqualTo(crypto.decrypt(b));
    }
}
