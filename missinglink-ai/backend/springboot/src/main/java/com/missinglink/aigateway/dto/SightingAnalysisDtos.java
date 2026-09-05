package com.missinglink.aigateway.dto;

import java.util.List;
import java.util.Map;

public class SightingAnalysisDtos {

    private SightingAnalysisDtos() {
    }

    /** Sent by the backend to the FastAPI sighting-analysis endpoint. */
    public record AnalyzeSightingRequest(
            double lat,
            double lng,
            String capturedAt,
            String description,
            String clothing,
            String imageBase64,
            Map<String, Double> weights,
            double geoRadiusKm,
            double timeDecayHours,
            double minOverallScore) {
    }

    /** Ranked potential matches returned by the AI service (never an identity claim). */
    public record AnalyzeSightingResponse(
            EvidenceSummary evidence,
            List<RankedMatch> potentialMatches,
            List<Double> imageEmbedding,
            String model,
            String warning) {
    }

    public record RankedMatch(
            Long caseId,
            String caseReference,
            double overallScore,
            double faceSimilarity,
            double clothingSimilarity,
            double accessorySimilarity,
            double bodySimilarity,
            double imageSimilarity,
            double locationRelevance,
            double timeRelevance,
            double textSimilarity,
            List<String> explanation,
            List<String> limitations,
            String modelVersion) {
    }

    public record EvidenceSummary(
            double qualityScore,
            List<String> qualityFlags,
            boolean faceDetected,
            List<String> clothingTags,
            List<String> accessoryTags) {
    }
}