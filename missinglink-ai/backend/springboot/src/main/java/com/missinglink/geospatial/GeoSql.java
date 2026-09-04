package com.missinglink.geospatial;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * PostGIS operations via JdbcTemplate. Geometry columns stay out of the JPA mapping;
 * creation and reads are expressed with PostGIS functions directly.
 */
@Component
public class GeoSql {

    private final JdbcTemplate jdbc;

    public GeoSql(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void createZone(Long caseId, String zoneType, int priority, double radiusKm,
                           double lat, double lng, String rationale, boolean aiGenerated) {
        jdbc.update("""
                        INSERT INTO search_zones
                          (case_id, zone_type, priority, radius_km, geom, rationale, ai_generated, reviewed, created_at)
                        VALUES
                          (?, ?, ?, ?, ST_Buffer(ST_SetSRID(ST_MakePoint(?, ?), 4326)::geography, ?)::geometry,
                           ?, ?, false, now())
                        """,
                caseId, zoneType, priority, radiusKm, lng, lat, radiusKm * 1000, rationale, aiGenerated);
    }

    public List<ZoneView> zonesForCase(Long caseId) {
        return jdbc.query("""
                        SELECT id, zone_type, priority, radius_km, rationale, ai_generated, reviewed,
                               ST_AsGeoJSON(geom) AS geojson
                        FROM search_zones
                        WHERE case_id = ?
                        ORDER BY priority, created_at
                        """,
                (rs, i) -> new ZoneView(
                        rs.getLong("id"),
                        rs.getString("zone_type"),
                        rs.getInt("priority"),
                        rs.getDouble("radius_km"),
                        rs.getString("rationale"),
                        rs.getBoolean("ai_generated"),
                        rs.getBoolean("reviewed"),
                        rs.getString("geojson")),
                caseId);
    }

    public List<ClusterView> clustersForCase(Long caseId) {
        return jdbc.query("""
                        SELECT DISTINCT c.id, c.title, c.source_count, c.first_timestamp, c.last_timestamp,
                               ST_X(c.centroid) AS lat, ST_Y(c.centroid) AS lng
                        FROM evidence_clusters c
                        JOIN sightings s ON s.evidence_cluster_id = c.id
                        WHERE s.case_id = ?
                        """,
                (rs, i) -> new ClusterView(
                        rs.getLong("id"),
                        rs.getString("title"),
                        rs.getInt("source_count"),
                        rs.getString("first_timestamp"),
                        rs.getString("last_timestamp"),
                        rs.getDouble("lat"),
                        rs.getDouble("lng")),
                caseId);
    }

    public record ZoneView(Long id, String zoneType, int priority, double radiusKm,
                           String rationale, boolean aiGenerated, boolean reviewed, String geojson) {
        public static final String AI_DISCLAIMER = "AI-assisted search suggestion — requires investigator review.";
    }

    public record ClusterView(Long id, String title, int sourceCount, String firstTimestamp,
                              String lastTimestamp, double lat, double lng) {
    }
}