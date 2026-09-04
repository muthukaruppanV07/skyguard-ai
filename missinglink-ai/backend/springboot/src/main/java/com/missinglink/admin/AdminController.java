package com.missinglink.admin;

import com.missinglink.audit.AuditLog;
import com.missinglink.user.User;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/admin")
public class AdminController {

    private final AdminService adminService;

    public AdminController(AdminService adminService) {
        this.adminService = adminService;
    }

    @GetMapping("/stats")
    @PreAuthorize("hasAuthority('admin:manage')")
    public ResponseEntity<Map<String, Object>> stats() {
        return ResponseEntity.ok(adminService.stats());
    }

    @GetMapping("/users")
    @PreAuthorize("hasAuthority('admin:manage')")
    public ResponseEntity<List<UserView>> users() {
        return ResponseEntity.ok(adminService.listUsers().stream().map(UserView::from).toList());
    }

    @PatchMapping("/users/{id}")
    @PreAuthorize("hasAuthority('admin:manage')")
    public ResponseEntity<Void> updateUser(@PathVariable Long id, @RequestBody UserUpdate update) {
        adminService.updateUser(id, update.status(), update.role());
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/audit")
    @PreAuthorize("hasAuthority('audit:read')")
    public ResponseEntity<Page<AuditLog>> audit(
            @RequestParam(required = false) String action,
            @RequestParam(required = false) String resourceType,
            @RequestParam(required = false) String resourceId,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(adminService.auditLogs(action, resourceType, resourceId, page, size));
    }

    @GetMapping("/model-versions")
    @PreAuthorize("hasAuthority('admin:manage')")
    public ResponseEntity<List<ModelVersion>> modelVersions() {
        return ResponseEntity.ok(adminService.modelVersions());
    }

    @GetMapping("/system-health")
    @PreAuthorize("hasAuthority('admin:manage')")
    public ResponseEntity<Map<String, String>> systemHealth() {
        return ResponseEntity.ok(Map.of(
                "status", "UP",
                "service", "missinglink-backend",
                "time", java.time.Instant.now().toString()));
    }

    @PostMapping("/reports")
    @PreAuthorize("hasAuthority('report:create')")
    public ResponseEntity<Report> fileReport(@RequestBody ReportRequest request) {
        return ResponseEntity.ok(adminService.fileReport(
                com.missinglink.security.SecurityUtils.currentUserId(),
                request.resourceType(), request.resourceId(), request.reason()));
    }

    @GetMapping("/reports")
    @PreAuthorize("hasAuthority('report:review')")
    public ResponseEntity<List<Report>> reports() {
        return ResponseEntity.ok(adminService.reports());
    }

    @PatchMapping("/reports/{id}")
    @PreAuthorize("hasAuthority('report:review')")
    public ResponseEntity<Report> updateReport(@PathVariable Long id, @RequestBody ReportStatus update) {
        return ResponseEntity.ok(adminService.updateReportStatus(id, Report.Status.valueOf(update.status()), update.notes()));
    }

    public record UserView(String id, String email, String fullName, String role, String status,
                           boolean mfaEnabled, java.time.Instant createdAt) {
        public static UserView from(User u) {
            return new UserView(String.valueOf(u.getId()), u.getEmail(), u.getFullName(),
                    u.getRole() == null ? "" : u.getRole().getName(), u.getStatus().name(),
                    u.isMfaEnabled(), u.getCreatedAt());
        }
    }

    public record UserUpdate(String status, String role) {
    }

    public record ReportRequest(String resourceType, String resourceId, String reason) {
    }

    public record ReportStatus(String status, String notes) {
    }
}