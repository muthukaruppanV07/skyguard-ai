package com.missinglink.audit;

import com.missinglink.security.SecurityUtils;
import com.missinglink.user.User;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.util.Map;

/** Append-only audit trail for sensitive actions. Always records without failing the caller. */
@Service
public class AuditService {

    private final AuditLogRepository repository;

    public AuditService(AuditLogRepository repository) {
        this.repository = repository;
    }

    public void record(String action, String resourceType, String resourceId, Map<String, Object> details) {
        recordSafe(action, resourceType, resourceId, details, currentActorOrNull());
    }

    public void recordSystem(String action, String resourceType, String resourceId, Map<String, Object> details) {
        recordSafe(action, resourceType, resourceId, details, null);
    }

    @Async
    void recordSafe(String action, String resourceType, String resourceId,
                    Map<String, Object> details, User actor) {
        try {
            AuditLog log = new AuditLog();
            log.setActor(actor);
            log.setAction(action);
            log.setResourceType(resourceType);
            log.setResourceId(resourceId);
            log.setDetails(details == null ? null : toJson(details));
            ServletRequestAttributes attrs =
                    (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
            HttpServletRequest request = attrs == null ? null : attrs.getRequest();
            if (request != null) {
                log.setIpAddress(clientIp(request));
                log.setUserAgent(request.getHeader("User-Agent"));
            } else {
                log.setIpAddress("system");
            }
            repository.save(log);
        } catch (Exception ignored) {
            // Audit failures must never take down the request
        }
    }

    private static User currentActorOrNull() {
        try {
            return SecurityUtils.currentUser();
        } catch (Exception e) {
            return null;
        }
    }

    private static String clientIp(HttpServletRequest request) {
        String xff = request.getHeader("X-Forwarded-For");
        return xff != null && !xff.isBlank() ? xff.split(",")[0].trim() : request.getRemoteAddr();
    }

    private static String toJson(Map<String, Object> details) {
        try {
            return new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(details);
        } catch (Exception e) {
            return "{}";
        }
    }
}