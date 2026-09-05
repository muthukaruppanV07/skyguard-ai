package com.missinglink.evidence.api;

import com.missinglink.aigateway.AIGatewayService;
import com.missinglink.aigateway.dto.AiDtos.AnalyzeImageResponse;
import com.missinglink.evidence.EvidenceService;
import com.missinglink.evidence.domain.Evidence;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.time.Instant;

@RestController
@RequestMapping("/api/v1/evidence")
public class EvidenceController {

    private final EvidenceService evidenceService;
    private final AIGatewayService aiGateway;

    public EvidenceController(EvidenceService evidenceService, AIGatewayService aiGateway) {
        this.evidenceService = evidenceService;
        this.aiGateway = aiGateway;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @PreAuthorize("hasAuthority('evidence:upload')")
    public ResponseEntity<EvidenceView> upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "sightingId", required = false) Long sightingId,
            @RequestParam(value = "caseId", required = false) Long caseId) {
        Evidence e = evidenceService.store(file, sightingId, caseId);
        return ResponseEntity.ok(EvidenceView.from(e));
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAuthority('evidence:read')")
    public ResponseEntity<EvidenceView> detail(@PathVariable Long id) {
        return ResponseEntity.ok(EvidenceView.from(evidenceService.require(id)));
    }

    @GetMapping("/{id}/url")
    @PreAuthorize("hasAuthority('evidence:download')")
    public ResponseEntity<SignedUrlResponse> signedUrl(@PathVariable Long id) {
        Evidence e = evidenceService.require(id);
        return ResponseEntity.ok(new SignedUrlResponse(evidenceService.signedUrl(e),
                e.getContentType(), e.getSizeBytes()));
    }

    @GetMapping("/{id}/analysis")
    @PreAuthorize("hasAuthority('evidence:read')")
    public ResponseEntity<AnalyzeImageResponse> analysis(@PathVariable Long id) {
        Evidence e = evidenceService.require(id);
        return ResponseEntity.ok(aiGateway.analyzeImage(e.getStorageKey()));
    }

    public record EvidenceView(String id, String sightingReference, String caseReference, String storageKey,
                               String originalFilename, String contentType, Long sizeBytes, String sha256,
                               String malwareScanStatus, Double qualityScore, Instant uploadedAt) {
        public static EvidenceView from(Evidence e) {
            return new EvidenceView(String.valueOf(e.getId()),
                    e.getSighting() == null ? null : e.getSighting().getSightingReference(),
                    e.getCaseRef() == null ? null : e.getCaseRef().getCaseReference(),
                    e.getStorageKey(), e.getOriginalFilename(), e.getContentType(), e.getSizeBytes(),
                    e.getSha256(), e.getMalwareScanStatus().name(), e.getQualityScore(), e.getUploadedAt());
        }
    }

    public record SignedUrlResponse(String url, String contentType, Long sizeBytes) {
    }
}