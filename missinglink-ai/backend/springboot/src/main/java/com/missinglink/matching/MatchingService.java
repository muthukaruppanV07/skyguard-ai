package com.missinglink.matching;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.missinglink.audit.AuditService;
import com.missinglink.cases.CaseAccessService;
import com.missinglink.cases.domain.MissingPersonCase;
import com.missinglink.common.ApiException;
import com.missinglink.matching.domain.PotentialMatch;
import com.missinglink.matching.domain.PotentialMatchRepository;
import com.missinglink.matching.domain.VerificationRecord;
import com.missinglink.matching.domain.VerificationRecordRepository;
import com.missinglink.notification.NotificationService;
import com.missinglink.security.SecurityUtils;
import com.missinglink.sighting.domain.Sighting;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * The AI lead queue. Every decision is audited, recorded in the verification history,
 * and reflected in the case timeline. Matches are ALWAYS framed as potential matches.
 */
@Service
public class MatchingService {

    private final PotentialMatchRepository matches;
    private final VerificationRecordRepository verifications;
    private final CaseAccessService access;
    private final NotificationService notifications;
    private final AuditService audit;
    private final ObjectMapper mapper = new ObjectMapper();

    public MatchingService(PotentialMatchRepository matches, VerificationRecordRepository verifications,
                           CaseAccessService access, NotificationService notifications, AuditService audit) {
        this.matches = matches;
        this.verifications = verifications;
        this.access = access;
        this.notifications = notifications;
        this.audit = audit;
    }

    @Transactional(readOnly = true)
    public List<PotentialMatch> queue(Long caseId) {
        if (caseId != null) {
            access.requireAccess(caseId);
        }
        return matches.awaitingReview();
    }

    @Transactional(readOnly = true)
    public PotentialMatch detail(Long matchId) {
        PotentialMatch m = matches.findById(matchId)
                .orElseThrow(() -> ApiException.notFound("Match not found"));
        access.requireAccess(m.getCaseRef().getId());
        return m;
    }

    @Transactional
    public PotentialMatch decide(Long matchId, DecisionRequest req) {
        PotentialMatch m = detail(matchId);
        if (req.decision() == null) {
            throw ApiException.badRequest("decision is required");
        }

        m.setStatus(mapDecisionToStatus(req.decision()));
        m.setReviewedBy(SecurityUtils.currentUser());
        m.setReviewedAt(Instant.now());
        m.setReviewNotes(req.notes());
        PotentialMatch saved = matches.save(m);

        VerificationRecord vr = new VerificationRecord();
        vr.setPotentialMatch(m);
        vr.setReviewer(SecurityUtils.currentUser());
        vr.setDecision(req.decision());
        vr.setNotes(req.notes());
        verifications.save(vr);

        // Keep case & sighting status in sync
        MissingPersonCase caseObj = m.getCaseRef();
        if (req.decision() == VerificationRecord.Decision.ACCEPT && m.getSighting() != null) {
            m.getSighting().setStatus(Sighting.Status.VERIFIED);
        } else if (req.decision() == VerificationRecord.Decision.REJECT && m.getSighting() != null) {
            m.getSighting().setStatus(Sighting.Status.REJECTED);
        } else if (req.decision() == VerificationRecord.Decision.DUPLICATE && m.getSighting() != null) {
            m.getSighting().setStatus(Sighting.Status.DUPLICATE);
        }

        // Timeline event (via case timeline append through a simple publisher)
        notifications.publishCaseEvent(caseObj, "match.decision",
                Map.of("matchId", saved.getId(), "decision", req.decision().name(),
                        "humanReview", true));

        // Case-level notification to the reporter when a lead is accepted.
        if (req.decision() == VerificationRecord.Decision.ACCEPT) {
            notifications.createForUser(caseObj.getReporter(), "match.accepted",
                    "A potential sighting was verified",
                    "Potentially significant lead accepted for case " + caseObj.getCaseReference()
                            + " — further verification required.", caseObj);
        }

        audit.record("match.decide", "potential_match", String.valueOf(saved.getId()),
                Map.of("decision", req.decision().name(), "notes", req.notes() == null ? "" : req.notes()));
        return saved;
    }

    private static PotentialMatch.Status mapDecisionToStatus(VerificationRecord.Decision d) {
        return switch (d) {
            case ACCEPT -> PotentialMatch.Status.ACCEPTED;
            case REJECT -> PotentialMatch.Status.REJECTED;
            case MORE_INFO -> PotentialMatch.Status.MORE_INFO;
            case DUPLICATE -> PotentialMatch.Status.DUPLICATE;
            case ESCALATE -> PotentialMatch.Status.ESCALATED;
        };
    }

    @Transactional(readOnly = true)
    public List<VerificationRecord> verificationHistory(Long matchId) {
        return verifications.findByPotentialMatchIdOrderByCreatedAtAsc(matchId);
    }

    public List<String> parseExplanation(PotentialMatch match) {
        if (match.getExplanation() == null) {
            return List.of();
        }
        try {
            return mapper.readValue(match.getExplanation(),
                    mapper.getTypeFactory().constructCollectionType(ArrayList.class, String.class));
        } catch (Exception e) {
            return List.of();
        }
    }

    public List<String> parseLimitations(PotentialMatch match) {
        if (match.getLimitations() == null) {
            return List.of();
        }
        try {
            return mapper.readValue(match.getLimitations(),
                    mapper.getTypeFactory().constructCollectionType(ArrayList.class, String.class));
        } catch (Exception e) {
            return List.of();
        }
    }

    public record DecisionRequest(VerificationRecord.Decision decision, String notes) {
    }
}