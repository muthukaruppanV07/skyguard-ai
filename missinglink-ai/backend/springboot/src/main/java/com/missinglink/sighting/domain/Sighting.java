package com.missinglink.sighting.domain;

import com.missinglink.cases.domain.MissingPersonCase;
import com.missinglink.user.User;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;

@Entity
@Table(name = "sightings")
@Getter
@Setter
@NoArgsConstructor
public class Sighting {

    public enum Status {
        UNVERIFIED, VERIFIED, REJECTED, DUPLICATE
    }

    public enum Source {
        WEB, MOBILE, VOICE, API
    }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "sighting_reference", nullable = false, unique = true, length = 20)
    private String sightingReference;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "submitter_id")
    private User submitter;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "case_id")
    private MissingPersonCase caseRef;

    @Column(columnDefinition = "text")
    private String description;

    @Column(length = 500)
    private String clothing;

    @Column(name = "direction_of_movement", length = 100)
    private String directionOfMovement;

    @Column(name = "vehicle_info", length = 300)
    private String vehicleInfo;

    @Column(columnDefinition = "text")
    private String notes;

    private Double lat;
    private Double lng;

    @Column(name = "location_name", length = 255)
    private String locationName;

    @Column(name = "captured_at")
    private Instant capturedAt;

    @Column(name = "reported_at", nullable = false)
    private Instant reportedAt = Instant.now();

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Source source = Source.WEB;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Status status = Status.UNVERIFIED;

    @Column(name = "evidence_cluster_id")
    private Long evidenceClusterId;

    @Column(columnDefinition = "jsonb")
    @JdbcTypeCode(SqlTypes.JSON)
    private String metadata;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();
}