import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.models import ImageryAnalysis, SpatialAnalytics, SpatialFeature
from typing import List

class PDFService:
    @classmethod
    def generate_analysis_pdf(
        cls,
        analysis: ImageryAnalysis,
        analytics: SpatialAnalytics | None,
        features: List[SpatialFeature],
        benchmarks: List['BenchmarkDefinition'] = None
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
            [Paragraph("<b>Coordinate System</b>", body_style), Paragraph(analysis.original_crs or analysis.normalized_crs or "EPSG:4326", body_style)],
            [Paragraph("<b>Population</b>", body_style), Paragraph(f"{analysis.population_count:,} Citizens" if analysis.population_count else "Unavailable", body_style)],
            [Paragraph("<b>Population Source</b>", body_style), Paragraph(analysis.population_source or "Unavailable", body_style)],
            [Paragraph("<b>Population Date</b>", body_style), Paragraph(analysis.population_date.strftime("%Y-%m-%d") if analysis.population_date else "Unavailable", body_style)],
            [Paragraph("<b>Formula Version</b>", body_style), Paragraph(analytics.formula_version if analytics and analytics.formula_version else "Unavailable", body_style)],
            [Paragraph("<b>Calculated At</b>", body_style), Paragraph(analytics.calculated_at.strftime("%B %d, %Y - %H:%M UTC") if analytics and analytics.calculated_at else "Unavailable", body_style)],
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

        # ---- Mode-aware coverage resolution -------------------------------------
        # Nadir segmentation stores m²-based coverage in SpatialAnalytics. Scene
        # segmentation (oblique/drone, pixel-space) stores coverage % in the analysis
        # summary; detection stores object counts. Surface whatever is actually available
        # instead of blanket "Unavailable".
        mode = (analysis.analysis_mode or "segmentation")
        summary = analysis.detection_summary or {}
        scene_cov = summary.get("class_counts") if summary.get("summary_type") == "scene_coverage_pct" else None
        det_counts = summary.get("class_counts") if summary.get("summary_type") == "detection_counts" else None

        _ana_cov = {}
        if analytics is not None:
            _ana_cov = {
                "road": analytics.road_coverage_pct, "building": analytics.building_coverage_pct,
                "tree_cover": analytics.tree_cover_pct, "water": analytics.water_cover_pct,
                "agriculture": analytics.agriculture_cover_pct, "barren_land": analytics.barren_cover_pct,
            }

        def cov(cls: str) -> str:
            v = _ana_cov.get(cls)
            if v is not None:
                return f"{v}%"
            if scene_cov and cls in scene_cov:
                return f"{scene_cov[cls]}%"
            return "N/A"

        pixel_space = mode in ("scene_segmentation", "detection") or not analysis.original_crs
        na_reason = "N/A — requires georeferenced nadir imagery"

        # Infrastructure Score KPI Table
        score_val = analytics.infrastructure_score if analytics and analytics.infrastructure_score is not None else None
        score_color = "#22C55E" if score_val is not None and score_val >= 70 else "#F59E0B" if score_val is not None and score_val >= 40 else "#EF4444"
        index_cell = (f"{score_val}/100" if score_val is not None
                      else ("N/A" if pixel_space else "Unavailable"))
        facilities_cell = ("Available" if analytics and (analytics.hospitals_per_1000 is not None or analytics.schools_per_1000 is not None)
                           else ("N/A" if pixel_space else "Unavailable"))
        kpi_data = [
            [
                Paragraph(f"<b>Infrastructure Index</b><br/><font size=18 color='{score_color}'><b>{index_cell}</b></font>", body_style),
                Paragraph(f"<b>Road Coverage</b><br/><font size=14 color='{primary_color}'><b>{cov('road')}</b></font>", body_style),
                Paragraph(f"<b>Building Coverage</b><br/><font size=14 color='{primary_color}'><b>{cov('building')}</b></font>", body_style),
                Paragraph(f"<b>Tree Cover</b><br/><font size=14 color='{primary_color}'><b>{cov('tree_cover')}</b></font>", body_style),
            ],
            [
                Paragraph(f"<b>Water Cover</b><br/><font size=14 color='{primary_color}'><b>{cov('water')}</b></font>", body_style),
                Paragraph(f"<b>Agriculture Cover</b><br/><font size=14 color='{primary_color}'><b>{cov('agriculture')}</b></font>", body_style),
                Paragraph(f"<b>Barren Cover</b><br/><font size=14 color='{primary_color}'><b>{cov('barren_land')}</b></font>", body_style),
                Paragraph(f"<b>Facilities Normalized</b><br/><font size=14 color='{primary_color}'><b>{facilities_cell}</b></font>", body_style),
            ],
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
        if pixel_space:
            note = ("<b>Note:</b> This is a "
                    + ("scene-segmentation" if mode == "scene_segmentation" else "detection" if mode == "detection" else "non-georeferenced")
                    + " analysis of pixel-space imagery. Coverage is reported as % of image area; "
                    "absolute areas (m²), the population-normalized Infrastructure Index and facility "
                    "benchmarks require georeferenced nadir imagery with a valid CRS.")
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(note, ParagraphStyle('KpiNote', parent=body_style, textColor=text_muted, fontSize=9)))
        elements.append(Spacer(1, 15))

        # Feature Breakdown Table
        elements.append(Paragraph("2. Detected Spatial Infrastructure Breakdown", section_heading))
        _SOURCE_LABEL = {
            "ai_segformer": "SegFormer AI", "ai_segformer_loveda": "SegFormer LoveDA",
            "ai_ade20k_scene": "ADE20K Scene AI", "detection_yolos": "YOLOS Detection",
            "osm_layer": "OSM GIS Layer", "openstreetmap": "OSM GIS Layer",
        }
        is_scene = scene_cov is not None
        # Scene mode reports coverage %; detection reports counts; segmentation reports m²
        area_header = "Coverage" if is_scene else ("Objects" if det_counts is not None else "Area (m²)")
        feature_rows = [["Category", "Source Engine", "Confidence", area_header, "Count"]]
        for f in features:
            props = f.properties or {}
            if is_scene and props.get("coverage_pct") is not None:
                area_cell = f"{props['coverage_pct']}%"
            elif f.area_sq_meters and f.area_sq_meters > 0:
                area_cell = f"{f.area_sq_meters:,.1f}"
            else:
                area_cell = "—"
            feature_rows.append([
                f.class_name.replace("_", " ").title(),
                _SOURCE_LABEL.get(f.source, f.source or "—"),
                f"{round((f.confidence or 0) * 100, 1)}%",
                area_cell,
                f"{f.feature_count:,}" if f.feature_count else "0",
            ])
        if len(feature_rows) == 1:
            feature_rows.append(["No features detected", "-", "-", "—", "0"])

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
        
        bench_data = [["Urban Metric Parameter", "Computed Value", "Target Standard", "Status", "Source"]]
        if analytics and analytics.component_scores:
            for key, data in analytics.component_scores.items():
                is_pct = 'cover' in key
                val_str = f"{data.get('value', 0):.2f}{'%' if is_pct else ''}"
                target_str = f"{data.get('target', 0):.2f}{'%' if is_pct else ''}"
                diff = data.get('value', 0) - data.get('target', 0)
                status = "Balanced"
                if diff < 0:
                    status = "Below Reference"
                elif diff > 0:
                    status = "Above Reference"
                
                source_str = data.get('source', 'Configured Reference')
                bench_data.append([key.replace('_', ' ').title(), val_str, target_str, status, source_str])
        else:
            bench_data.append(["No benchmark data available", "-", "-", "-", "-"])

        bench_table = Table(bench_data, colWidths=[120, 90, 90, 100, 100])
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

        elements.append(Paragraph("4. Data Provenance", section_heading))
        _ai_model = summary.get("model") or (features[0].model_name if features and features[0].model_name else None)
        _mode_label = {"scene_segmentation": "ADE20K scene segmentation", "detection": "COCO object detection"}.get(mode, "SegFormer LoveDA segmentation")
        _ai_prov = f"AI Derived ({_ai_model})" if _ai_model else f"AI Derived ({_mode_label})"
        prov_data = [
            ["Data Point", "Provenance Source", "Notes"],
            ["AI-Detected Classes", _ai_prov, f"{_mode_label} on input imagery"],
            ["Hospitals, Schools, Police, Fire", "OpenStreetMap (Overpass API)", "Mapped GIS layers"],
            ["Population", "User Supplied", analysis.population_source or "User input"],
            ["Coverage %, Rates, Scores", "Calculated Metric", "UrbanSense PostGIS Analytics Engine"],
            ["Benchmark Targets", "Configured Reference", "UrbanSense Benchmark Definitions"]
        ]
        prov_table = Table(prov_data, colWidths=[160, 180, 160])
        prov_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_light]),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(prov_table)
        elements.append(Spacer(1, 15))

        elements.append(Paragraph("5. Strategic Planning Recommendations", section_heading))
        rec_text = (
            "1. <b>Greenery Preservation:</b> Protect existing urban canopy cover and mandate green roofs in commercial zones.<br/>"
            "2. <b>Infrastructure Access:</b> Ensure public facilities (healthcare and schools) scale proportionally with population density.<br/>"
            "3. <b>Road Connectivity:</b> Improve arterial road connectivity in high-density informal settlement zones."
        )
        elements.append(Paragraph(rec_text, body_style))
        elements.append(Spacer(1, 15))

        elements.append(Paragraph("6. Methodology & Limitations", section_heading))
        methodology_text = (
            "<b>AI Segmentation Pipeline:</b> Imagery is tiled into sub-patches and passed through a pretrained SegFormer transformer "
            "model for semantic segmentation. Pixel masks are vector polygonized and simplified.<br/>"
            "<b>OSM GIS Enrichment:</b> OpenStreetMap Overpass queries extract amenity nodes (hospitals, schools) and informal settlement boundaries.<br/><br/>"
            "<b>Known Limitations:</b><br/>"
            "- Pretrained LoveDA model may have domain shift limitations on significantly different geographies.<br/>"
            "- Tiled inference can occasionally result in edge artifacts across tile boundaries despite overlapping sliding windows.<br/>"
            "- Infrastructure scoring is dependent on accurate user-supplied population data.<br/>"
            "- Road density is unavailable when only road polygons (and not centerlines) are detected.<br/>"
            "- Facility counts are strictly dependent on OpenStreetMap completeness in the target region."
        )
        elements.append(Paragraph(methodology_text, body_style))

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
