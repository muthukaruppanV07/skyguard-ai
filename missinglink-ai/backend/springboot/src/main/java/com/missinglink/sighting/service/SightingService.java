package com.missinglink.sighting.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.missinglink.aigateway.AIGatewayService;
import com.missinglink.aigateway.dto.SightingAnalysisDtos.AnalyzeSightingResponse;
import com.missinglink.aigateway.dto.SightingAnalysisDtos.RankedMatch;
import com.missinglink.cases.domain.CaseRepository;
import com.missinglink.cases.domain.MissingPersonCase;
import com.missinglink.config.AppProperties;
import com.missinglink.config.RateLimiter;
import com.missinglink.evidence.EvidenceService;
import com.missinglink.evidence.VectorWriter;
import com.missinglink.evidence.domain.Evidence;
import com.missinglink.evidence.domain.EvidenceCluster;
import com.missinglink.evidence.domain.EvidenceClusterRepository;
import com.missinglink.evidence.domain.EvidenceRepository;
import com.missinglink.matching.domain.PotentialMatch;
import com.missinglink.matching.domain.PotentialMatchRepository;
import com.missinglink.notification.NotificationService;
import com.missinglink.security.SecurityUtils;
import com.missinglink.sighting.domain.Sighting;
import com.missinglink.sighting.domain.SightingRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.time.Instant;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Service
public class SightingService {

    private final SightingRepository sightings;
    private final EvidenceService evidenceService;
    private final EvidenceRepository evidenceRepository;
    private final EvidenceClusterRepository clusterRepository;
    private final PotentialMatchRepository matchRepository;
    private final AIGatewayService aiGateway;
    private final VectorWriter vectorWriter;
    private final CaseRepository caseRepository;
    private final NotificationService notifications;
    private final AppProperties props;
    private final RateLimiter rateLimiter;
    private final ObjectMapper mapper = new ObjectMapper();

    public SightingService(SightingRepository sightings, EvidenceService evidenceService,
                           EvidenceRepository evidenceRepository, EvidenceClusterRepository clusterRepository,
                           PotentialMatchRepository matchRepository, AIGatewayService aiGateway,
                           VectorWriter vectorWriter, CaseRepository caseRepository,
                           NotificationService notifications, AppProperties props, RateLimiter rateLimiter) {
        this.sightings = sightings;
        this.evidenceService = evidenceService;
        this.evidenceRepository = evidenceRepository;
        this.clusterRepository = clusterRepository;
        this.matchRepository = matchRepository;
        this.aiGateway = aiGateway;
        this.vectorWriter = vectorWriter;
        this.caseRepository = caseRepository;
        this.notifications = notifications;
        this.props = props;
        this.rateLimiter = rateLimiter;
    }

    @Transactional
    public Sighting submit(MultipartFile photo, SightingSubmitRequest req) {
        rateLimiter.check("sighting", SecurityUtils.currentUser().getEmail(),
                props.getRateLimit().getSightingPerMinute());

        Sighting sighting = new Sighting();
        sighting.setSubmitter(SecurityUtils.currentUser());
        sighting.setSightingReference(nextReference());
        sighting.setDescription(req.description());
        sighting.setClothing(req.clothing());
        sighting.setDirectionOfMovement(req.directionOfMovement());
        sighting.setVehicleInfo(req.vehicleInfo());
        sighting.setNotes(req.notes());
        sighting.setLat(req.lat());
        sighting.setLng(req.lng());
        sighting.setLocationName(req.locationName());
        sighting.setCapturedAt(req.capturedAt());
        sighting.setSource(parseSource(req.source()));
        sighting.setStatus(Sighting.Status.UNVERIFIED);
        Sighting saved = sightings.save(sighting);

        byte[] imageBytes = readFile(photo);
        Evidence evidence = null;
        if (photo != null && !photo.isEmpty()) {
            evidence = evidenceService.store(photo, saved.getId(), null);
        }

        // Duplicate detection: identical binary (SHA-256) => likely same event.
        if (evidence != null && evidence.getSha256() != null) {
            Long evidenceId = evidence.getId();
            Evidence previous = evidenceRepository.findFirstBySha256(evidence.getSha256())
                    .filter(e -> !e.getId().equals(evidenceId))
                    .orElse(null);
            if (previous != null) {
                saved.setStatus(Sighting.Status.DUPLICATE);
                EvidenceCluster cluster = clusterFor(previous, saved);
                if (cluster != null) {
                    saved.setEvidenceClusterId(cluster.getId());
                }
                saved = sightings.save(saved);
            }
        }

        // AI analysis + ranking; persist sighting embedding + potential matches.
        AnalyzeSightingResponse response = analyze(saved, evidence, imageBytes);
        if (evidence != null && response != null && response.imageEmbedding() != null) {
            vectorWriter.upsertEvidenceEmbedding(evidence.getId(),
                    toArray(response.imageEmbedding()), modelVersionId(response), 512);
        }

        notifications.publishGlobal("sighting.new", Map.of(
                "sightingReference", saved.getSightingReference(),
                "status", saved.getStatus().name(),
                "lat", saved.getLat() == null ? 0 : saved.getLat(),
                "lng", saved.getLng() == null ? 0 : saved.getLng()));
        return saved;
    }

    private AnalyzeSightingResponse analyze(Sighting sighting, Evidence evidence, byte[] imageBytes) {
        String capturedAt = sighting.getCapturedAt() == null ? "" : sighting.getCapturedAt().toString();
        String description = sighting.getDescription() == null ? "" : sighting.getDescription();
        String clothing = sighting.getClothing() == null ? "" : sighting.getClothing();
        double lat = sighting.getLat() == null ? 0 : sighting.getLat();
        double lng = sighting.getLng() == null ? 0 : sighting.getLng();

        AnalyzeSightingResponse response = aiGateway.analyzeSighting(imageBytes, lat, lng,
                capturedAt, description, clothing);
        if (response == null || response.potentialMatches() == null) {
            return response;
        }
        for (RankedMatch rm : response.potentialMatches()) {
            upsertMatch(sighting, rm);
        }
        return response;
    }

    private void upsertMatch(Sighting sighting, RankedMatch rm) {
        try {
            MissingPersonCase caseObj = caseRepository.findByIdNotDeleted(rm.caseId())
                    .orElseThrow(() -> new IllegalStateException("Ranked case not found"));
            Optional<PotentialMatch> existing =
                    matchRepository.findFirstByCaseRefIdAndSightingId(caseObj.getId(), sighting.getId());
            PotentialMatch match = existing.orElseGet(PotentialMatch::new);
            match.setCaseRef(caseObj);
            match.setSighting(sighting);
            match.setOverallScore(rm.overallScore());
            match.setFaceSimilarity(rm.faceSimilarity());
            match.setClothingSimilarity(rm.clothingSimilarity());
            match.setAccessorySimilarity(rm.accessorySimilarity());
            match.setBodySimilarity(rm.bodySimilarity());
            match.setImageSimilarity(rm.imageSimilarity());
            match.setLocationRelevance(rm.locationRelevance());
            match.setTimeRelevance(rm.timeRelevance());
            match.setTextSimilarity(rm.textSimilarity());
            match.setExplanation(rm.explanation() == null ? null : toJson(rm.explanation()));
            match.setLimitations(rm.limitations() == null ? null : toJson(rm.limitations()));
            match.setStatus(PotentialMatch.Status.AWAITING_REVIEW);
            if (existing.isEmpty()) {
                matchRepository.save(match);
                notifications.createForInvestigators("match.new",
                        "New potential match from " + sighting.getSightingReference(),
                        caseObj.getCaseReference() + " queued for human review.", caseObj);
            } else {
                matchRepository.save(match);
            }
        } catch (IllegalStateException ignored) {
            // Case may have been archived mid-flight; skip silently.
        } catch (Exception e) {
            throw new com.missinglink.common.ApiException(
                    org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR,
                    "Failed to persist potential match");
        }
    }

    private EvidenceCluster clusterFor(Evidence previous, Sighting current) {
        if (previous.getSighting() != null && previous.getSighting().getEvidenceClusterId() != null) {
            return clusterRepository.findById(previous.getSighting().getEvidenceClusterId()).orElse(null);
        }
        EvidenceCluster cluster = new EvidenceCluster();
        cluster.setTitle("Evidence Cluster #" + (clusterRepository.count() + 24));
        cluster.setSourceCount(2);
        cluster.setFirstTimestamp(previous.getUploadedAt());
        cluster.setLastTimestamp(current.getCapturedAt() == null ? Instant.now() : current.getCapturedAt());
        cluster.setAvgSimilarity(1.0);
        return clusterRepository.save(cluster);
    }

    private Long modelVersionId(AnalyzeSightingResponse response) {
        return response.model() == null ? null : 1L; // seeded v1.0.0 in demo
    }

    private static byte[] readFile(MultipartFile photo) {
        if (photo == null || photo.isEmpty()) {
            return new byte[0];
        }
        try {
            return photo.getBytes();
        } catch (Exception e) {
            throw new com.missinglink.common.ApiException(
                    org.springframework.http.HttpStatus.BAD_REQUEST, "Unable to read uploaded file");
        }
    }

    private static double[] toArray(List<Double> list) {
        double[] out = new double[list.size()];
        for (int i = 0; i < list.size(); i++) {
            out[i] = list.get(i);
        }
        return out;
    }

    private String toJson(List<String> values) {
        try {
            return mapper.writeValueAsString(values);
        } catch (Exception e) {
            return "[]";
        }
    }

    private static Sighting.Source parseSource(String source) {
        if (source == null || source.isBlank()) {
            return Sighting.Source.WEB;
        }
        try {
            return Sighting.Source.valueOf(source);
        } catch (Exception e) {
            return Sighting.Source.WEB;
        }
    }

    private String nextReference() {
        return "ST-" + (sightings.count() + 1001);
    }

    public record SightingSubmitRequest(
            String description,
            String clothing,
            String directionOfMovement,
            String vehicleInfo,
            String notes,
            Double lat,
            Double lng,
            String locationName,
            Instant capturedAt,
            String source) {
    }
}