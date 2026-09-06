package com.missinglink.evidence.domain;

import com.missinglink.cases.domain.MissingPersonCase;
import com.missinglink.sighting.domain.Sighting;
import com.missinglink.user.User;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;

@Entity
@Table(name = "evidence")
@Getter
@Setter
@NoArgsConstructor
public class Evidence {

    public enum MalwareScanStatus {
        PENDING, CLEAN, SUSPICIOUS, FLAGGED
    }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "sighting_id")
    private Sighting sighting;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "case_id")
    private MissingPersonCase caseRef;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "uploader_id")
    private User uploader;

    @Column(name = "storage_key", nullable = false, length = 500)
    private String storageKey;

    @Column(name = "original_filename", length = 255)
    private String originalFilename;

    @Column(name = "content_type", length = 120)
    private String contentType;

    @Column(name = "size_bytes")
    private Long sizeBytes;

    @Column(length = 64)
    private String sha256;

    @Enumerated(EnumType.STRING)
    @Column(name = "malware_scan_status", nullable = false)
    private MalwareScanStatus malwareScanStatus = MalwareScanStatus.PENDING;

    @Column(name = "quality_score")
    private Double qualityScore;

    @Column(name = "uploaded_at", nullable = false)
    private Instant uploadedAt = Instant.now();
}