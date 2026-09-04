package com.missinglink.admin;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ModelVersionRepository extends JpaRepository<ModelVersion, Long> {

    Optional<ModelVersion> findByVersion(String version);

    List<ModelVersion> findAllByOrderByCreatedAtDesc();
}