package com.missinglink.geospatial;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface SearchZoneRepository extends JpaRepository<SearchZone, Long> {

    List<SearchZone> findByCaseRefIdOrderByPriorityAsc(Long caseId);
}