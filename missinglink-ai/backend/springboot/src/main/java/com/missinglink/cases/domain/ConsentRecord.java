package com.missinglink.cases.domain;

import com.missinglink.user.User;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;

@Entity
@Table(name = "consent_records")
@Getter
@Setter
@NoArgsConstructor
public class ConsentRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "case_id")
    private MissingPersonCase caseRef;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "granter_id")
    private User granter;

    @Column(name = "consent_type", nullable = false, length = 40)
    private String consentType;

    @Column(name = "consent_text", columnDefinition = "text")
    private String consentText;

    @Column(name = "signed_at", nullable = false)
    private Instant signedAt = Instant.now();

    @Column(name = "storage_key", length = 500)
    private String storageKey;
}