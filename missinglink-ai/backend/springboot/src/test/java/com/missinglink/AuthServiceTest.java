package com.missinglink;

import com.missinglink.config.AppProperties;
import com.missinglink.user.*;
import com.missinglink.audit.AuditService;
import com.missinglink.config.RateLimiter;
import com.missinglink.security.jwt.JwtTokenService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock
    private UserRepository userRepository;
    @Mock
    private RoleRepository roleRepository;
    @Mock
    private RefreshTokenRepository refreshTokenRepository;
    @Mock
    private AuditService audit;

    private final PasswordEncoder passwordEncoder = new BCryptPasswordEncoder(4);
    private JwtTokenService jwt;
    private AppProperties props;
    private RateLimiter rateLimiter;

    @BeforeEach
    void setUp() {
        props = new AppProperties();
        props.getJwt().setSecret("test-secret-that-is-at-least-64-characters-long-for-hmac-sha-256-signing-ok");
        jwt = new JwtTokenService(props);
        rateLimiter = new RateLimiter();
    }

    @Test
    void registersUserWithHashedPassword() {
        when(userRepository.existsByEmailIgnoreCase("a@b.c")).thenReturn(false);
        when(roleRepository.findByName("PUBLIC_USER")).thenReturn(Optional.of(role()));
        when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));

        AuthService service = new AuthService(userRepository, roleRepository, refreshTokenRepository,
                passwordEncoder, jwt, props, rateLimiter, audit);
        AuthService.AuthResponse res = service.register(
                new AuthService.RegisterRequest("a@b.c", "StrongPass1", "A B", null), "127.0.0.1");

        assertThat(res.accessToken()).isNotBlank();
        assertThat(res.refreshToken()).isNotBlank();
        assertThat(res.user().role()).isEqualTo("PUBLIC_USER");
    }

    @Test
    void duplicateEmailRejected() {
        when(userRepository.existsByEmailIgnoreCase("a@b.c")).thenReturn(true);
        AuthService service = new AuthService(userRepository, roleRepository, refreshTokenRepository,
                passwordEncoder, jwt, props, rateLimiter, audit);
        assertThatThrownBy(() -> service.register(
                new AuthService.RegisterRequest("a@b.c", "StrongPass1", "A B", null), "127.0.0.1"))
                .hasMessageContaining("already exists");
    }

    @Test
    void loginValidatesPasswordAndIssuesTokens() {
        String hash = passwordEncoder.encode("Secret123");
        User user = new User();
        user.setId(1L);
        user.setEmail("a@b.c");
        user.setPasswordHash(hash);
        user.setFullName("A B");
        user.setRole(role());
        user.setStatus(User.Status.ACTIVE);
        when(userRepository.findByEmailIgnoreCase("a@b.c")).thenReturn(Optional.of(user));
        when(userRepository.findPermissionNamesByUserId(1L)).thenReturn(List.of("sighting:submit"));

        AuthService service = new AuthService(userRepository, roleRepository, refreshTokenRepository,
                passwordEncoder, jwt, props, rateLimiter, audit);
        AuthService.AuthResponse res = service.login("a@b.c", "Secret123", "127.0.0.1");

        assertThat(jwt.parse(res.accessToken()).getSubject()).isEqualTo("1");
        assertThat(res.user().permissions()).contains("sighting:submit");
    }

    private static Role role() {
        Role r = new Role();
        r.setId(1L);
        r.setName("PUBLIC_USER");
        return r;
    }
}
