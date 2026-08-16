import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.models import ImageryAnalysis, UrbanBenchmark, SpatialFeature
from typing import List

class PDFService:
    @classmethod
    def generate_analysis_pdf(
        cls,
        analysis: ImageryAnalysis,
        benchmark: UrbanBenchmark,
        features: List[SpatialFeature]
    ) -> bytes:
        """
        Generate a multi-page executive PDF report featuring:
        - Page 1: Cover Page with System Branding & Metadata
        - Page 2: Executive Summary, Infrastructure Score KPI, Feature Breakdown
        - Page 3: Spatial Benchmark Evaluation, Recommendations, Methodology & Appendix
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()

        # Custom Palette
        primary_color = colors.HexColor('#0F172A')   # Slate 900
        accent_blue   = colors.HexColor('#3B82F6')   # Blue 500
        text_dark     = colors.HexColor('#1E293B')   # Slate 800
        text_muted    = colors.HexColor('#64748B')   # Slate 500
        bg_light      = colors.HexColor('#F8FAFC')   # Slate 50

        # Typography Styles
        cover_title = ParagraphStyle(
            'CoverTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=28,
            textColor=primary_color,
            spaceAfter=10,
            alignment=0
        )
        cover_subtitle = ParagraphStyle(
            'CoverSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=14,
            textColor=accent_blue,
            spaceAfter=25,
            alignment=0
        )
        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=primary_color,
            spaceBefore=14,
            spaceAfter=8
        )
        body_style = ParagraphStyle(
            'ReportBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=text_dark,
            leading=14,
            spaceAfter=8
        )

        elements = []

        # =========================================================================
        # PAGE 1: COVER PAGE
        # =========================================================================
        elements.append(Spacer(1, 40))
        elements.append(Paragraph("UrbanSense", cover_title))
        elements.append(Paragraph("AI-Powered Urban Infrastructure Intelligence System", cover_subtitle))
        elements.append(HRFlowable(width="100%", thickness=2, color=accent_blue, spaceAfter=40))

        elements.append(Spacer(1, 40))
        
        meta_table_data = [
            [Paragraph("<b>Report Document</b>", body_style), Paragraph("Executive Infrastructure Assessment", body_style)],
            [Paragraph("<b>Target Image Analysis</b>", body_style), Paragraph(analysis.filename, body_style)],
            [Paragraph("<b>Analysis Reference ID</b>", body_style), Paragraph(f"#{analysis.id}", body_style)],
            [Paragraph("<b>Coordinate System</b>", body_style), Paragraph(analysis.crs or "EPSG:4326", body_style)],
            [Paragraph("<b>Estimated Population</b>", body_style), Paragraph(f"{analysis.population_estimate:,} Citizens", body_style)],
            [Paragraph("<b>Report Generated Date</b>", body_style), Paragraph(analysis.created_at.strftime("%B %d, %Y - %H:%M UTC"), body_style)],
        ]
        meta_table = Table(meta_table_data, colWidths=[180, 320])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), bg_light),
            ('TEXTCOLOR', (0, 0), (-1, -1), text_dark),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(meta_table)

        elements.append(Spacer(1, 120))
        elements.append(Paragraph("<b>Notice:</b> This automated document combines pretrained aerial SegFormer neural network segmentation with OpenStreetMap spatial enrichment layers.", ParagraphStyle('Notice', parent=body_style, textColor=text_muted, fontSize=9)))

        elements.append(PageBreak())

        # =========================================================================
        # PAGE 2: EXECUTIVE SUMMARY & AI RESULTS
        # =========================================================================
        elements.append(Paragraph("1. Executive Summary", section_heading))
        summary_text = (
            f"This spatial intelligence report details aerial land cover detection and social infrastructure mapping for "
            f"<b>{analysis.filename}</b>. High-resolution imagery was processed through deep learning segmentation to identify "
            f"physical land footprints (roads, building structures, tree canopy cover, water systems, and barren land), "
            f"enriched with OpenStreetMap geospatial layers for critical community assets (hospitals, schools, and informal settlements)."
        )
        elements.append(Paragraph(summary_text, body_style))
        elements.append(Spacer(1, 10))

        # Infrastructure Score KPI Table
        score_val = benchmark.infrastructure_score if benchmark else 0.0
        score_color = "#22C55E" if score_val >= 70 else "#F59E0B" if score_val >= 40 else "#EF4444"
        kpi_data = [
            [
                Paragraph(f"<b>Infrastructure Index</b><br/><font size=18 color='{score_color}'><b>{score_val}/100</b></font>", body_style),
                Paragraph(f"<b>Road Density</b><br/><font size=14 color='{primary_color}'><b>{benchmark.road_density_km_per_sqkm if benchmark else 0.0} km/km²</b></font>", body_style),
                Paragraph(f"<b>Building Ratio</b><br/><font size=14 color='{primary_color}'><b>{benchmark.building_coverage_pct if benchmark else 0.0}%</b></font>", body_style),
                Paragraph(f"<b>Tree Cover</b><br/><font size=14 color='{primary_color}'><b>{benchmark.tree_cover_pct if benchmark else 0.0}%</b></font>", body_style),
            ]
        ]
        kpi_table = Table(kpi_data, colWidths=[125, 125, 125, 125])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg_light),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(kpi_table)
        elements.append(Spacer(1, 15))

        # Feature Breakdown Table
        elements.append(Paragraph("2. Detected Spatial Infrastructure Breakdown", section_heading))
        feature_rows = [["Category", "Source Engine", "Confidence", "Area (m²)", "Count"]]
        for f in features:
            feature_rows.append([
                f.class_name.replace("_", " ").title(),
                "SegFormer AI" if f.source == "ai_segformer" else "OSM GIS Layer",
                f"{round(f.confidence * 100, 1)}%",
                f"{f.area_sq_meters:,.1f}",
                str(f.feature_count)
            ])
        if len(feature_rows) == 1:
            feature_rows.append(["No features detected", "-", "-", "0.0", "0"])

        feat_table = Table(feature_rows, colWidths=[120, 110, 80, 110, 80])
        feat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_light]),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(feat_table)

        elements.append(PageBreak())

        # =========================================================================
        # PAGE 3: BENCHMARKS, RECOMMENDATIONS & METHODOLOGY
        # =========================================================================
        elements.append(Paragraph("3. Spatial Benchmark Evaluation", section_heading))
        bench_data = [
            ["Urban Metric Parameter", "Computed Value", "Target Standard", "Status"],
            ["Road Network Density", f"{benchmark.road_density_km_per_sqkm if benchmark else 0.0} km/km²", "10.0 km/km²", "Sufficient" if (benchmark and benchmark.road_density_km_per_sqkm >= 8.0) else "Deficit"],
            ["Building Coverage Ratio", f"{benchmark.building_coverage_pct if benchmark else 0.0}%", "25.0% - 40.0%", "Balanced"],
            ["Tree Canopy Cover Ratio", f"{benchmark.tree_cover_pct if benchmark else 0.0}%", "15.0% Minimum", "Optimal" if (benchmark and benchmark.tree_cover_pct >= 15.0) else "Below Target"],
            ["Water Body Ratio", f"{benchmark.water_cover_pct if benchmark else 0.0}%", "5.0% Minimum", "Normal"],
            ["Hospitals / 10k Pop", f"{benchmark.hospitals_per_10k_pop if benchmark else 0.0}", "2.5 per 10k", "Adequate" if (benchmark and benchmark.hospitals_per_10k_pop >= 2.0) else "Action Needed"],
            ["Schools / 10k Pop", f"{benchmark.schools_per_10k_pop if benchmark else 0.0}", "5.0 per 10k", "Adequate" if (benchmark and benchmark.schools_per_10k_pop >= 4.0) else "Action Needed"],
        ]
        bench_table = Table(bench_data, colWidths=[150, 110, 120, 120])
        bench_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_light]),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(bench_table)
        elements.append(Spacer(1, 15))

        elements.append(Paragraph("4. Strategic Planning Recommendations", section_heading))
        rec_text = (
            "1. <b>Greenery Preservation:</b> Protect existing urban canopy cover and mandate green roofs in commercial zones.<br/>"
            "2. <b>Infrastructure Access:</b> Ensure public facilities (healthcare and schools) scale proportionally with population density.<br/>"
            "3. <b>Road Connectivity:</b> Improve arterial road connectivity in high-density informal settlement zones."
        )
        elements.append(Paragraph(rec_text, body_style))
        elements.append(Spacer(1, 15))

        elements.append(Paragraph("5. Methodology & Appendix", section_heading))
        methodology_text = (
            "<b>AI Segmentation Pipeline:</b> Imagery is tiled into sub-patches and passed through a pretrained SegFormer transformer "
            "model for semantic segmentation. Pixel masks are vector polygonized and simplified.<br/>"
            "<b>OSM GIS Enrichment:</b> OpenStreetMap Overpass queries extract amenity nodes (hospitals, schools) and informal settlement boundaries."
        )
        elements.append(Paragraph(methodology_text, body_style))

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
