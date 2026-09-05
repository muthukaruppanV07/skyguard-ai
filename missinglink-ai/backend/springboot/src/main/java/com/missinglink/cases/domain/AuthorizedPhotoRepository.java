package com.missinglink.cases.domain;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface AuthorizedPhotoRepository extends JpaRepository<AuthorizedPhoto, Long> {

    List<AuthorizedPhoto> findByCaseRefId(Long caseId);
}