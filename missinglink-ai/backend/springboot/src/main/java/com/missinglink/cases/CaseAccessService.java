package com.missinglink.cases;

import com.missinglink.cases.domain.CaseRepository;
import com.missinglink.cases.domain.MissingPersonCase;
import com.missinglink.common.ApiException;
import com.missinglink.security.SecurityUtils;
import com.missinglink.user.RoleRepository;
import com.missinglink.user.User;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Per-case authorization: determines whether the current user may read or act on a
 * given case. This is the core enforcement point beyond role-based permissions.
 */
@Service
public class CaseAccessService {

    private final CaseRepository caseRepository;
    private final RoleRepository roleRepository;

    public CaseAccessService(CaseRepository caseRepository, RoleRepository roleRepository) {
        this.caseRepository = caseRepository;
        this.roleRepository = roleRepository;
    }

    public MissingPersonCase requireAccess(Long caseId) {
        MissingPersonCase caseRef = caseRepository.findByIdNotDeleted(caseId)
                .orElseThrow(() -> ApiException.notFound("Case not found"));
        User user = SecurityUtils.currentUser();
        if (canAccess(user, caseRef)) {
            return caseRef;
        }
        throw ApiException.forbidden("You do not have access to this case");
    }

    public MissingPersonCase requireCaseOrPublic(Long caseId) {
        MissingPersonCase caseRef = caseRepository.findByIdNotDeleted(caseId)
                .orElseThrow(() -> ApiException.notFound("Case not found"));
        if (caseRef.isPublic()) {
            return caseRef;
        }
        return requireAccess(caseId);
    }

    public boolean canAccess(User user, MissingPersonCase caseRef) {
        String role = user.getRole().getName();
        if ("ADMIN".equals(role) || "INVESTIGATOR".equals(role)) {
            return true;
        }
        if ("FAMILY".equals(role)) {
            return caseRef.getReporter().getId().equals(user.getId());
        }
        // PUBLIC_USER: only public cases without full PII
        return caseRef.isPublic();
    }

    /** Readers who should receive all case notifications (investigators + admin). */
    @Transactional(readOnly = true)
    public java.util.List<User> investigatorsAndAdmins() {
        return roleRepository.findByName("INVESTIGATOR")
                .map(r -> r.getUsers().stream()
                        .filter(u -> u.getStatus() == User.Status.ACTIVE && u.getId() != null)
                        .collect(java.util.stream.Collectors.toList()))
                .orElseGet(java.util.List::of);
    }
}