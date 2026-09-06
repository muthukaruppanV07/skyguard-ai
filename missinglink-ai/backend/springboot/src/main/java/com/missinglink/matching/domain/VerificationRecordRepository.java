package com.missinglink.matching.domain;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface VerificationRecordRepository extends JpaRepository<VerificationRecord, Long> {

    List<VerificationRecord> findByPotentialMatchIdOrderByCreatedAtAsc(Long potentialMatchId);
}