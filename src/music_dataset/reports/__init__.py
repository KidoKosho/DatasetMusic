"""Reports package."""

from music_dataset.reports.capabilities import generate_capabilities_report
from music_dataset.reports.generator import QualityReportGenerator

__all__ = ["generate_capabilities_report", "QualityReportGenerator"]
