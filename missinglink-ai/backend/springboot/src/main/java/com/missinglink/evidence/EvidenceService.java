package com.missinglink.evidence;

import com.missinglink.audit.AuditService;
import com.missinglink.cases.domain.CaseRepository;
import com.missinglink.cases.domain.MissingPersonCase;
import com.missinglink.common.ApiException;
import com.missinglink.config.AppProperties;
import com.missinglink.evidence.domain.Evidence;
import com.missinglink.evidence.domain.Evidence.MalwareScanStatus;
import com.missinglink.evidence.domain.EvidenceRepository;
import com.missinglink.notification.NotificationService;
import com.missinglink.security.SecurityUtils;
import com.missinglink.sighting.domain.SightingRepository;
import com.missinglink.storage.SignedUrlService;
import com.missinglink.storage.StorageService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.ByteArrayInputStream;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Map;
import java.util.UUID;

/** Evidence intake pipeline: validation → checksum → malware scan → storage → DB. */
@Service
public class EvidenceService {

    private final EvidenceRepository evidenceRepository;
    private final StorageService storage;
    private final SignedUrlService signedUrls;
    private final FileValidationService fileValidation;
    private final SightingRepository sightingRepository;
    private final CaseRepository caseRepository;
    private final AppProperties props;
    private final AuditService audit;
    private final NotificationService notifications;

    public EvidenceService(EvidenceRepository evidenceRepository, StorageService storage,
                           SignedUrlService signedUrls, FileValidationService fileValidation,
                           SightingRepository sightingRepository, CaseRepository caseRepository,
                           AppProperties props, AuditService audit, NotificationService notifications) {
        this.evidenceRepository = evidenceRepository;
        this.storage = storage;
        this.signedUrls = signedUrls;
        this.fileValidation = fileValidation;
        this.sightingRepository = sightingRepository;
        this.caseRepository = caseRepository;
        this.props = props;
        this.audit = audit;
        this.notifications = notifications;
    }

    @Transactional
    public Evidence store(MultipartFile file, Long sightingId, Long caseId) {
        byte[] bytes;
        try {
            bytes = file.getBytes();
        } catch (Exception e) {
            throw ApiException.badRequest("Unable to read uploaded file");
        }

        // 1. Type + size validation (magic bytes, not the browser header)
        String sniffedMime = fileValidation.validate(bytes, file.getContentType());

        // 2. Checksum
        String sha256 = sha256(bytes);

        // 3. Malware scan hook
        MalwareScanStatus scan = fileValidation.scanForMalware(bytes, sniffedMime);

        // 4. Store
        String key = "evidence/" + UUID.randomUUID() + "-" + safeFilename(file.getOriginalFilename());
        storage.store(key, new ByteArrayInputStream(bytes), sniffedMime);

        // 5. DB record
        Evidence evidence = new Evidence();
        evidence.setSighting(sightingId == null ? null : sightingRepository.findById(sightingId)
                .orElseThrow(() -> ApiException.notFound("Sighting not found")));
        evidence.setCaseRef(caseId == null ? null : caseRepository.findByIdNotDeleted(caseId)
                .orElseThrow(() -> ApiException.notFound("Case not found")));
        evidence.setUploader(SecurityUtils.currentUser());
        evidence.setStorageKey(key);
        evidence.setOriginalFilename(file.getOriginalFilename());
        evidence.setContentType(sniffedMime);
        evidence.setSizeBytes((long) bytes.length);
        evidence.setSha256(sha256);
        evidence.setMalwareScanStatus(scan);
        Evidence saved = evidenceRepository.save(evidence);

        MissingPersonCase caseObj = evidence.getCaseRef();
        if (caseObj != null) {
            notifications.publishCaseEvent(caseObj, "evidence.added",
                    Map.of("evidenceId", saved.getId(), "status", scan.name()));
        }
        audit.record("evidence.upload", "evidence", String.valueOf(saved.getId()),
                Map.of("sha256", sha256, "scan", scan.name(), "bytes", bytes.length, "mime", sniffedMime));
        return saved;
    }

    @Transactional(readOnly = true)
    public Evidence require(Long id) {
        Evidence e = evidenceRepository.findById(id)
                .orElseThrow(() -> ApiException.notFound("Evidence not found"));
        audit.record("evidence.access", "evidence", String.valueOf(id), Map.of());
        return e;
    }

    public String signedUrl(Evidence evidence) {
        audit.record("evidence.download", "evidence", String.valueOf(evidence.getId()), Map.of());
        return signedUrls.create(evidence.getStorageKey(), props.getStorage().getSignedUrlExpireMinutes());
    }

    private static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (Exception e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    private static String safeFilename(String name) {
        if (name == null) return "file.bin";
        return name.replaceAll("[^a-zA-Z0-9._-]", "_");
    }
}