package com.missinglink.notification;

import com.missinglink.config.AppProperties;
import org.springframework.stereotype.Component;

import java.time.Instant;

/** Logs outbound notifications to the console — safe default for dev/demo. */
@Component
public class ConsoleNotificationChannel implements NotificationChannel {

    private final AppProperties props;

    public ConsoleNotificationChannel(AppProperties props) {
        this.props = props;
    }

    @Override
    public void send(EmailMessage email) {
        // Deliberately no body in logs for demo builds beyond metadata.
        System.out.printf("[NOTIFICATION] from=%s to=%s subject=%s at %s%n",
                props.getEmail().getSmtp().getFrom(), email.to(), email.subject(), Instant.now());
    }
}