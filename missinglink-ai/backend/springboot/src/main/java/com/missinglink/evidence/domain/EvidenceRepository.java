package com.missinglink.evidence.domain;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface EvidenceRepository extends JpaRepository<Evidence, Long> {

    List<Evidence> findBySightingId(Long sightingId);

    List<Evidence> findByCaseRefId(Long caseId);

    Optional<Evidence> findFirstBySha256(String sha256);
}