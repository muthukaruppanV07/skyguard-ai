package com.missinglink;

import com.missinglink.aigateway.AIGatewayService;
import com.missinglink.aigateway.dto.FaceMatchDtos.FaceMatch;
import com.missinglink.aigateway.dto.FaceMatchDtos.FaceMatchResponse;
import com.missinglink.audit.AuditService;
import com.missinglink.common.ApiException;
import com.missinglink.evidence.FileValidationService;
import com.missinglink.matching.api.PhotoMatchController;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PhotoMatchControllerTest {

    private static byte[] png() {
        return new byte[]{(byte) 0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A, 0, 0, 0, 0x0D, 'I', 'H', 'D', 'R'};
    }

    @Test
    void returnsAiMatchesForValidPhoto() {
        AIGatewayService ai = mock(AIGatewayService.class);
        FaceMatchResponse expected = new FaceMatchResponse(
                true, 0.9, List.of(), List.of(
                        new FaceMatch(1L, "MP-101", "Aarav Menon", "ACTIVE", 0.81,
                                0.77, 0.65, Map.of("face", 0.55, "image", 0.15),
                                "Facial similarity supports the match.", List.of(), "PRIORITY")),
                "fallback-perceptual", 0.35, 42, "");
        when(ai.photoMatch(any())).thenReturn(expected);

        PhotoMatchController controller = new PhotoMatchController(
                ai, new FileValidationService(), mock(AuditService.class));
        MockMultipartFile file = new MockMultipartFile("photo", "face.png", "image/png", png());

        FaceMatchResponse body = controller.match(file).getBody();
        assertThat(body).isNotNull();
        assertThat(body.faceDetected()).isTrue();
        assertThat(body.matches()).hasSize(1);
        assertThat(body.matches().get(0).caseReference()).isEqualTo("MP-101");
        verify(ai).photoMatch(any());
    }

    @Test
    void rejectsNonImageUpload() {
        AIGatewayService ai = mock(AIGatewayService.class);
        PhotoMatchController controller = new PhotoMatchController(
                ai, new FileValidationService(), mock(AuditService.class));
        MockMultipartFile file = new MockMultipartFile("photo", "evil.txt", "text/plain",
                "not an image at all".getBytes(StandardCharsets.UTF_8));
        assertThatThrownBy(() -> controller.match(file)).isInstanceOf(ApiException.class);
    }
}