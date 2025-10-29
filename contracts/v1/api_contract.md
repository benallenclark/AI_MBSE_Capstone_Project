# API Contract: Analyze Response (v1)

- **Path:** `POST /v1/analyze` and `POST /v1/analyze/upload`
- **Versioning:** Path version `/v1` + field `schema_version`.
- **Stability:** Backward compatible; **fields are additive only**.

## Response (`AnalyzeResponse`)

```json
{
  "schema_version": "1.0",
  "model": { "vendor": "sparx", "version": "17.1" },
  "maturity_level": 2,
  "summary": { "total": 2, "passed": 2, "failed": 0, "duration_ms": 87 },
  "results": [
    {
      "id": "mml_1:count_tables",
      "mml": 1,
      "passed": true,
      "duration_ms": 12,
      "details": {
        "vendor": "sparx",
        "version": "17.1",
        "missing_tables": [],
        "unexpected_tables": [],
        "table_counts": {
          "t_object": true,
          "t_connector": true,
          "t_package": true
        },
        "row_counts": { "t_object": 722, "t_connector": 373, "t_package": 46 },
        "total_rows": 1141,
        "counts": { "passed": 3, "failed": 0, "missing": 0, "unexpected": 0 },
        "evidence": {
          "passed": [
            { "table": "t_object", "rows": 722 },
            { "table": "t_connector", "rows": 373 },
            { "table": "t_package", "rows": 46 }
          ],
          "failed": []
        },
        "capabilities": { "counts": true, "sql": true, "per_table": true }
      }
    },
    {
      "id": "mml_2:block_has_port",
      "mml": 2,
      "passed": true,
      "duration_ms": 75,
      "details": {
        "vendor": "sparx",
        "version": "17.1",
        "blocks_total": 15,
        "blocks_with_ports": 15,
        "blocks_missing_ports": 0,
        "counts": { "passed": 15, "failed": 0 },
        "evidence": {
          "passed": [
            {
              "block_id": 101,
              "block_guid": "{...}",
              "block_name": "Antenna",
              "port_count": 3
            }
          ],
          "failed": []
        },
        "capabilities": { "sql": true, "per_block": true }
      }
    }
  ]
}
```
