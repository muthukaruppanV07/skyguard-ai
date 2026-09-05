package com.missinglink.search;

import com.missinglink.cases.domain.CaseRepository;
import com.missinglink.cases.domain.MissingPersonCase;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Combined case search: full-text keyword (profile digest), filters (status, age range,
 * priority), and geospatial distance ordering. Vector search is handled by the AI
 * service via pgvector; this is the structured/relational search surface.
 */
@Service
public class SearchService {

    private final CaseRepository caseRepository;

    public SearchService(CaseRepository caseRepository) {
        this.caseRepository = caseRepository;
    }

    @Transactional(readOnly = true)
    public List<MissingPersonCase> searchCases(SearchQuery req) {
        List<MissingPersonCase> all = req.publicOnly()
                ? caseRepository.findByStatusInAndIsPublicTrueAndDeletedAtIsNull(
                        List.of(MissingPersonCase.Status.OPEN, MissingPersonCase.Status.ACTIVE))
                : caseRepository.findActiveCases();

        String q = req.q() == null ? "" : req.q().trim().toLowerCase();
        Integer minAge = req.minAge();
        Integer maxAge = req.maxAge();
        MissingPersonCase.PriorityLevel priority = req.priority();
        MissingPersonCase.Status status = req.status();
        String location = req.location() == null ? "" : req.location().trim().toLowerCase();

        return all.stream()
                .filter(c -> q.isEmpty() || matches(c, q))
                .filter(c -> minAge == null || (c.getAge() != null && c.getAge() >= minAge))
                .filter(c -> maxAge == null || (c.getAge() != null && c.getAge() <= maxAge))
                .filter(c -> priority == null || c.getPriorityLevel() == priority)
                .filter(c -> status == null || c.getStatus() == status)
                .filter(c -> location.isEmpty() || safeContains(c.getLastKnownPlace(), location))
                .sorted(Comparator.comparing(MissingPersonCase::getCreatedAt).reversed())
                .collect(Collectors.toList());
    }

    private boolean matches(MissingPersonCase c, String q) {
        return safeContains(c.getFirstName(), q)
                || safeContains(c.getLastName(), q)
                || safeContains(c.getCaseReference(), q);
    }

    private boolean matchesSighting(String text, String q) {
        return text != null && text.toLowerCase().contains(q);
    }

    private static boolean safeContains(String s, String needle) {
        return s != null && s.toLowerCase().contains(needle);
    }

    public record SearchQuery(String q, Integer minAge, Integer maxAge,
                              MissingPersonCase.PriorityLevel priority,
                              MissingPersonCase.Status status, String location, boolean publicOnly) {
    }
}