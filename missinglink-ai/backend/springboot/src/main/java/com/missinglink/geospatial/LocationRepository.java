package com.missinglink.geospatial;

import com.missinglink.cases.domain.MissingPersonCase;
import com.missinglink.sighting.domain.Sighting;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface LocationRepository extends JpaRepository<Location, Long> {

    List<Location> findByCaseRefId(Long caseId);

    @Query("SELECT l FROM Location l WHERE l.caseRef.id = :caseId ORDER BY l.occurredAt NULLS LAST")
    List<Location> findByCaseIdOrdered(@Param("caseId") Long caseId);

    Optional<Location> findFirstByCaseRefIdAndLocationType(Long caseId, Location.LocationType type);
}