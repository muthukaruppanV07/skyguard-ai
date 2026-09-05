package com.missinglink.admin;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;

@Entity
@Table(name = "model_versions")
@Getter
@Setter
@NoArgsConstructor
public class ModelVersion {

    public enum Status {
        ACTIVE, BETA, RETIRED
    }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 40)
    private String version;

    @Column(length = 120)
    private String name;

    @Column(name = "face_model", length = 120)
    private String faceModel;

    @Column(name = "embedding_model", length = 120)
    private String embeddingModel;

    @Column(name = "detection_model", length = 120)
    private String detectionModel;

    @Column(columnDefinition = "jsonb")
    @JdbcTypeCode(SqlTypes.JSON)
    private String metrics;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Status status = Status.ACTIVE;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();
}