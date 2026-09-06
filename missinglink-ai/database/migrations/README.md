# Database migrations

Canonical source of truth: `backend/springboot/src/main/resources/db/migration` and
`.../db/seed`. Flyway runs them automatically when the Spring Boot backend starts
(`spring.flyway.locations=classpath:db/migration,classpath:db/seed`).

The files mirrored here are for **standalone review / manual `psql` application**:

```bash
psql -U missinglink -d missinglink -f database/migrations/V1__init_schema.sql
psql -U missinglink -d missinglink -f database/migrations/V2__seed_base.sql
psql -U missinglink -d missinglink -f database/seed/V100__demo_data.sql
```

> Keep the files in `database/` in sync with the classpath originals. When adding a
> new migration, bump the version number (`V{n}__...`) and add it to both locations.
