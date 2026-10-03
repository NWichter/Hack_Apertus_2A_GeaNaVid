$track = Split-Path $PSScriptRoot -Parent
docker run --rm -v "${track}:/data" -w /data pandoc/core:latest technical_report.md -t typst --shift-heading-level-by=-1 -o report/body.typ
docker run --rm -v "${track}:/data" -w /data ghcr.io/typst/typst:latest compile report/main.typ Apertool_Report.pdf
