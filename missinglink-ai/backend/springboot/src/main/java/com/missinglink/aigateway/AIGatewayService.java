package com.missinglink.aigateway;

import com.missinglink.aigateway.dto.AiDtos.AnalyzeImageResponse;
import com.missinglink.aigateway.dto.FaceMatchDtos.FaceMatchResponse;
import com.missinglink.aigateway.dto.SightingAnalysisDtos;
import com.missinglink.common.ApiException;
import com.missinglink.config.AppProperties;
import com.missinglink.storage.StorageService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.io.IOException;
import java.io.InputStream;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Optional;

/**
 * The AI Gateway — the ONLY entry point between the backend and the FastAPI AI
 * service. Every call carries the server-side API key; browsers never touch it.
 */
@Service
public class AIGatewayService {

    private static final Logger log = LoggerFactory.getLogger(AIGatewayService.class);

    private final AppProperties props;
    private final StorageService storage;
    private final RestClient client;

    public AIGatewayService(AppProperties props, StorageService storage) {
        this.props = props;
        this.storage = storage;
        HttpClient http = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(10))
                .build();
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(http);
        this.client = RestClient.builder()
                .requestFactory(factory)
                .baseUrl(props.getAi().getServiceUrl())
                .defaultHeader("X-API-Key", props.getAi().getApiKey())
                .build();
    }

    /** Forward an evidence file to the FastAPI vision pipeline. */
    public AnalyzeImageResponse analyzeImage(String storageKey) {
        byte[] bytes = loadBytes(storageKey);
        try {
            MultiValueMap<String, Object> form = multipart("file", fileNameOf(storageKey), bytes);
            return client.post()
                    .uri("/analyze/analyze-image")
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(form)
                    .retrieve()
                    .body(AnalyzeImageResponse.class);
        } catch (ResourceAccessException e) {
            return fallbackImage(bytes);
        } catch (Exception e) {
            log.warn("AI analyze-image failed: {}", e.getMessage());
            if (props.getAi().isFallbackAllowed()) {
                return fallbackImage(bytes);
            }
            throw ApiException.badGateway("AI service unavailable");
        }
    }

    /**
     * Rank a sighting against active case profiles. imageBytes may be empty for
     * text/location/time-only ranking.
     */
    public SightingAnalysisDtos.AnalyzeSightingResponse analyzeSighting(
            byte[] imageBytes, double lat, double lng, String capturedAt,
            String description, String clothing) {
        SightingAnalysisDtos.AnalyzeSightingRequest request = new SightingAnalysisDtos.AnalyzeSightingRequest(
                lat, lng, capturedAt, description, clothing,
                imageBytes.length == 0 ? "" : Base64.getEncoder().encodeToString(imageBytes),
                props.getMatching().getWeights(),
                props.getMatching().getGeoRadiusKm(),
                props.getMatching().getTimeDecayHours(),
                props.getMatching().getMinOverallScore());
        try {
            return client.post()
                    .uri("/analyze/sighting")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .body(SightingAnalysisDtos.AnalyzeSightingResponse.class);
        } catch (ResourceAccessException e) {
            return fallbackSighting(request);
        } catch (Exception e) {
            log.warn("AI analyze-sighting failed: {}", e.getMessage());
            if (!props.getAi().isFallbackAllowed()) {
                throw ApiException.badGateway("AI service unavailable");
            }
            return fallbackSighting(request);
        }
    }

    /** Location/time/text-only local fallback so the queue stays live when AI is down. */
    private SightingAnalysisDtos.AnalyzeSightingResponse fallbackSighting(
            SightingAnalysisDtos.AnalyzeSightingRequest request) {
        return new SightingAnalysisDtos.AnalyzeSightingResponse(
                new SightingAnalysisDtos.EvidenceSummary(0.5, List.of("ai-unavailable"), false,
                        List.of(), List.of()),
                List.of(), null, "local-fallback/v1",
                "AI service unreachable — visual matching unavailable. Location/time signals only.");
    }

    /**
     * Rank a photo of a person against active case profiles by face/appearance.
     * Returns the raw AI result; harmless when the AI service is unreachable.
     */
    public FaceMatchResponse photoMatch(byte[] bytes) {
        try {
            MultiValueMap<String, Object> form = multipart("file", "photo.jpg", bytes);
            return client.post()
                    .uri("/v1/face-match")
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(form)
                    .retrieve()
                    .body(FaceMatchResponse.class);
        } catch (ResourceAccessException e) {
            return fallbackFaceMatch();
        } catch (Exception e) {
            log.warn("AI face-match failed: {}", e.getMessage());
            if (!props.getAi().isFallbackAllowed()) {
                throw ApiException.badGateway("AI service unavailable");
            }
            return fallbackFaceMatch();
        }
    }

    /** Multipart form whose values are real file parts (filename + image content type). */
    private static MultiValueMap<String, Object> multipart(String field, String filename, byte[] bytes) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add(field, new ByteArrayResource(bytes) {
            @Override
            public String getFilename() {
                return filename;
            }
        });
        return form;
    }

    private static com.missinglink.aigateway.dto.FaceMatchDtos.FaceMatchResponse fallbackFaceMatch() {
        return new com.missinglink.aigateway.dto.FaceMatchDtos.FaceMatchResponse(
                false, 0.0, List.of("ai-unavailable"), List.of(),
                "local-fallback/v1", 0.35, 0L,
                "AI service unreachable — face matching is unavailable right now.");
    }

    private byte[] loadBytes(String storageKey) {
        Optional<InputStream> streamOpt = storage.load(storageKey);
        if (streamOpt.isEmpty()) {
            throw ApiException.notFound("Evidence file not found in storage");
        }
        try (InputStream in = streamOpt.get()) {
            return in.readAllBytes();
        } catch (IOException e) {
            throw ApiException.internal("Failed to read evidence file");
        }
    }

    private AnalyzeImageResponse fallbackImage(byte[] bytes) {
        long started = System.currentTimeMillis();
        double[] embedding = LocalFallbackAnalyzer.embeddingFrom(bytes, 512);
        return new AnalyzeImageResponse(true, LocalFallbackAnalyzer.MODEL,
                LocalFallbackAnalyzer.quality(bytes.length),
                List.of("fallback-model-in-use"), false,
                new com.missinglink.aigateway.dto.AiDtos.FaceInfo(0.0, 0, 0, 0, 0, new double[0]),
                null, toBoxed(embedding), List.of(), List.of(), 512,
                System.currentTimeMillis() - started);
    }

    private static String fileNameOf(String key) {
        return key == null ? "file.bin" : key.substring(key.lastIndexOf('/') + 1);
    }

    private static List<Double> toBoxed(double[] arr) {
        List<Double> out = new ArrayList<>(arr.length);
        for (double d : arr) {
            out.add(d);
        }
        return out;
    }
}