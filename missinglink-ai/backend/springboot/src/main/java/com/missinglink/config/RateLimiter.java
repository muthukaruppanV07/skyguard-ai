package com.missinglink.config;

import com.missinglink.common.ApiException;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Sliding-window rate limiter keyed by (bucket, key). In-memory implementation;
 * an interface so a Redis-backed limiter can replace it in production.
 */
@Component
public class RateLimiter {

    private final ConcurrentHashMap<String, Bucket> buckets = new ConcurrentHashMap<>();

    public void check(String bucket, String key, int maxPerMinute) {
        if (maxPerMinute <= 0) {
            return;
        }
        String cacheKey = bucket + ":" + key;
        long now = System.currentTimeMillis();
        Bucket current = buckets.compute(cacheKey, (k, existing) -> {
            Bucket b = existing == null ? new Bucket() : existing;
            if (now - b.windowStart > 60_000) {
                b.windowStart = now;
                b.count = 0;
            }
            b.count++;
            return b;
        });
        if (current.count > maxPerMinute) {
            throw ApiException.tooManyRequests("Rate limit exceeded for " + bucket + ". Retry later.");
        }
    }

    private static class Bucket {
        long windowStart = Instant.now().toEpochMilli();
        int count;
    }
}
