package com.missinglink.matching.api;

import com.missinglink.aigateway.AIGatewayService;
import com.missinglink.aigateway.dto.FaceMatchDtos.FaceMatchResponse;
import com.missinglink.audit.AuditService;
import com.missinglink.evidence.FileValidationService;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.Map;

/**
 * Photo/face matching: upload a photo of a person and get ranked potential
 * matches against active case profiles. Browsers never talk to the AI service
 * directly — everything flows through the AI gateway with the server-side key.
 */
@RestController
@RequestMapping("/api/v1/photo-match")
public class PhotoMatchController {

    private final AIGatewayService aiGateway;
    private final FileValidationService validation;
    private final AuditService audit;

    public PhotoMatchController(AIGatewayService aiGateway,
                                FileValidationService validation,
                                AuditService audit) {
        this.aiGateway = aiGateway;
        this.validation = validation;
        this.audit = audit;
    }

    @PostMapping
    @PreAuthorize("isAuthenticated()")
    public ResponseEntity<FaceMatchResponse> match(@RequestParam("photo") MultipartFile photo) {
        byte[] bytes;
        try {
            bytes = photo.getBytes();
        } catch (IOException e) {
            throw com.missinglink.common.ApiException.badRequest("Could not read the uploaded photo");
        }
        validation.validate(bytes, photo.getContentType());
        FaceMatchResponse result = aiGateway.photoMatch(bytes);
        audit.record("photo.match", "photo", "anonymous",
                Map.of("faces", result.faceDetected(), "matches", result.matches().size()));
        return ResponseEntity.ok(result);
    }
}