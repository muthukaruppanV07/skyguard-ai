package com.missinglink.cases.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface CaseRepository extends JpaRepository<MissingPersonCase, Long> {

    Optional<MissingPersonCase> findByCaseReferenceAndDeletedAtIsNull(String caseReference);

    Optional<MissingPersonCase> findByIdAndDeletedAtIsNull(Long id);

    List<MissingPersonCase> findByStatusInAndIsPublicTrueAndDeletedAtIsNull(List<MissingPersonCase.Status> statuses);

    List<MissingPersonCase> findByReporterIdAndDeletedAtIsNull(Long reporterId);

    @Query("""
            SELECT DISTINCT c FROM MissingPersonCase c
            LEFT JOIN FETCH c.reporter
            WHERE c.deletedAt IS NULL
            """)
    List<MissingPersonCase> findAllActive();

    @Query("SELECT c FROM MissingPersonCase c WHERE c.status <> 'LOCATED' AND c.status <> 'CLOSED' AND c.deletedAt IS NULL ORDER BY c.createdAt DESC")
    List<MissingPersonCase> findActiveCases();

    @Query("SELECT count(c) FROM MissingPersonCase c WHERE c.status <> 'LOCATED' AND c.status <> 'CLOSED' AND c.deletedAt IS NULL")
    long countActive();

    @Query("SELECT count(c) FROM MissingPersonCase c WHERE c.priorityLevel = 'CRITICAL' AND c.status <> 'LOCATED' AND c.status <> 'CLOSED' AND c.deletedAt IS NULL")
    long countCritical();

    @Query("SELECT count(c) FROM MissingPersonCase c WHERE c.priorityLevel = 'HIGH' AND c.status <> 'LOCATED' AND c.status <> 'CLOSED' AND c.deletedAt IS NULL")
    long countHigh();

    @Query("""
            SELECT c FROM MissingPersonCase c
            WHERE c.deletedAt IS NULL AND c.status <> 'ARCHIVED'
            ORDER BY
                CASE c.priorityLevel WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 ELSE 2 END,
                c.createdAt DESC
            """)
    List<MissingPersonCase> findPriorityOrdered();

    /** Alternative names used by some queries. */
    @Query("SELECT c FROM MissingPersonCase c WHERE c.id = :id AND c.deletedAt IS NULL")
    Optional<MissingPersonCase> findByIdNotDeleted(@Param("id") Long id);
}