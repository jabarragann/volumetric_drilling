# Notes

## Notes:
* Remember to `id` field to geometry files. The tool makers is not doing it by default.

## Syntax to define a reference marker

```json
{
    "tools":
    [
        {
            "name": "anatomy_marker",
            "json-file": "anatomy_marker2.json"
        },
        {
            "name": "drill_marker",
            "json-file": "drill_marker2.json",
            "reference": "anatomy_marker"
        }
    ],
}
```

