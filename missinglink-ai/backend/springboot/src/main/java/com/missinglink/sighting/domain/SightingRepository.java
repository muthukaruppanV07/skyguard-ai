package com.missinglink.sighting.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;

public interface SightingRepository extends JpaRepository<Sighting, Long> {

    Optional<Sighting> findFirstBySightingReference(String reference);

    @Query("SELECT COUNT(s) FROM Sighting s WHERE s.status = 'UNVERIFIED'")
    long countUnverified();

    @Query("""
            SELECT s FROM Sighting s
            WHERE (:caseId IS NULL OR s.caseRef.id = :caseId)
            ORDER BY s.reportedAt DESC
            """)
    List<Sighting> search(Long caseId);

    @Query("SELECT s FROM Sighting s WHERE s.caseRef.id = :caseId ORDER BY s.reportedAt ASC")
    List<Sighting> findByCaseIdOrdered(Long caseId);
}