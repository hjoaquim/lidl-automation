# lidl-automation

Automation that turns CSV data into chart images and assembles them into slides.

## Pipeline

```mermaid
flowchart LR
    src[/"Source: ?"/] --> csv[CSVs]

    subgraph auto [Automation layer]
        chart[CSV to chart] --> imgs[Images to slides]
    end

    csv --> chart
    imgs --> slides[Slides]
```

## Open questions

1. Where do the CSVs come from (the "Source: ?" box)?
2. Where does the automation run?
   1. Google Apps Script
   2. Cloud Run (GCP)
