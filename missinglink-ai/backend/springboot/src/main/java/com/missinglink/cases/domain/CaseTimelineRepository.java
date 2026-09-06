package com.missinglink.cases.domain;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface CaseTimelineRepository extends JpaRepository<CaseTimeline, Long> {

    List<CaseTimeline> findByCaseRefIdOrderByCreatedAtAsc(Long caseId);
}