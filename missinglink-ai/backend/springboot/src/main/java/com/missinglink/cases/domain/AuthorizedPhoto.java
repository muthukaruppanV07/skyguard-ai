package com.missinglink.cases.domain;

import com.missinglink.user.User;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;

@Entity
@Table(name = "authorized_photos")
@Getter
@Setter
@NoArgsConstructor
public class AuthorizedPhoto {

    public enum PhotoType {
        FRONT_FACE, SIDE_PROFILE, FULL_BODY, OLDER
    }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "case_id")
    private MissingPersonCase caseRef;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "uploader_id")
    private User uploader;

    @Column(name = "storage_key", nullable = false, length = 500)
    private String storageKey;

    @Enumerated(EnumType.STRING)
    @Column(name = "photo_type", nullable = false)
    private PhotoType photoType = PhotoType.FRONT_FACE;

    @Column(name = "consent_record_id")
    private Long consentRecordId;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();
}