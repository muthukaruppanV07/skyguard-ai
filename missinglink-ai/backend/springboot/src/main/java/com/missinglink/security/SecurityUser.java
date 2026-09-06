package com.missinglink.security;

import com.missinglink.user.User;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.stream.Collectors;

/** Authenticated principal; carries the domain User plus its authorities. */
public class SecurityUser implements UserDetails {

    private final User user;
    private final List<String> authorities;

    public SecurityUser(User user, List<String> authorities) {
        this.user = user;
        this.authorities = authorities == null ? List.of() : authorities;
    }

    public static SecurityUser from(User user, Collection<String> permissions) {
        List<String> auth = new ArrayList<>(permissions);
        auth.add("ROLE_" + user.getRole().getName());
        return new SecurityUser(user, auth);
    }

    public User getUser() {
        return user;
    }

    public Long getId() {
        return user.getId();
    }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return authorities.stream().map(SimpleGrantedAuthority::new).collect(Collectors.toList());
    }

    @Override
    public String getPassword() {
        return user.getPasswordHash();
    }

    @Override
    public String getUsername() {
        return user.getEmail();
    }

    @Override
    public boolean isAccountNonExpired() {
        return true;
    }

    @Override
    public boolean isAccountNonLocked() {
        return user.getStatus() != User.Status.LOCKED;
    }

    @Override
    public boolean isCredentialsNonExpired() {
        return true;
    }

    @Override
    public boolean isEnabled() {
        return user.getStatus() == User.Status.ACTIVE;
    }
}
