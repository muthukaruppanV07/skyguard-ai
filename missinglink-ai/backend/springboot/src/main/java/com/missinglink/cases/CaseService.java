package com.missinglink.cases;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.missinglink.aigateway.AIGatewayService;
import com.missinglink.aigateway.dto.AiDtos.AnalyzeImageResponse;
import com.missinglink.cases.domain.*;
import com.missinglink.common.ApiException;
import com.missinglink.evidence.EvidenceService;
import com.missinglink.evidence.VectorWriter;
import com.missinglink.evidence.domain.Evidence;
import com.missinglink.evidence.domain.EvidenceRepository;
import com.missinglink.notification.NotificationService;
import com.missinglink.security.SecurityUtils;
import com.missinglink.user.User;
import com.missinglink.user.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Case lifecycle: multi-step wizard, emergency classification heuristic, AI profile, timeline. */
@Service
public class CaseService {

    private final CaseRepository caseRepository;
    private final PersonProfileRepository profileRepository;
    private final CaseTimelineRepository timelineRepository;
    private final AuthorizedPhotoRepository photoRepository;
    private final UserRepository userRepository;
    private final CaseAccessService access;
    private final NotificationService notifications;
    private final EvidenceService evidenceService;
    private final EvidenceRepository evidenceRepository;
    private final AIGatewayService aiGateway;
    private final VectorWriter vectorWriter;
    private final ObjectMapper mapper = new ObjectMapper();

    public CaseService(CaseRepository caseRepository, PersonProfileRepository profileRepository,
                       CaseTimelineRepository timelineRepository, AuthorizedPhotoRepository photoRepository,
                       UserRepository userRepository, CaseAccessService access,
                       NotificationService notifications, EvidenceService evidenceService,
                       EvidenceRepository evidenceRepository, AIGatewayService aiGateway,
                       VectorWriter vectorWriter) {
        this.caseRepository = caseRepository;
        this.profileRepository = profileRepository;
        this.timelineRepository = timelineRepository;
        this.photoRepository = photoRepository;
        this.userRepository = userRepository;
        this.access = access;
        this.notifications = notifications;
        this.evidenceService = evidenceService;
        this.evidenceRepository = evidenceRepository;
        this.aiGateway = aiGateway;
        this.vectorWriter = vectorWriter;
    }

    @Transactional
    public MissingPersonCase create(CreateCaseRequest req) {
        User reporter = SecurityUtils.currentUser();
        MissingPersonCase c = new MissingPersonCase();
        c.setCaseReference(nextReference());
        c.setReporter(reporter);
        c.setStatus(MissingPersonCase.Status.OPEN);
        c.setTitle(req.title());
        c.setFirstName(req.firstName());
        c.setLastName(req.lastName());
        c.setAge(req.age());
        c.setGender(req.gender());
        c.setHeightCm(req.heightCm());
        c.setIdentificationMarks(req.identificationMarks());
        c.setLanguages(req.languages());
        c.setLastKnownActivity(req.lastKnownActivity());
        c.setTransportation(req.transportation());
        c.setPossibleDestinations(req.possibleDestinations());
        c.setDescription(req.description());
        c.setLastKnownPlace(req.lastKnownPlace());
        c.setLastKnownAt(req.lastKnownAt());
        c.setLastKnownLat(req.lastKnownLat());
        c.setLastKnownLng(req.lastKnownLng());
        c.setPublic(Boolean.TRUE.equals(req.isPublic()));

        Classification cls = classify(req);
        c.setPriorityLevel(cls.priority());
        c.setEmergencyClassification(cls.label());

        MissingPersonCase saved = caseRepository.save(c);

        appendAuditTrail(saved, "CASE_CREATED",
                "Case " + saved.getCaseReference() + " reported.",
                Map.of("reference", saved.getCaseReference()));
        notifications.createForUsers(access.investigatorsAndAdmins(), "case.new",
                "New missing-person case",
                saved.getCaseReference() + " reported by " + reporter.getFullName(), saved);
        return saved;
    }

    @Transactional(readOnly = true)
    public MissingPersonCase getForCurrentUser(Long caseId) {
        return access.requireAccess(caseId);
    }

    @Transactional
    public MissingPersonCase update(Long caseId, CreateCaseRequest patch) {
        MissingPersonCase c = access.requireAccess(caseId);
        if (patch.firstName() != null) c.setFirstName(patch.firstName());
        if (patch.lastName() != null) c.setLastName(patch.lastName());
        if (patch.age() != null) c.setAge(patch.age());
        if (patch.gender() != null) c.setGender(patch.gender());
        if (patch.heightCm() != null) c.setHeightCm(patch.heightCm());
        if (patch.identificationMarks() != null) c.setIdentificationMarks(patch.identificationMarks());
        if (patch.languages() != null) c.setLanguages(patch.languages());
        if (patch.lastKnownActivity() != null) c.setLastKnownActivity(patch.lastKnownActivity());
        if (patch.transportation() != null) c.setTransportation(patch.transportation());
        if (patch.possibleDestinations() != null) c.setPossibleDestinations(patch.possibleDestinations());
        if (patch.description() != null) c.setDescription(patch.description());
        if (patch.lastKnownPlace() != null) c.setLastKnownPlace(patch.lastKnownPlace());
        if (patch.lastKnownAt() != null) c.setLastKnownAt(patch.lastKnownAt());
        if (patch.lastKnownLat() != null) c.setLastKnownLat(patch.lastKnownLat());
        if (patch.lastKnownLng() != null) c.setLastKnownLng(patch.lastKnownLng());
        MissingPersonCase saved = caseRepository.save(c);
        appendAuditTrail(saved, "CASE_UPDATED", "Case details updated.");
        return saved;
    }

    @Transactional
    public void changeStatus(Long caseId, MissingPersonCase.Status status, String note) {
        MissingPersonCase c = access.requireAccess(caseId);
        c.setStatus(status);
        if (status == MissingPersonCase.Status.LOCATED || status == MissingPersonCase.Status.CLOSED) {
            c.setResolvedAt(Instant.now());
        }
        caseRepository.save(c);
        String message = "Status changed to " + status + (note == null || note.isBlank() ? "" : " — " + note);
        appendAuditTrail(c, "STATUS_CHANGED", message);
        notifications.publishCaseEvent(c, "case.status.changed", Map.of("status", status.name()));
    }

    @Transactional
    public PersonProfile getOrGenerateProfile(Long caseId) {
        return profileRepository.findByCaseRefId(caseId)
                .map(p -> p)
                .orElseGet(() -> {
                    MissingPersonCase c = access.requireAccess(caseId);
                    PersonProfile p = new PersonProfile();
                    p.setCaseRef(c);
                    p.setSearchableText(c.getFirstName() + " " + safe(c.getLastName()) + " "
                            + safe(c.getGender()) + " " + safe(String.valueOf(c.getAge())) + " years "
                            + safe(String.valueOf(c.getHeightCm())) + " cm " + safe(c.getIdentificationMarks())
                            + " " + safe(c.getLastKnownPlace()));
                    PersonProfile saved = profileRepository.save(p);
                    appendAuditTrail(c, "PROFILE_GENERATED",
                            "AI-assisted searchable profile generated.", Map.of("profileId", saved.getId()));
                    return saved;
                });
    }

    public void appendAuditTrail(MissingPersonCase c, String eventType, String description) {
        appendAuditTrail(c, eventType, description, Map.of());
    }

    public void appendAuditTrail(MissingPersonCase c, String eventType, String description,
                                 Map<String, Object> payload) {
        CaseTimeline t = new CaseTimeline();
        t.setCaseRef(c);
        try {
            t.setActor(SecurityUtils.currentUser());
        } catch (Exception e) {
            t.setActor(null);
        }
        t.setEventType(eventType);
        t.setDescription(description);
        t.setPayload(toJson(payload));
        timelineRepository.save(t);
    }

    /** Configurable emergency classification — an aid only, never a medical/legal conclusion. */
    public static Classification classify(CreateCaseRequest req) {
        int score = 0;
        Instant now = Instant.now();
        if (req.lastKnownAt() != null) {
            long hours = Duration.between(req.lastKnownAt(), now).toHours();
            if (hours <= 24) score += 3;
            else if (hours <= 72) score += 2;
            else score += 1;
        }
        Integer age = req.age();
        if (age != null && age < 13) score += 3;
        else if (age != null && age >= 60) score += 2;

        boolean atRisk = Boolean.TRUE.equals(req.potentialMentalHealth())
                || Boolean.TRUE.equals(req.medicalCondition())
                || Boolean.TRUE.equals(req.atRiskAdulthood());
        if (atRisk) score += 2;

        if (score >= 6) {
            return new Classification(MissingPersonCase.PriorityLevel.CRITICAL, "At-risk person — high priority");
        }
        if (score >= 4) {
            return new Classification(MissingPersonCase.PriorityLevel.HIGH, "At-risk person — priority");
        }
        return new Classification(MissingPersonCase.PriorityLevel.STANDARD, "Standard — monitor");
    }

    @Transactional(readOnly = true)
    public List<MissingPersonCase> listing() {
        return caseRepository.findActiveCases();
    }

    @Transactional(readOnly = true)
    public List<MissingPersonCase> forReporter(Long reporterId) {
        return caseRepository.findByReporterIdAndDeletedAtIsNull(reporterId);
    }

    @Transactional(readOnly = true)
    public List<MissingPersonCase> publicCases() {
        return caseRepository.findByStatusInAndIsPublicTrueAndDeletedAtIsNull(
                List.of(MissingPersonCase.Status.OPEN, MissingPersonCase.Status.ACTIVE));
    }

    private String nextReference() {
        long next = caseRepository.count() + 101;
        return "MP-" + next;
    }

    /** Timeline as a plain view (avoids lazy entity serialization). */
    @Transactional(readOnly = true)
    public List<TimelineView> getTimeline(Long caseId) {
        return timelineRepository.findByCaseRefIdOrderByCreatedAtAsc(caseId).stream()
                .map(t -> new TimelineView(t.getId(), t.getEventType(), t.getDescription(),
                        t.getPayload(), t.getActor() == null ? null : t.getActor().getFullName(),
                        t.getCreatedAt()))
                .toList();
    }

    /** Profile without lazy entity references / embedding vector. */
    @Transactional(readOnly = true)
    public ProfileView getProfileView(Long caseId) {
        PersonProfile p = getOrGenerateProfile(caseId);
        return new ProfileView(p.getId(), p.getHair(), p.getEyes(), p.getSkinTone(), p.getClothing(),
                p.getAccessories(), p.getBackpack(), p.getShoes(), p.getOtherCharacteristics(),
                p.getEmbeddingModel());
    }

    /** Upload an authorized photo, run vision analysis, fold its embedding into the case profile. */
    @Transactional
    public void uploadAuthorizedPhoto(Long caseId, MultipartFile file, String type) {
        MissingPersonCase c = access.requireAccess(caseId);
        Evidence evidence = evidenceService.store(file, null, caseId);
        AuthorizedPhoto photo = new AuthorizedPhoto();
        photo.setCaseRef(c);
        photo.setUploader(SecurityUtils.currentUser());
        photo.setStorageKey(evidence.getStorageKey());
        photo.setPhotoType(parsePhotoType(type));
        photoRepository.save(photo);

        // Vision analysis → embedding (non-fatal when AI service is unavailable).
        try {
            AnalyzeImageResponse result = aiGateway.analyzeImage(evidence.getStorageKey());
            if (result != null && result.embedding() != null && !result.embedding().isEmpty()) {
                vectorWriter.upsertEvidenceEmbedding(evidence.getId(),
                        toArray(result.embedding()), null, 512);
                recomputeProfileEmbedding(c.getId());
            }
        } catch (Exception e) {
            // photo stored; enrichment continues when AI is available.
        }
        appendAuditTrail(c, "PHOTO_UPLOADED", "Authorized photo uploaded (" + type + ").");
    }

    private void recomputeProfileEmbedding(Long caseId) {
        List<double[]> vectors = vectorWriter.embeddingsForCase(caseId);
        if (vectors.isEmpty()) {
            return;
        }
        double[] mean = VectorWriter.mean(vectors.toArray(double[][]::new));
        vectorWriter.upsertProfileEmbedding(caseId, mean, "analysis/v1");
    }

    private static AuthorizedPhoto.PhotoType parsePhotoType(String type) {
        try {
            return AuthorizedPhoto.PhotoType.valueOf(type);
        } catch (Exception e) {
            return AuthorizedPhoto.PhotoType.FRONT_FACE;
        }
    }

    private static double[] toArray(List<Double> list) {
        double[] out = new double[list.size()];
        for (int i = 0; i < list.size(); i++) {
            out[i] = list.get(i);
        }
        return out;
    }

    private static String safe(String s) {
        return s == null ? "" : s;
    }

    private static String toJson(Map<String, Object> map) {
        try {
            return new ObjectMapper().writeValueAsString(map);
        } catch (Exception e) {
            return "{}";
        }
    }

    public record Classification(MissingPersonCase.PriorityLevel priority, String label) {
    }

    public record TimelineView(Long id, String eventType, String description, String payload,
                               String actorName, Instant createdAt) {
    }

    public record ProfileView(Long id, String hair, String eyes, String skinTone, String clothing,
                              String accessories, String backpack, String shoes,
                              String otherCharacteristics, String embeddingModel) {
    }

    public record CreateCaseRequest(
            String title, String firstName, String lastName, Integer age, String gender, Integer heightCm,
            String identificationMarks, String languages,
            String lastKnownActivity, String transportation, String possibleDestinations, String description,
            String lastKnownPlace, Instant lastKnownAt, Double lastKnownLat, Double lastKnownLng,
            Boolean isPublic, Boolean potentialMentalHealth, Boolean medicalCondition, Boolean atRiskAdulthood) {
    }
}