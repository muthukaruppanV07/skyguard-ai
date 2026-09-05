package com.missinglink.geospatial;

import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/geo")
public class GeoController {

    private final GeoService geoService;

    public GeoController(GeoService geoService) {
        this.geoService = geoService;
    }

    @GetMapping("/cases/{caseId}/map")
    @PreAuthorize("hasAuthority('geo:view')")
    public ResponseEntity<GeoService.MapView> map(@PathVariable Long caseId) {
        return ResponseEntity.ok(geoService.mapForCase(caseId));
    }

    @PostMapping("/cases/{caseId}/search-zones")
    @PreAuthorize("hasAuthority('geo:write')")
    public ResponseEntity<List<GeoSql.ZoneView>> generateZones(@PathVariable Long caseId) {
        return ResponseEntity.ok(geoService.generateSearchZones(caseId));
    }

    @GetMapping("/cases/{caseId}/search-zones")
    @PreAuthorize("hasAuthority('geo:view')")
    public ResponseEntity<List<GeoSql.ZoneView>> zones(@PathVariable Long caseId) {
        return ResponseEntity.ok(geoService.searchZones(caseId));
    }
}