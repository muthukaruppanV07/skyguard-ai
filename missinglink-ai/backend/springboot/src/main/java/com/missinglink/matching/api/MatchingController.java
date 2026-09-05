package com.missinglink.matching.api;

import com.missinglink.matching.MatchingService;
import com.missinglink.matching.domain.PotentialMatch;
import com.missinglink.matching.domain.VerificationRecord;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/matches")
public class MatchingController {

    private final MatchingService matchingService;

    public MatchingController(MatchingService matchingService) {
        this.matchingService = matchingService;
    }

    @GetMapping
    @PreAuthorize("hasAuthority('match:review')")
    public ResponseEntity<List<MatchView>> queue(@RequestParam(required = false) Long caseId) {
        return ResponseEntity.ok(matchingService.queue(caseId).stream()
                .map(MatchView::from).toList());
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAuthority('match:review')")
    public ResponseEntity<MatchDetail> detail(@PathVariable Long id) {
        PotentialMatch m = matchingService.detail(id);
        return ResponseEntity.ok(MatchDetail.from(m,
                matchingService.parseExplanation(m),
                matchingService.parseLimitations(m)));
    }

    @PatchMapping("/{id}/decision")
    @PreAuthorize("hasAuthority('match:review')")
    public ResponseEntity<MatchDetail> decide(@PathVariable Long id,
                                              @RequestBody MatchingService.DecisionRequest request) {
        PotentialMatch m = matchingService.decide(id, request);
        return ResponseEntity.ok(MatchDetail.from(m,
                matchingService.parseExplanation(m),
                matchingService.parseLimitations(m)));
    }

    public record MatchView(String id, String caseReference, String sightingReference,
                            double overallScore, String status, String createdAt,
                            String warning) {
        public static MatchView from(PotentialMatch m) {
            return new MatchView(String.valueOf(m.getId()),
                    m.getCaseRef() == null ? "" : m.getCaseRef().getCaseReference(),
                    m.getSighting() == null ? "" : m.getSighting().getSightingReference(),
                    m.getOverallScore(), m.getStatus().name(),
                    m.getCreatedAt() == null ? "" : m.getCreatedAt().toString(),
                    PotentialMatch.HUMAN_REVIEW_LABEL);
        }
    }

    public record MatchDetail(String id, String caseReference, String sightingReference,
                              double overallScore, String status, String reviewedBy,
                              String reviewNotes, List<String> explanation, List<String> limitations,
                              String warning) {
        public static MatchDetail from(PotentialMatch m, List<String> explanation, List<String> limits) {
            return new MatchDetail(String.valueOf(m.getId()),
                    m.getCaseRef() == null ? "" : m.getCaseRef().getCaseReference(),
                    m.getSighting() == null ? "" : m.getSighting().getSightingReference(),
                    m.getOverallScore(), m.getStatus().name(),
                    m.getReviewedBy() == null ? null : m.getReviewedBy().getFullName(),
                    m.getReviewNotes(), explanation, limits,
                    PotentialMatch.HUMAN_REVIEW_LABEL);
        }
    }
}