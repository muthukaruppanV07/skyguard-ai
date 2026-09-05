package com.missinglink.security;

import com.missinglink.common.ApiException;
import com.missinglink.user.User;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

/** Helpers to read the current authenticated user. */
public final class SecurityUtils {

    private SecurityUtils() {
    }

    public static SecurityUser current() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof SecurityUser su) {
            return su;
        }
        throw ApiException.unauthorized("Authentication required");
    }

    public static User currentUser() {
        return current().getUser();
    }

    public static Long currentUserId() {
        return current().getId();
    }

    public static boolean hasPermission(String permission) {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof SecurityUser su)) {
            return false;
        }
        return su.getAuthorities().stream()
                .anyMatch(a -> a.getAuthority().equals(permission));
    }
}
