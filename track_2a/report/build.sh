#!/bin/sh
cd "$(dirname "$0")/.." || exit 1
docker run --rm -v "$PWD:/data" -w /data pandoc/core:latest technical_report.md -t typst --shift-heading-level-by=-1 -o report/body.typ
docker run --rm -v "$PWD:/data" -w /data ghcr.io/typst/typst:latest compile report/main.typ Apertool_Report.pdf
