package com.missinglink.notification;

import com.missinglink.cases.CaseAccessService;
import com.missinglink.cases.domain.MissingPersonCase;
import com.missinglink.config.AppProperties;
import com.missinglink.user.User;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/** In-app notifications persisted to the DB plus realtime push via WebSocket. */
@Service
public class NotificationService {

    private final NotificationRepository repository;
    private final NotificationChannel channel;
    private final SimpMessagingTemplate messaging;
    private final AppProperties props;
    private final CaseAccessService caseAccess;

    public NotificationService(NotificationRepository repository,
                               NotificationChannel channel,
                               SimpMessagingTemplate messaging,
                               AppProperties props,
                               CaseAccessService caseAccess) {
        this.repository = repository;
        this.channel = channel;
        this.messaging = messaging;
        this.props = props;
        this.caseAccess = caseAccess;
    }

public Notification createForUser(User user, String type, String title, String body,
                                      MissingPersonCase caseRef) {
        Notification n = new Notification();
        n.setUser(user);
        n.setType(type);
        n.setTitle(title);
        n.setBody(body);
        n.setRelatedCase(caseRef);
        Notification saved = repository.save(n);
        messaging.convertAndSendToUser(String.valueOf(user.getId()),
                "/queue/notifications", savedToMap(saved));
        return saved;
    }

    public void createForUsers(List<User> users, String type, String title, String body,
                               MissingPersonCase caseRef) {
        users.forEach(u -> createForUser(u, type, title, body, caseRef));
    }

    /** Notifies all authorized investigators & admins about a case-relevant event. */
    public void createForInvestigators(String type, String title, String body, MissingPersonCase caseRef) {
        createForUsers(caseAccess.investigatorsAndAdmins(), type, title, body, caseRef);
    }

    public void sendEmail(String to, String subject, String html, String text) {
        channel.send(new NotificationChannel.EmailMessage(to, subject, html, text));
    }

    /** Fires a realtime event (new sighting, match decision, case update). */
    public void publishCaseEvent(MissingPersonCase caseRef, String eventType, Map<String, Object> payload) {
        Map<String, Object> message = new java.util.HashMap<>(payload);
        message.put("type", eventType);
        message.put("caseId", caseRef.getId());
        message.put("caseReference", caseRef.getCaseReference());
        messaging.convertAndSend("/topic/case." + caseRef.getId(), message);
    }

    public void publishGlobal(String eventType, Map<String, Object> payload) {
        Map<String, Object> message = new java.util.HashMap<>(payload);
        message.put("type", eventType);
        messaging.convertAndSend("/topic/public", message);
    }

    private static Map<String, Object> savedToMap(Notification n) {
        return Map.of(
                "id", n.getId(),
                "type", n.getType(),
                "title", n.getTitle(),
                "body", n.getBody() == null ? "" : n.getBody(),
                "read", n.isRead(),
                "createdAt", n.getCreatedAt() == null ? Instant.now().toString() : n.getCreatedAt().toString());
    }

    public List<Notification> listForUser(Long userId) {
        return repository.findByUserIdOrderByCreatedAtDesc(userId);
    }

    public long unreadCount(Long userId) {
        return repository.countByUserIdAndReadFalse(userId);
    }
}