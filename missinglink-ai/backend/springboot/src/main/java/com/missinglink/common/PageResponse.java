package com.missinglink.common;

import lombok.Getter;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@Getter
public class PageResponse<T> {
    private final List<T> content;
    private final int page;
    private final int size;
    private final long totalElements;
    private final int totalPages;

    public PageResponse(List<T> content, int page, int size, long totalElements) {
        this.content = content;
        this.page = page;
        this.size = size;
        this.totalElements = totalElements;
        this.totalPages = size == 0 ? 0 : (int) Math.ceil((double) totalElements / size);
    }

    public record ErrorResponse(Instant timestamp, int status, String error, String path,
                                Map<String, String> fieldErrors) {
    }
}
