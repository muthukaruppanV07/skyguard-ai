package com.missinglink.matching.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface PotentialMatchRepository extends JpaRepository<PotentialMatch, Long> {

    List<PotentialMatch> findByStatusOrderByOverallScoreDesc(PotentialMatch.Status status);

    @Query("""
            SELECT pm FROM PotentialMatch pm
            WHERE pm.status = 'AWAITING_REVIEW'
            ORDER BY pm.overallScore DESC
            """)
    List<PotentialMatch> awaitingReview();

    @Query("SELECT COUNT(pm) FROM PotentialMatch pm WHERE pm.status = 'AWAITING_REVIEW'")
    long countAwaiting();

    @Query("SELECT COUNT(pm) FROM PotentialMatch pm WHERE pm.status = 'ACCEPTED'")
    long countAccepted();

    @Query("SELECT COUNT(pm) FROM PotentialMatch pm WHERE pm.status = 'REJECTED'")
    long countRejected();

    Optional<PotentialMatch> findByIdAndCaseRefId(Long id, Long caseId);

    /** Case-aware queue: only matches for cases the user can access. */
    @Query("""
            SELECT pm FROM PotentialMatch pm
            WHERE pm.status = 'AWAITING_REVIEW'
              AND (:caseId IS NULL OR pm.caseRef.id = :caseId)
            ORDER BY pm.overallScore DESC
            """)
    List<PotentialMatch> awaitingReviewForCase(@Param("caseId") Long caseId);

    long countBySightingId(Long sightingId);

    java.util.Optional<PotentialMatch> findFirstByCaseRefIdAndSightingId(Long caseId, Long sightingId);
}