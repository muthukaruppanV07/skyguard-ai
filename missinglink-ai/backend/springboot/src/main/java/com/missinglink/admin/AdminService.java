package com.missinglink.admin;

import com.missinglink.audit.AuditLog;
import com.missinglink.audit.AuditLogRepository;
import com.missinglink.cases.domain.CaseRepository;
import com.missinglink.config.AppProperties;
import com.missinglink.sighting.domain.SightingRepository;
import com.missinglink.matching.domain.PotentialMatchRepository;
import com.missinglink.user.Role;
import com.missinglink.user.RoleRepository;
import com.missinglink.user.User;
import com.missinglink.user.UserRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

/** Administrative operations: user management, stats, audit, model versions, reports. */
@Service
public class AdminService {

    private final UserRepository users;
    private final RoleRepository roles;
    private final CaseRepository cases;
    private final SightingRepository sightings;
    private final PotentialMatchRepository matches;
    private final AuditLogRepository audit;
    private final ModelVersionRepository modelVersions;
    private final ReportRepository reports;
    private final AppProperties props;

    public AdminService(UserRepository users, RoleRepository roles, CaseRepository cases, SightingRepository sightings,
                        PotentialMatchRepository matches, AuditLogRepository audit,
                        ModelVersionRepository modelVersions, ReportRepository reports,
                        AppProperties props) {
        this.users = users;
        this.roles = roles;
        this.cases = cases;
        this.sightings = sightings;
        this.matches = matches;
        this.audit = audit;
        this.modelVersions = modelVersions;
        this.reports = reports;
        this.props = props;
    }

    @Transactional(readOnly = true)
    public Map<String, Object> stats() {
        return Map.of(
                "activeCases", cases.countActive(),
                "criticalCases", cases.countCritical(),
                "highPriorityCases", cases.countHigh(),
                "unverifiedSightings", sightings.countUnverified(),
                "awaitingMatches", matches.countAwaiting(),
                "acceptedMatches", matches.countAccepted(),
                "rejectedMatches", matches.countRejected(),
                "totalUsers", users.count(),
                "retentionDays", props.getRetention().getRetentionDays(),
                "generatedAt", java.time.Instant.now().toString());
    }

    @Transactional(readOnly = true)
    public List<User> listUsers() {
        return users.findAll();
    }

    @Transactional
    public void updateUser(Long userId, String status, String roleName) {
        User user = users.findById(userId)
                .orElseThrow(() -> new com.missinglink.common.ApiException(
                        org.springframework.http.HttpStatus.NOT_FOUND, "User not found"));
        if (roleName != null && !roleName.isBlank()) {
            Role role = roles.findByName(roleName)
                    .orElseThrow(() -> new com.missinglink.common.ApiException(
                            org.springframework.http.HttpStatus.BAD_REQUEST, "Unknown role"));
            user.setRole(role);
        }
        if (status != null && !status.isBlank()) {
            user.setStatus(User.Status.valueOf(status));
        }
        users.save(user);
    }

    @Transactional(readOnly = true)
    public Page<AuditLog> auditLogs(String action, String resourceType, String resourceId,
                                    int page, int size) {
        PageRequest pageable = PageRequest.of(page, size);
        if (action != null && !action.isBlank()) {
            return audit.findByAction(action, pageable);
        }
        if (resourceType != null && resourceId != null && !resourceType.isBlank()) {
            return audit.findByResourceTypeAndResourceId(resourceType, resourceId, pageable);
        }
        return audit.findAll(pageable);
    }

    @Transactional(readOnly = true)
    public List<ModelVersion> modelVersions() {
        return modelVersions.findAllByOrderByCreatedAtDesc();
    }

    @Transactional
    public Report fileReport(Long reporterId, String resourceType, String resourceId, String reason) {
        Report report = new Report();
        report.setReporter(users.getReferenceById(reporterId));
        report.setResourceType(resourceType);
        report.setResourceId(resourceId);
        report.setReason(reason);
        return reports.save(report);
    }

    @Transactional(readOnly = true)
    public List<Report> reports() {
        return reports.findAll();
    }

    @Transactional
    public Report updateReportStatus(Long reportId, Report.Status status, String notes) {
        Report r = reports.findById(reportId)
                .orElseThrow(() -> new com.missinglink.common.ApiException(
                        org.springframework.http.HttpStatus.NOT_FOUND, "Report not found"));
        r.setStatus(status);
        if (notes != null) r.setNotes(notes);
        return reports.save(r);
    }
}