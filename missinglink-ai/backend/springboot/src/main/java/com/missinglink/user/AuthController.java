package com.missinglink.user;

import com.missinglink.security.SecurityUtils;
import com.missinglink.security.SecurityUser;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.List;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @PostMapping("/register")
    public ResponseEntity<AuthService.AuthResponse> register(
            @Valid @RequestBody AuthService.RegisterRequest request, HttpServletRequest req) {
        return ResponseEntity.ok(authService.register(request, clientIp(req)));
    }

    @PostMapping("/login")
    public ResponseEntity<AuthService.AuthResponse> login(
            @RequestBody AuthService.LoginRequest request, HttpServletRequest req) {
        return ResponseEntity.ok(authService.login(request.email(), request.password(), clientIp(req)));
    }

    @PostMapping("/refresh")
    public ResponseEntity<AuthService.AuthResponse> refresh(
            @RequestBody AuthService.RefreshRequest request, HttpServletRequest req) {
        return ResponseEntity.ok(authService.refresh(request.refreshToken(), clientIp(req)));
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(@RequestBody AuthService.RefreshRequest request) {
        authService.logout(request.refreshToken());
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/change-password")
    public ResponseEntity<Void> changePassword(@RequestBody ChangePasswordRequest request) {
        authService.changePassword(request.currentPassword(), request.newPassword());
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/me")
    public ResponseEntity<AuthService.UserDto> me() {
        SecurityUser su = SecurityUtils.current();
        List<String> perms = new java.util.ArrayList<>(su.getAuthorities().stream()
                .map(a -> a.getAuthority()).filter(a -> a.startsWith("ROLE_") == false)
                .toList());
        return ResponseEntity.ok(new AuthService.UserDto(su.getId(), su.getUser().getEmail(),
                su.getUser().getFullName(), su.getUser().getRole().getName(),
                su.getUser().isMfaEnabled(), perms));
    }

    private static String clientIp(HttpServletRequest req) {
        String xff = req.getHeader("X-Forwarded-For");
        return xff != null && !xff.isBlank() ? xff.split(",")[0].trim() : req.getRemoteAddr();
    }

    public record ChangePasswordRequest(String currentPassword, String newPassword) {
    }
}