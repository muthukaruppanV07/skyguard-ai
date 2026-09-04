package com.missinglink.cases.api;

import com.missinglink.cases.CaseService;
import com.missinglink.cases.domain.MissingPersonCase;
import com.missinglink.security.SecurityUtils;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.time.Instant;
import java.util.List;

@RestController
@RequestMapping("/api/v1/cases")
public class CaseController {

    private final CaseService caseService;

    public CaseController(CaseService caseService) {
        this.caseService = caseService;
    }

    @PostMapping
    @PreAuthorize("hasAuthority('case:create')")
    public ResponseEntity<CaseCreated> create(@RequestBody CaseService.CreateCaseRequest request) {
        MissingPersonCase c = caseService.create(request);
        return ResponseEntity.ok(new CaseCreated(String.valueOf(c.getId()), c.getCaseReference(),
                c.getStatus().name(), c.getPriorityLevel().name(), c.getEmergencyClassification()));
    }

    @GetMapping("/public")
    public ResponseEntity<List<CaseSummary>> publicCases() {
        return ResponseEntity.ok(caseService.publicCases().stream().map(CaseSummary::from).toList());
    }

    @GetMapping
    public ResponseEntity<List<CaseSummary>> myCases() {
        String role = SecurityUtils.currentUser().getRole().getName();
        List<MissingPersonCase> cases = ("INVESTIGATOR".equals(role) || "ADMIN".equals(role))
                ? caseService.listing()
                : caseService.forReporter(SecurityUtils.currentUserId());
        return ResponseEntity.ok(cases.stream().map(CaseSummary::from).toList());
    }

    @GetMapping("/{id}")
    public ResponseEntity<CaseDetail> detail(@PathVariable Long id) {
        MissingPersonCase c = caseService.getForCurrentUser(id);
        return ResponseEntity.ok(CaseDetail.from(c, caseService.getProfileView(id), caseService.getTimeline(id)));
    }

    @PatchMapping("/{id}")
    @PreAuthorize("hasAuthority('case:update')")
    public ResponseEntity<CaseDetail> update(@PathVariable Long id, @RequestBody CaseService.CreateCaseRequest request) {
        MissingPersonCase c = caseService.update(id, request);
        return ResponseEntity.ok(CaseDetail.from(c, caseService.getProfileView(id), caseService.getTimeline(id)));
    }

    @PostMapping("/{id}/photos")
    @PreAuthorize("hasAuthority('photo:upload')")
    public ResponseEntity<PhotoUploaded> uploadPhoto(@PathVariable Long id,
                                                     @RequestParam("file") MultipartFile file,
                                                     @RequestParam(value = "type", defaultValue = "FRONT_FACE") String type) {
        caseService.uploadAuthorizedPhoto(id, file, type);
        return ResponseEntity.ok(new PhotoUploaded(true, "Authorized photo accepted for AI analysis"));
    }

    @PostMapping("/{id}/status")
    @PreAuthorize("hasAuthority('case:status')")
    public ResponseEntity<Void> changeStatus(@PathVariable Long id, @RequestBody StatusRequest request) {
        caseService.changeStatus(id, MissingPersonCase.Status.valueOf(request.status()), request.note());
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/{id}/timeline")
    public ResponseEntity<List<CaseService.TimelineView>> timeline(@PathVariable Long id) {
        caseService.getForCurrentUser(id);
        return ResponseEntity.ok(caseService.getTimeline(id));
    }

    public record StatusRequest(String status, String note) {
    }

    public record CaseCreated(String id, String caseReference, String status, String priority,
                              String emergencyClassification) {
    }

    public record PhotoUploaded(boolean accepted, String message) {
    }

    public record CaseSummary(String id, String caseReference, String status, String priority,
                              String firstName, String lastName, Integer age, String gender,
                              String lastKnownPlace, Instant lastKnownAt, Boolean isPublic,
                              Double lastKnownLat, Double lastKnownLng, Instant createdAt) {
        public static CaseSummary from(MissingPersonCase c) {
            return new CaseSummary(String.valueOf(c.getId()), c.getCaseReference(), c.getStatus().name(),
                    c.getPriorityLevel().name(), c.getFirstName(), c.getLastName(), c.getAge(), c.getGender(),
                    c.getLastKnownPlace(), c.getLastKnownAt(), c.isPublic(), c.getLastKnownLat(),
                    c.getLastKnownLng(), c.getCreatedAt());
        }
    }

    public record CaseDetail(String id, String caseReference, String status, String priority,
                             String emergencyClassification, String firstName, String lastName,
                             Integer age, String gender, Integer heightCm, String identificationMarks,
                             String languages, String lastKnownPlace, Instant lastKnownAt,
                             Double lastKnownLat, Double lastKnownLng, String description,
                             boolean isPublic, List<CaseService.TimelineView> timeline,
                             CaseService.ProfileView profile, List<String> photos) {
        public static CaseDetail from(MissingPersonCase c, CaseService.ProfileView profile,
                                      List<CaseService.TimelineView> timeline) {
            return new CaseDetail(String.valueOf(c.getId()), c.getCaseReference(), c.getStatus().name(),
                    c.getPriorityLevel().name(), c.getEmergencyClassification(), c.getFirstName(),
                    c.getLastName(), c.getAge(), c.getGender(), c.getHeightCm(), c.getIdentificationMarks(),
                    c.getLanguages(), c.getLastKnownPlace(), c.getLastKnownAt(), c.getLastKnownLat(),
                    c.getLastKnownLng(), c.getDescription(), c.isPublic(), timeline, profile,
                    List.of());
        }
    }
}