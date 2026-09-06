package com.missinglink.notification;

import com.missinglink.security.SecurityUtils;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/notifications")
public class NotificationController {

    private final NotificationService service;
    private final NotificationRepository repository;

    public NotificationController(NotificationService service, NotificationRepository repository) {
        this.service = service;
        this.repository = repository;
    }

    @GetMapping
    public ResponseEntity<List<NotificationView>> list() {
        Long userId = SecurityUtils.currentUserId();
        return ResponseEntity.ok(service.listForUser(userId).stream().map(NotificationView::from).toList());
    }

    @GetMapping("/unread")
    public ResponseEntity<UnreadCount> unread() {
        return ResponseEntity.ok(new UnreadCount(service.unreadCount(SecurityUtils.currentUserId())));
    }

    @PatchMapping("/{id}/read")
    public ResponseEntity<Void> markRead(@PathVariable Long id) {
        repository.findById(id).ifPresent(n -> {
            if (n.getUser().getId().equals(SecurityUtils.currentUserId())) {
                n.setRead(true);
                repository.save(n);
            }
        });
        return ResponseEntity.noContent().build();
    }

    public record NotificationView(String id, String type, String title, String body,
                                   String caseReference, boolean read, String createdAt) {
        public static NotificationView from(Notification n) {
            return new NotificationView(String.valueOf(n.getId()), n.getType(), n.getTitle(),
                    n.getBody(), n.getRelatedCase() == null ? null : n.getRelatedCase().getCaseReference(),
                    n.isRead(), n.getCreatedAt() == null ? "" : n.getCreatedAt().toString());
        }
    }

    public record UnreadCount(long count) {
    }
}