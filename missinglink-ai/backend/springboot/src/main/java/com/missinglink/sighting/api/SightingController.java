package com.missinglink.sighting.api;

import com.missinglink.sighting.domain.Sighting;
import com.missinglink.sighting.domain.SightingRepository;
import com.missinglink.sighting.service.SightingService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/api/v1/sightings")
public class SightingController {

    private final SightingService sightingService;
    private final SightingRepository sightings;

    public SightingController(SightingService sightingService, SightingRepository sightings) {
        this.sightingService = sightingService;
        this.sightings = sightings;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @PreAuthorize("hasAuthority('sighting:submit')")
    public ResponseEntity<SightingOutcome> submit(
            @RequestParam(value = "photo", required = false) MultipartFile photo,
            @RequestParam(value = "description", required = false) String description,
            @RequestParam(value = "clothing", required = false) String clothing,
            @RequestParam(value = "directionOfMovement", required = false) String direction,
            @RequestParam(value = "vehicleInfo", required = false) String vehicleInfo,
            @RequestParam(value = "notes", required = false) String notes,
            @RequestParam(value = "lat", required = false) Double lat,
            @RequestParam(value = "lng", required = false) Double lng,
            @RequestParam(value = "locationName", required = false) String locationName,
            @RequestParam(value = "capturedAt", required = false) String capturedAt,
            @RequestParam(value = "source", required = false) String source) {

        java.time.Instant captured = capturedAt == null || capturedAt.isBlank()
                ? null : java.time.Instant.parse(capturedAt);
        SightingService.SightingSubmitRequest request = new SightingService.SightingSubmitRequest(
                description, clothing, direction, vehicleInfo, notes, lat, lng, locationName,
                captured, source);
        Sighting saved = sightingService.submit(photo, request);
        return ResponseEntity.ok(new SightingOutcome(saved.getSightingReference(), saved.getStatus().name(),
                saved.getEvidenceClusterId()));
    }

    @GetMapping
    @PreAuthorize("hasAuthority('sighting:read')")
    public ResponseEntity<List<SightingView>> list(@RequestParam(required = false) Long caseId) {
        List<Sighting> rows = caseId == null ? sightings.findAll()
                : sightings.findByCaseIdOrdered(caseId);
        return ResponseEntity.ok(rows.stream().map(SightingView::from).toList());
    }

    @PatchMapping("/{id}/status")
    @PreAuthorize("hasAuthority('sighting:review')")
    public ResponseEntity<Void> updateStatus(@PathVariable Long id, @RequestBody StatusUpdate update) {
        Sighting s = sightings.findById(id)
                .orElseThrow(() -> new com.missinglink.common.ApiException(
                        org.springframework.http.HttpStatus.NOT_FOUND, "Sighting not found"));
        s.setStatus(Sighting.Status.valueOf(update.status()));
        sightings.save(s);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/clusters")
    @PreAuthorize("hasAuthority('sighting:read')")
    public ResponseEntity<List<Object[]>> clusters() {
        // Evidence-cluster summary is exposed via the geo map endpoint for authorized users.
        return ResponseEntity.ok(List.of());
    }

    public record SightingOutcome(String sightingReference, String status, Long evidenceClusterId) {
    }

    public record StatusUpdate(String status) {
    }

    public record SightingView(String id, String sightingReference, String caseReference, String status,
                               String description, String clothing, String locationName,
                               Double lat, Double lng, java.time.Instant capturedAt,
                               java.time.Instant reportedAt) {
        public static SightingView from(Sighting s) {
            return new SightingView(String.valueOf(s.getId()), s.getSightingReference(),
                    s.getCaseRef() == null ? null : String.valueOf(s.getCaseRef().getId()),
                    s.getStatus().name(), s.getDescription(), s.getClothing(), s.getLocationName(),
                    s.getLat(), s.getLng(), s.getCapturedAt(), s.getReportedAt());
        }
    }
}