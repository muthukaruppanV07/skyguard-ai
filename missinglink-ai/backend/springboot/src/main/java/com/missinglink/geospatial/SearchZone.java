package com.missinglink.geospatial;

import com.missinglink.cases.domain.MissingPersonCase;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;

@Entity
@Table(name = "search_zones")
@Getter
@Setter
@NoArgsConstructor
public class SearchZone {

    public enum ZoneType {
        HIGH_PRIORITY, MEDIUM_PRIORITY, LOW_PRIORITY, LEAD_CLUSTER
    }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "case_id")
    private MissingPersonCase caseRef;

    @Enumerated(EnumType.STRING)
    @Column(name = "zone_type", nullable = false, length = 40)
    private ZoneType zoneType;

    @Column(nullable = false)
    private int priority = 3;

    @Column(name = "radius_km")
    private Double radiusKm;

    // geom (PostGIS polygon) is read/written via JdbcTemplate (GeoSql), not mapped here.

    @Column(columnDefinition = "text")
    private String rationale;

    @Column(name = "ai_generated", nullable = false)
    private boolean aiGenerated = true;

    @Column(nullable = false)
    private boolean reviewed = false;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();
}