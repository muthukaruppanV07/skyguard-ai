package com.missinglink.geospatial;

import com.missinglink.cases.CaseAccessService;
import com.missinglink.cases.domain.MissingPersonCase;
import com.missinglink.common.ApiException;
import com.missinglink.sighting.domain.Sighting;
import com.missinglink.sighting.domain.SightingRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/** Geospatial intelligence: map markers + AI-assisted search-zone generation. */
@Service
public class GeoService {

    private final CaseAccessService access;
    private final SightingRepository sightings;
    private final GeoSql geo;

    public GeoService(CaseAccessService access, SightingRepository sightings,
                      GeoSql geo) {
        this.access = access;
        this.sightings = sightings;
        this.geo = geo;
    }

    @Transactional(readOnly = true)
    public MapView mapForCase(Long caseId) {
        MissingPersonCase c = access.requireAccess(caseId);
        List<Marker> markers = new ArrayList<>();

        if (c.getLastKnownLat() != null && c.getLastKnownLng() != null) {
            markers.add(new Marker("ACTIVE_CASE", c.getLastKnownLat(), c.getLastKnownLng(),
                    "Last known location", c.getCaseReference(), null, null, null));
        }

        for (Sighting s : sightings.findByCaseIdOrdered(caseId)) {
            if (s.getLat() == null || s.getLng() == null) {
                continue;
            }
            String type = switch (s.getStatus()) {
                case VERIFIED -> "VERIFIED_LEAD";
                case REJECTED, DUPLICATE -> "UNVERIFIED_REPORT";
                default -> "POTENTIAL_SIGHTING";
            };
            markers.add(new Marker(type, s.getLat(), s.getLng(),
                    s.getLocationName() == null ? s.getSightingReference() : s.getLocationName(),
                    c.getCaseReference(), s.getSightingReference(), s.getStatus().name(),
                    s.getCapturedAt() == null ? null : s.getCapturedAt().toString()));
        }

        for (GeoSql.ClusterView cv : geo.clustersForCase(caseId)) {
            markers.add(new Marker("EVIDENCE_CLUSTER", cv.lat(), cv.lng(), cv.title(),
                    c.getCaseReference(), null, cv.sourceCount() + " reports", null));
        }

        List<GeoSql.ZoneView> zones = geo.zonesForCase(caseId);

        return new MapView(c.getCaseReference(), markers, zones,
                List.of(GeoSql.ZoneView.AI_DISCLAIMER));
    }

    /** Generate AI-assisted search zones — suggestion only, requires investigator review. */
    @Transactional
    public List<GeoSql.ZoneView> generateSearchZones(Long caseId) {
        MissingPersonCase c = access.requireAccess(caseId);
        if (c.getLastKnownLat() == null || c.getLastKnownLng() == null) {
            throw ApiException.badRequest("Case has no last-known coordinates");
        }

        long elapsedHours = c.getLastKnownAt() == null ? 0
                : Math.max(0, Duration.between(c.getLastKnownAt(), Instant.now()).toHours());
        boolean hasVehicle = c.getTransportation() != null
                && !c.getTransportation().isBlank()
                && !c.getTransportation().toLowerCase().contains("walk");

        // Walking radius
        double walkRadius = 3.0;
        geo.createZone(caseId, "HIGH_PRIORITY", 1, walkRadius,
                c.getLastKnownLat(), c.getLastKnownLng(),
                "Within walking distance of last known location.", true);

        // Extended radius based on elapsed time & transport
        double durationHours = elapsedHours;
        double extended = (hasVehicle ? 30.0 : 10.0) + Math.min(20.0, durationHours * 0.5);
        geo.createZone(caseId, "MEDIUM_PRIORITY", 2, extended,
                c.getLastKnownLat(), c.getLastKnownLng(),
                "Reasonable travel range given elapsed time (AI estimate).", true);

        // Lead clusters around verified sightings
        for (Sighting s : sightings.findByCaseIdOrdered(caseId)) {
            if (s.getStatus() == Sighting.Status.VERIFIED && s.getLat() != null && s.getLng() != null) {
                geo.createZone(c.getId(), "LEAD_CLUSTER", 1, 1.0,
                        s.getLat(), s.getLng(),
                        "Verified sighting at " + s.getLocationName() + " — concentrate search.", true);
            }
        }
        return geo.zonesForCase(caseId);
    }

    /** Alias for reading existing zones (no generation). */
    @Transactional(readOnly = true)
    public List<GeoSql.ZoneView> searchZones(Long caseId) {
        access.requireAccess(caseId);
        return geo.zonesForCase(caseId);
    }

    public record MapView(String caseReference, List<Marker> markers, List<GeoSql.ZoneView> zones,
                          List<String> disclaimers) {
    }

    public record Marker(String type, double lat, double lng, String label, String caseReference,
                         String sightingReference, String detail, String timestamp) {
    }
}