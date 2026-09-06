package com.missinglink;

import com.missinglink.cases.CaseService;
import com.missinglink.cases.domain.MissingPersonCase;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.time.temporal.ChronoUnit;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Emergency classification heuristic is configurable and must never make
 * medical or legal claims — it only ranks urgency for triage.
 */
class CaseClassificationTest {

    private static CaseService.CreateCaseRequest req(Integer age, Instant lastKnownAt,
                                                     boolean atRisk) {
        return new CaseService.CreateCaseRequest(
                "T", "First", "Last", age, "MALE", 160, null, null, null, null,
                null, null, null, lastKnownAt, 12.9, 77.6, true,
                atRisk, false, false);
    }

    @Test
    void recentChildMissingIsCritical() {
        CaseService.Classification c = CaseService.classify(
                req(9, Instant.now().minus(6, ChronoUnit.HOURS), false));
        assertThat(c.priority()).isEqualTo(MissingPersonCase.PriorityLevel.CRITICAL);
        assertThat(c.label()).doesNotContain("medical");
    }

    @Test
    void elderlyRecentIsHigh() {
        CaseService.Classification c = CaseService.classify(
                req(74, Instant.now().minus(30, ChronoUnit.HOURS), false));
        assertThat(c.priority()).isEqualTo(MissingPersonCase.PriorityLevel.HIGH);
    }

    @Test
    void atRiskIndicatorRaisesPriority() {
        CaseService.Classification noRisk = CaseService.classify(
                req(40, Instant.now().minus(50, ChronoUnit.HOURS), false));
        CaseService.Classification withRisk = CaseService.classify(
                req(40, Instant.now().minus(50, ChronoUnit.HOURS), true));
        assertThat(withRisk.priority().ordinal()).isGreaterThanOrEqualTo(noRisk.priority().ordinal());
        assertThat(withRisk.label()).isNotBlank();
    }

    @Test
    void oldCaseWithAdultIsStandard() {
        CaseService.Classification c = CaseService.classify(
                req(40, Instant.now().minus(10, ChronoUnit.DAYS), false));
        assertThat(c.priority()).isEqualTo(MissingPersonCase.PriorityLevel.STANDARD);
    }
}
