---
name: academic-paper-generator
description: Generate professional 2-column academic papers based on a GitHub project or topic. Uses WeasyPrint for PDF rendering and generates beautiful SVG visualizations.
license: MIT
compatibility: Requires python with weasyprint (`pip install weasyprint --break-system-packages`)
metadata:
  author: OpenCLAW Hive
  version: "1.0"
---

# Academic Paper Generator Skill

**CRITICAL RULE:** You are a professional, honest Academic Paper Research Agent. All references and citations you mention must be 100% confirmed. No errors or false information are allowed.

**IMPORTANT AUTHOR DATA INJECTION:** You must ALWAYS ask the user for their Author details (Name, Institution, GitHub, ResearchGate, etc.) or extract them from the ongoing conversation context. **DO NOT** use default names like "Francisco Angulo de Lafuente" unless the user explicitly is that person. Dynamically replace all `[AUTHOR_NAME]` and `[AUTHOR_SOCIALS]` placeholders with the real user's data.

## 1. PROJECT ANALYSIS
- Explore the provided GitHub repository using `read_url_content`, or run code analysis tools on the local repository.
- Identify technologies, architecture, methodology, and results.
- Extract key technical information: configurations, metrics, specifications.

## 2. PAPER STRUCTURE (15,000+ words)
Include these mandatory sections:

**Frontmatter:**
- Descriptive academic title
- `[AUTHOR_NAME]` and affiliation
- Complete abstract (200-300 words)
- Keywords (8-10 terms)

**Main Body:**
1. **Introduction** (contextualization, motivation, contributions)
2. **Theoretical Framework** (mathematical and physical foundations with equations)
3. **System Architecture** (detailed design description)
4. **Implementation Details** (technologies, optimizations, code)
5. **Results** (metrics, convergence, evaluation)
6. **Hardware/Applications** (compatibility, deployment, use cases)
7. **Comparisons** (vs other methods/approaches)
8. **Limitations & Future Work**
9. **Conclusions**
10. **Acknowledgments**
11. **References** (40+ references with complete DOIs)

## 3. VISUAL ELEMENTS (Embedded SVG)
Create minimum 5 professional figures:
- Architecture diagrams with data flow
- Convergence/performance graphs with axes, legends, annotations
- Processing pipelines with visual stages
- Algorithm/process representations

**SVG Specifications:**
- Dimensions: `viewBox="0 0 600 200-300"`
- Professional colors with gradients
- Readable typography (8-11pt)
- Arrows, connectors, annotations
- Descriptive legends and labels

Create minimum 7 tables with:
- Descriptive captions
- Headers with dark background (`#333`)
- Borders and zebra-striping
- Precise technical data
- Comparisons when relevant

## 4. PROFESSIONAL HTML FORMAT

Use the following HTML template, replacing the brackets with the generated content and the dynamic user data:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>[Paper Title]</title>
    <style>
        /* CRITICAL CSS */
        @page { size: A4; margin: 2cm; }
        
        body {
            font-family: 'Times New Roman', Times, serif;
            font-size: 10pt;
            line-height: 1.5;
            margin: 0;
            padding: 20px;
            background: white;
        }
        
        .container {
            max-width: 210mm;
            margin: 0 auto;
            padding: 20mm;
        }
        
        /* 2-COLUMN FORMAT */
        .two-column {
            column-count: 2;
            column-gap: 20px;
            text-align: justify;
        }
        
        /* Prevent page breaks */
        h2, h3, h4 { break-after: avoid; }
        .figure, table, .equation { break-inside: avoid; }
        
        /* Title styles */
        h1 { font-size: 18pt; text-align: center; margin: 20px 0 10px 0; }
        h2 { font-size: 12pt; margin: 15px 0 8px 0; }
        h3 { font-size: 11pt; font-style: italic; }
        
        /* Figures and tables */
        .figure { margin: 15px 0; text-align: center; }
        .figure-caption { font-size: 9pt; text-align: left; padding: 0 10px; }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 9pt;
            margin: 15px 0;
        }
        th { background: #333; color: white; padding: 8px; }
        td { border: 1px solid #ddd; padding: 6px; }
        tr:nth-child(even) { background: #f9f9f9; }
        
        /* Equations */
        .equation {
            text-align: center;
            margin: 15px 0;
            font-style: italic;
        }
        .equation-number { float: right; }
        
        /* Abstract */
        .abstract {
            margin: 20px 0;
            padding: 15px;
            background: #f9f9f9;
            border-left: 4px solid #333;
        }
        
        /* References */
        .references { font-size: 9pt; }
        .references ol { padding-left: 20px; }
        .references li { margin: 8px 0; text-align: justify; }
        
        @media print {
            .container { max-width: 100%; padding: 0; }
            body { padding: 0; }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Title, authors, affiliation -->
        <h1>[Paper Title]</h1>
        
        <div class="authors">
            [AUTHOR_NAME]
        </div>
        
        <div class="affiliation">
            [Research Group/Institution]<br>
            [Project/Competition Name]<br>
            Contact: See social media links at end of document
        </div>
        
        <!-- Abstract with keywords -->
        <div class="abstract">
            <strong>Abstract:</strong> [Abstract Content]<br><br>
            <strong>Keywords:</strong> [Keywords]
        </div>
        
        <div class="two-column">
            <!-- All paper content -->
        </div>
        
        <!-- Final section with contact/social media -->
        <hr style="margin: 30px 0; border: none; border-top: 2px solid #333;">
        
        <div style="text-align: center; margin-top: 30px; font-size: 9pt; color: #666;">
            <p><strong>Manuscript submitted to:</strong> [Journal/Conference Name]</p>
            <p><strong>Date:</strong> [Current Date]</p>
            <p style="margin-top: 15px;"><strong>Author Contact & Publications:</strong></p>
            <p style="line-height: 1.8; margin-top: 8px;">
                [AUTHOR_SOCIALS_HTML_LINKS]
            </p>
        </div>
    </div>
</body>
</html>
```

## 5. DETAILED TECHNICAL CONTENT

**Mathematical equations:**
- Number sequentially: (1), (2), (3)...
- Use standard notation (LaTeX-style in text)
- Explain each variable after the equation

**Citations and references:**
- Format: [1], [2], [3] in text
- Complete list at the end with: Authors, year, title in italics, Journal/conference, DOI when available.

**Tables & Figures:**
- Tables must have bold captions before the table.
- Figures must have detailed captions explaining all elements, embedded as vector SVGs.

## 6. PDF GENERATION

**Step 1:** Create HTML file in an accessible directory (e.g. `[workspace]/outputs/[name].html`). Use the your tools to write this file.
**Step 2:** Ensure WeasyPrint is installed (`pip install weasyprint --break-system-packages -q`). Wait for it to finish.
**Step 3:** Use the `run_command` tool to convert to PDF in Python:
```bash
python -c "
from weasyprint import HTML, CSS
HTML(filename='outputs/[name].html').write_pdf(
    'outputs/[name].pdf',
    stylesheets=[CSS(string='@page { size: A4 portrait; margin: 2cm; }')]
)
"
```

## 7. FINAL CHECKLIST

Before notifying the user, verify:
- [ ] Paper is extremely comprehensive and detailed.
- [ ] Perfect 2-column format.
- [ ] Minimum 5 professional SVG figures included in the HTML inline.
- [ ] Minimum 7 tables with real data.
- [ ] 40+ bibliographic references.
- [ ] Complete abstract and keywords.
- [ ] Equations numbered correctly.
- [ ] HTML file rendered correctly and saved.
- [ ] PDF generated with WeasyPrint (NOT wkhtmltopdf).
- [ ] Author info correctly interpolated with the user's specific data `[AUTHOR_NAME]`.
- [ ] All social media links `[AUTHOR_SOCIALS]` correctly formatted.

## 8. DELIVERY TO USER

Upon completion, use the `notify_user` to provide the final output paths:
```
Professional academic paper completed!

[View your HTML paper](file:///absolute/path/to/outputs/[name].html)
[View your PDF paper](file:///absolute/path/to/outputs/[name].pdf)

**Content Summary:**
- Comprehensive technical analysis of the project
- 5+ professional SVG figures
- 7+ technical data tables
- 40+ complete bibliographic references

**Author Information Indexed:**
[AUTHOR_NAME]
[AUTHOR_SOCIALS_AS_MARKDOWN_LINKS]
```
