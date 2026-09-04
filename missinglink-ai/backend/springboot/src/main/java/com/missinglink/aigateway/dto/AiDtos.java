package com.missinglink.aigateway.dto;

import java.util.List;
import java.util.Map;

/** Shared DTOs for the backend↔FastAPI contract. */
public class AiDtos {

    private AiDtos() {
    }

    public record AnalyzeImageResponse(
            boolean ok,
            String model,
            double qualityScore,
            List<String> qualityFlags,
            boolean faceDetected,
            FaceInfo face,
            List<DetectedObject> objects,
            List<Double> embedding,
            List<String> clothingTags,
            List<String> accessoryTags,
            int dimension,
            long processingTimeMs) {
    }

    public record FaceInfo(double confidence, int x, int y, int width, int height, double[] landmarks) {
    }

    public record DetectedObject(String label, double confidence, int[] bbox) {
    }
}