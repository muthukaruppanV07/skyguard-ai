package com.missinglink.evidence;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.stream.Collectors;
import java.util.stream.IntStream;

/**
 * Writes pgvector embeddings from the Java side. The vector column is text-cast
 * via `?::vector` — pgvector accepts the `[0.1,0.2,...]` literal form.
 */
@Service
public class VectorWriter {

    private final JdbcTemplate jdbc;

    public VectorWriter(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void upsertEvidenceEmbedding(Long evidenceId, double[] embedding, Long modelVersionId, int dim) {
        jdbc.update("""
                        INSERT INTO evidence_embeddings (evidence_id, embedding, model_version_id, dimension, created_at)
                        VALUES (?, ?::vector, ?, ?, now())
                        ON CONFLICT (evidence_id) DO UPDATE SET embedding = EXCLUDED.embedding
                        """,
                evidenceId, literal(embedding), modelVersionId, dim);
    }

    public void upsertProfileEmbedding(Long caseId, double[] embedding, String model) {
        jdbc.update("""
                        UPDATE person_profiles
                        SET embedding = ?::vector, embedding_model = ?, updated_at = now()
                        WHERE case_id = ?
                        """, literal(embedding), model, caseId);
    }

    /** All evidence embeddings linked to a case (for aggregating the profile vector). */
    public java.util.List<double[]> embeddingsForCase(Long caseId) {
        return jdbc.query("""
                        SELECT e.embedding
                        FROM evidence_embeddings e
                        JOIN evidence ev ON ev.id = e.evidence_id
                        WHERE ev.case_id = ?
                        """,
                (rs, i) -> parse(rs.getString("embedding")),
                caseId);
    }

    public static double[] parse(String literal) {
        String cleaned = literal.replace("[", "").replace("]", "").trim();
        if (cleaned.isEmpty()) {
            return new double[0];
        }
        String[] parts = cleaned.split(",");
        double[] vec = new double[parts.length];
        for (int i = 0; i < parts.length; i++) {
            vec[i] = Double.parseDouble(parts[i].trim());
        }
        return vec;
    }

    public static String literal(double[] embedding) {
        return "[" + IntStream.range(0, embedding.length)
                .mapToObj(i -> String.format(java.util.Locale.ROOT, "%.6f", embedding[i]))
                .collect(Collectors.joining(",")) + "]";
    }

    /** Mean vector (used to aggregate authorized-photo embeddings into a profile vector). */
    public static double[] mean(double[][] vectors) {
        int dim = vectors[0].length;
        double[] out = new double[dim];
        for (double[] v : vectors) {
            for (int i = 0; i < dim; i++) {
                out[i] += v[i];
            }
        }
        for (int i = 0; i < dim; i++) {
            out[i] /= vectors.length;
        }
        double norm = 0;
        for (double d : out) norm += d * d;
        norm = Math.sqrt(norm);
        if (norm > 1e-9) {
            for (int i = 0; i < dim; i++) out[i] /= norm;
        }
        return out;
    }
}