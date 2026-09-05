package com.missinglink.cases.domain;

import com.missinglink.user.User;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;

@Entity
@Table(name = "missing_person_cases")
@Getter
@Setter
@NoArgsConstructor
public class MissingPersonCase {

    public enum Status {
        OPEN, ACTIVE, LOCATED, CLOSED, ARCHIVED
    }

    public enum PriorityLevel {
        STANDARD, HIGH, CRITICAL
    }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "case_reference", nullable = false, unique = true, length = 20)
    private String caseReference;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "reporter_id", nullable = false)
    private User reporter;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Status status = Status.OPEN;

    @Enumerated(EnumType.STRING)
    @Column(name = "priority_level", nullable = false)
    private PriorityLevel priorityLevel = PriorityLevel.STANDARD;

    @Column(name = "emergency_classification", length = 60)
    private String emergencyClassification;

    @Column(length = 255)
    private String title;

    @Column(name = "first_name", length = 120)
    private String firstName;

    @Column(name = "last_name", length = 120)
    private String lastName;

    private Integer age;

    @Column(length = 30)
    private String gender;

    @Column(name = "height_cm")
    private Integer heightCm;

    @Column(name = "identification_marks", columnDefinition = "text")
    private String identificationMarks;

    @Column(length = 500)
    private String languages;

    @Column(name = "last_known_activity", columnDefinition = "text")
    private String lastKnownActivity;

    @Column(length = 300)
    private String transportation;

    @Column(name = "possible_destinations", length = 500)
    private String possibleDestinations;

    @Column(columnDefinition = "text")
    private String description;

    @Column(name = "last_known_place", length = 255)
    private String lastKnownPlace;

    @Column(name = "last_known_at")
    private Instant lastKnownAt;

    @Column(name = "last_known_lat")
    private Double lastKnownLat;

    @Column(name = "last_known_lng")
    private Double lastKnownLng;

    @Column(name = "is_public", nullable = false)
    private boolean isPublic = false;

    @Column(name = "resolved_at")
    private Instant resolvedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt = Instant.now();

    @Column(name = "deleted_at")
    private Instant deletedAt;

    @PreUpdate
    void onUpdate() {
        updatedAt = Instant.now();
    }
}
