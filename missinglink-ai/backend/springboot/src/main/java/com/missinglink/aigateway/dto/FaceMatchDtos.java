package com.missinglink.aigateway.dto;

import java.util.List;
import java.util.Map;

/** Contract for the FastAPI photo/face-match endpoint (POST /v1/face-match). */
public class FaceMatchDtos {

    private FaceMatchDtos() {
    }

    public record FaceMatchResponse(
            boolean faceDetected,
            double qualityScore,
            List<String> qualityFlags,
            List<FaceMatch> matches,
            String model,
            double threshold,
            long processingTimeMs,
            String warning) {
    }

    public record FaceMatch(
            Long caseId,
            String caseReference,
            String fullName,
            String status,
            double matchScore,
            double faceSimilarity,
            double imageSimilarity,
            Map<String, Double> signalWeights,
            String explanation,
            List<String> limitations,
            String recommendation) {
    }
}