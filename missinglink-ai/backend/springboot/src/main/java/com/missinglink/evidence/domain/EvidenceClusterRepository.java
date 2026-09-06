package com.missinglink.evidence.domain;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface EvidenceClusterRepository extends JpaRepository<EvidenceCluster, Long> {

    List<EvidenceCluster> findAllByOrderByCreatedAtDesc();
}