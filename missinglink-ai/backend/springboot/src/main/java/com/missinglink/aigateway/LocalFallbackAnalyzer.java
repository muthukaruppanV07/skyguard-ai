package com.missinglink.aigateway;

/**
 * Local deterministic fallback used only when the FastAPI service is unreachable
 * and AI_FALLBACK_ALLOWED=true. Produces valid-but-weak vision signals so the whole
 * pipeline (vector store, ranking, queue) still works during demos/dev.
 */
public class LocalFallbackAnalyzer {

    private LocalFallbackAnalyzer() {
    }

    public static final String MODEL = "local-fallback/v1";

    public static double[] embeddingFrom(byte[] data, int dim) {
        // Deterministic 512-d feature from file bytes (FNV-based), L2-normalized.
        double[] vec = new double[dim];
        long h1 = 0x9E3779B97F4A7C15L;
        long h2 = 0xBF58476D1CE4E5B9L;
        for (byte b : data) {
            h1 ^= (b & 0xFF);
            h1 = rotl64(h1, 23) + h2;
            h2 = rotl64(h2 ^ (b & 0xFF), 17) + h1;
        }
        for (int i = 0; i < dim; i++) {
            h1 = rotl64(h1, 11) ^ h2;
            h2 = rotl64(h2, 31) + h1;
            vec[i] = ((h1 ^ h2) % 2L == 0 ? 1.0 : -1.0);
        }
        return l2Normalize(vec);
    }

    public static double quality(long sizeBytes) {
        // Longer non-trivial files have "better" signal in this fallback.
        return Math.min(0.95, 0.35 + Math.log10(sizeBytes + 1) * 0.05);
    }

    public static double[] l2Normalize(double[] v) {
        double norm = 0;
        for (double d : v) {
            norm += d * d;
        }
        norm = Math.sqrt(norm);
        if (norm < 1e-9) {
            return v;
        }
        for (int i = 0; i < v.length; i++) {
            v[i] /= norm;
        }
        return v;
    }

    private static long rotl64(long x, int s) {
        return (x << s) | (x >>> (64 - s));
    }
}