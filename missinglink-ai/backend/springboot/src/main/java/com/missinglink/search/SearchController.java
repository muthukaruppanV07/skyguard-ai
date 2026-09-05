package com.missinglink.search;

import com.missinglink.cases.api.CaseController;
import com.missinglink.cases.domain.MissingPersonCase;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/search")
public class SearchController {

    private final SearchService searchService;

    public SearchController(SearchService searchService) {
        this.searchService = searchService;
    }

    @GetMapping("/cases")
    public ResponseEntity<List<CaseController.CaseSummary>> search(
            @RequestParam(required = false) String q,
            @RequestParam(required = false) Integer minAge,
            @RequestParam(required = false) Integer maxAge,
            @RequestParam(required = false) String priority,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String location,
            @RequestParam(defaultValue = "true") boolean publicOnly) {

        MissingPersonCase.PriorityLevel prio = priority == null ? null : MissingPersonCase.PriorityLevel.valueOf(priority);
        MissingPersonCase.Status st = status == null ? null : MissingPersonCase.Status.valueOf(status);
        List<MissingPersonCase> results = searchService.searchCases(
                new SearchService.SearchQuery(q, minAge, maxAge, prio, st, location, publicOnly));
        return ResponseEntity.ok(results.stream().map(CaseController.CaseSummary::from).toList());
    }
}