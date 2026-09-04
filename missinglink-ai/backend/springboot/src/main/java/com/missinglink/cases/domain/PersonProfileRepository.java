package com.missinglink.cases.domain;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PersonProfileRepository extends JpaRepository<PersonProfile, Long> {

    Optional<PersonProfile> findByCaseRefId(Long caseId);

    List<PersonProfile> findAllByCaseRefIdIn(List<Long> caseIds);
}