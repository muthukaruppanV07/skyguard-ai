package com.missinglink.notification;

/**
 * Outbound notification channel abstraction. Implementations: console (default),
 * SMTP email, SMS/WhatsApp (architecture stub). Keeps credentials out of callers.
 */
public interface NotificationChannel {

    void send(EmailMessage email);

    record EmailMessage(String to, String subject, String bodyHtml, String bodyText) {
    }
}