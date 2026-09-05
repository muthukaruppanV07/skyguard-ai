package com.missinglink.evidence.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;

@Entity
@Table(name = "evidence_clusters")
@Getter
@Setter
@NoArgsConstructor
public class EvidenceCluster {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String title;

    // centroid (PostGIS) is read/written via JdbcTemplate (GeoSql), not mapped here.

    @Column(name = "first_timestamp")
    private Instant firstTimestamp;

    @Column(name = "last_timestamp")
    private Instant lastTimestamp;

    @Column(name = "source_count", nullable = false)
    private int sourceCount = 1;

    @Column(name = "avg_similarity")
    private Double avgSimilarity;

    @Column(columnDefinition = "jsonb")
    @JdbcTypeCode(SqlTypes.JSON)
    private String meta;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();
}