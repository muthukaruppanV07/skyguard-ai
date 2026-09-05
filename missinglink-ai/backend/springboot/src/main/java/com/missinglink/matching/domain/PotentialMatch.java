package com.missinglink.matching.domain;

import com.missinglink.cases.domain.MissingPersonCase;
import com.missinglink.evidence.domain.Evidence;
import com.missinglink.sighting.domain.Sighting;
import com.missinglink.user.User;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;

@Entity
@Table(name = "potential_matches")
@Getter
@Setter
@NoArgsConstructor
public class PotentialMatch {

    public enum Status {
        AWAITING_REVIEW, ACCEPTED, REJECTED, MORE_INFO, DUPLICATE, ESCALATED
    }

    public static final String HUMAN_REVIEW_LABEL = "POTENTIAL MATCH — HUMAN VERIFICATION REQUIRED";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "case_id")
    private MissingPersonCase caseRef;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "sighting_id")
    private Sighting sighting;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "evidence_id")
    private Evidence evidence;

    @Column(name = "overall_score", nullable = false)
    private Double overallScore;

    @Column(name = "face_similarity")
    private Double faceSimilarity;

    @Column(name = "clothing_similarity")
    private Double clothingSimilarity;

    @Column(name = "accessory_similarity")
    private Double accessorySimilarity;

    @Column(name = "body_similarity")
    private Double bodySimilarity;

    @Column(name = "image_similarity")
    private Double imageSimilarity;

    @Column(name = "location_relevance")
    private Double locationRelevance;

    @Column(name = "time_relevance")
    private Double timeRelevance;

    @Column(name = "text_similarity")
    private Double textSimilarity;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Status status = Status.AWAITING_REVIEW;

    @Column(columnDefinition = "jsonb")
    @JdbcTypeCode(SqlTypes.JSON)
    private String explanation;

    @Column(columnDefinition = "jsonb")
    @JdbcTypeCode(SqlTypes.JSON)
    private String limitations;

    @Column(name = "model_version_id")
    private Long modelVersionId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "reviewed_by")
    private User reviewedBy;

    @Column(name = "reviewed_at")
    private Instant reviewedAt;

    @Column(name = "review_notes", columnDefinition = "text")
    private String reviewNotes;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();
}