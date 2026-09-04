package com.missinglink.user;

import com.missinglink.audit.AuditService;
import com.missinglink.common.ApiException;
import com.missinglink.config.AppProperties;
import com.missinglink.config.RateLimiter;
import com.missinglink.security.SecurityUtils;
import com.missinglink.security.SecurityUser;
import com.missinglink.security.jwt.JwtTokenService;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final RoleRepository roleRepository;
    private final RefreshTokenRepository refreshTokenRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenService jwt;
    private final AppProperties props;
    private final RateLimiter rateLimiter;
    private final AuditService audit;

    public AuthService(UserRepository userRepository, RoleRepository roleRepository,
                       RefreshTokenRepository refreshTokenRepository, PasswordEncoder passwordEncoder,
                       JwtTokenService jwt, AppProperties props, RateLimiter rateLimiter,
                       AuditService audit) {
        this.userRepository = userRepository;
        this.roleRepository = roleRepository;
        this.refreshTokenRepository = refreshTokenRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwt = jwt;
        this.props = props;
        this.rateLimiter = rateLimiter;
        this.audit = audit;
    }

    @Transactional
    public AuthResponse register(RegisterRequest request, String ip) {
        if (userRepository.existsByEmailIgnoreCase(request.email())) {
            throw ApiException.conflict("An account with this email already exists");
        }
        Role role = roleRepository.findByName("PUBLIC_USER")
                .orElseThrow(() -> ApiException.internal("PUBLIC_USER role missing from seed"));
        User user = new User();
        user.setEmail(request.email().trim().toLowerCase());
        user.setPasswordHash(passwordEncoder.encode(request.password()));
        user.setFullName(request.fullName());
        user.setPhone(request.phone());
        user.setRole(role);
        user.setStatus(User.Status.ACTIVE);
        userRepository.save(user);

        audit.record("auth.register", "user", String.valueOf(user.getId()),
                Map.of("email", user.getEmail(), "ip", ip));
        return issueTokens(user);
    }

    @Transactional
    public AuthResponse login(String email, String password, String ip) {
        rateLimiter.check("login", ip, props.getRateLimit().getLoginPerMinute());
        User user = userRepository.findByEmailIgnoreCase(email)
                .orElseThrow(() -> ApiException.unauthorized("Invalid email or password"));
        if (!passwordEncoder.matches(password, user.getPasswordHash())) {
            audit.recordSystem("auth.login_failed", "user", String.valueOf(user.getId()),
                    Map.of("email", email, "ip", ip));
            throw ApiException.unauthorized("Invalid email or password");
        }
        if (user.getStatus() != User.Status.ACTIVE) {
            throw ApiException.forbidden("Account is not active");
        }
        audit.record("auth.login", "user", String.valueOf(user.getId()), Map.of("ip", ip));
        return issueTokens(user);
    }

    @Transactional
    public AuthResponse refresh(String refreshToken, String ip) {
        String hash = JwtTokenService.sha256(refreshToken);
        RefreshToken token = refreshTokenRepository.findByTokenHash(hash)
                .filter(t -> !t.isRevoked())
                .filter(t -> t.getExpiresAt().isAfter(Instant.now()))
                .orElseThrow(() -> ApiException.unauthorized("Invalid or expired refresh token"));
        token.setRevoked(true);
        refreshTokenRepository.save(token);
        audit.record("auth.refresh", "user", String.valueOf(token.getUser().getId()), Map.of("ip", ip));
        return issueTokens(token.getUser());
    }

    @Transactional
    public void logout(String refreshToken) {
        if (refreshToken == null || refreshToken.isBlank()) {
            return;
        }
        refreshTokenRepository.findByTokenHash(JwtTokenService.sha256(refreshToken))
                .ifPresent(t -> {
                    t.setRevoked(true);
                    refreshTokenRepository.save(t);
                });
    }

    @Transactional
    public void changePassword(String currentPassword, String newPassword) {
        User user = SecurityUtils.currentUser();
        if (!passwordEncoder.matches(currentPassword, user.getPasswordHash())) {
            throw ApiException.badRequest("Current password is incorrect");
        }
        user.setPasswordHash(passwordEncoder.encode(newPassword));
        userRepository.save(user);
        audit.record("auth.change_password", "user", String.valueOf(user.getId()), Map.of());
    }

    private AuthResponse issueTokens(User user) {
        List<String> permissions = userRepository.findPermissionNamesByUserId(user.getId());
        String accessToken = jwt.createAccessToken(user, permissions);
        String refreshToken = jwt.createRefreshToken();

        RefreshToken rt = new RefreshToken();
        rt.setUser(user);
        rt.setTokenHash(JwtTokenService.sha256(refreshToken));
        rt.setExpiresAt(Instant.now().plusMillis(jwt.getRefreshTtlMs()));
        refreshTokenRepository.save(rt);

        return new AuthResponse(
                accessToken,
                refreshToken,
                jwt.getRefreshTtlMs() / 1000,
                new UserDto(user.getId(), user.getEmail(), user.getFullName(), user.getRole().getName(),
                        user.isMfaEnabled(), permissions));
    }

    public record RegisterRequest(
            @jakarta.validation.constraints.Email String email,
            @jakarta.validation.constraints.NotBlank @jakarta.validation.constraints.Size(min = 8) String password,
            @jakarta.validation.constraints.NotBlank String fullName,
            String phone) {
    }

    public record LoginRequest(String email, String password) {
    }

    public record RefreshRequest(String refreshToken) {
    }

    public record AuthResponse(String accessToken, String refreshToken, long refreshTtlSeconds, UserDto user) {
    }

    public record UserDto(Long id, String email, String fullName, String role, boolean mfaEnabled,
                          List<String> permissions) {
    }
}