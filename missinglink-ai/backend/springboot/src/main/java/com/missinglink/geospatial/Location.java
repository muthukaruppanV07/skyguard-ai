package com.missinglink.geospatial;

import com.missinglink.cases.domain.MissingPersonCase;
import com.missinglink.sighting.domain.Sighting;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;

@Entity
@Table(name = "locations")
@Getter
@Setter
@NoArgsConstructor
public class Location {

    public enum LocationType {
        LAST_KNOWN, SIGHTING, RESOURCE, IMPORTANT
    }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "case_id")
    private MissingPersonCase caseRef;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "sighting_id")
    private Sighting sighting;

    // geom (PostGIS) is read/written via JdbcTemplate (GeoSql), not mapped here.

    @Column(length = 255)
    private String label;

    @Enumerated(EnumType.STRING)
    @Column(name = "location_type", length = 40)
    private LocationType locationType;

    @Column(name = "accuracy_meters")
    private Double accuracyMeters;

    @Column(name = "occurred_at")
    private Instant occurredAt;
}