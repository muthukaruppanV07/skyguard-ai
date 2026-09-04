package com.missinglink.cases.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;

@Entity
@Table(name = "person_profiles")
@Getter
@Setter
@NoArgsConstructor
public class PersonProfile {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "case_id", unique = true)
    private MissingPersonCase caseRef;

    @Column(length = 200)
    private String hair;

    @Column(length = 200)
    private String eyes;

    @Column(name = "skin_tone", length = 200)
    private String skinTone;

    @Column(length = 500)
    private String clothing;

    @Column(length = 500)
    private String accessories;

    @Column(length = 200)
    private String backpack;

    @Column(length = 200)
    private String shoes;

    @Column(name = "other_characteristics", columnDefinition = "text")
    private String otherCharacteristics;

    @Column(name = "searchable_text", columnDefinition = "text")
    private String searchableText;

    @Column(name = "embedding_model", length = 100)
    private String embeddingModel;

    // embedding (VECTOR(512)) and embedding_model are written by the AI service
    // (pgvector/PostGIS live outside the JPA mapping for performance).

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt = Instant.now();

    @PreUpdate
    void onUpdate() {
        updatedAt = Instant.now();
    }
}