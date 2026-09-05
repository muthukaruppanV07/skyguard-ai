package com.missinglink.user;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByEmailIgnoreCase(String email);

    boolean existsByEmailIgnoreCase(String email);

    @Query("""
            SELECT p.name FROM Permission p
            JOIN p.roles r
            JOIN r.users u
            WHERE u.id = :userId
            """)
    List<String> findPermissionNamesByUserId(Long userId);
}
