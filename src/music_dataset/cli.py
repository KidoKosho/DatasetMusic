"""Command Line Interface for Music Dataset Crawler and Vietnamese Music Pipeline."""

import json
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.table import Table

from archive_inspector.manifest import ManifestGenerator
from music_dataset.config import load_config
from music_dataset.pipeline.discover import DatasetDiscoverer
from music_dataset.pipeline.scanner import MetadataScanner
from music_dataset.pipeline.detector_phase import CandidateDetectorPhase
from music_dataset.pipeline.planner import DownloadPlanner
from music_dataset.reports.inspection_report import InspectionReportGenerator
from music_dataset.pipeline.runner import PipelineRunner
from music_dataset.pipeline.validate import DatasetValidator
from music_dataset.state.database import StateDatabase

import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(highlight=False)


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to config.yaml")
@click.pass_context
def cli(ctx: click.Context, config: Optional[str]) -> None:
    """Music Dataset Crawler & Vietnamese Music Detection Pipeline."""
    ctx.ensure_object(dict)
    cfg = load_config(Path(config) if config else None)
    ctx.obj["config"] = cfg
    ctx.obj["runner"] = PipelineRunner(config=cfg)
    ctx.obj["state_db"] = StateDatabase()


@cli.command("inspect")
@click.pass_context
def inspect_cmd(ctx: click.Context) -> None:
    """Inspect all 4 source URLs, probe HTTP headers, Range support, and generate archive manifests."""
    console.print("[bold cyan]====================================[/bold cyan]")
    console.print("[bold cyan]REMOTE ARCHIVE INSPECTION[/bold cyan]")
    console.print("[bold cyan]====================================[/bold cyan]\n")

    manifest_gen = ManifestGenerator()
    manifests = manifest_gen.generate_all()

    table = Table(title="Archive Inspection Summary")
    table.add_column("Dataset", style="cyan", no_wrap=True)
    table.add_column("Archive / Endpoint", style="white")
    table.add_column("Size (bytes)", style="magenta")
    table.add_column("Type", style="yellow")
    table.add_column("Remote Inspection", style="green")

    for ds_name, p in manifests.items():
        data = json.loads(p.read_text(encoding="utf-8"))
        for arch in data.get("archives", []):
            table.add_row(
                ds_name,
                arch.get("name", ""),
                str(arch.get("size", 0)),
                arch.get("type", ""),
                arch.get("remote_inspection", ""),
            )

    console.print(table)
    console.print(f"\n[bold green]Archive manifests generated in data/manifests/[/bold green]")
    for ds_name, p in manifests.items():
        console.print(f"  - {p}")


@cli.command("discover")
@click.pass_context
def discover_cmd(ctx: click.Context) -> None:
    """Phase 1: Discover archives, metadata files, and audio subsets across all 4 sources."""
    discoverer = DatasetDiscoverer()
    discoverer.discover_all(print_output=True)


@cli.command("scan")
@click.option("--limit", "-l", type=int, help="Limit tracks to scan per dataset")
@click.pass_context
def scan_cmd(ctx: click.Context, limit: Optional[int]) -> None:
    """Phase 2: Scan metadata fields across CSV, TXT, ID3 tags and write data/manifests/discovered.jsonl."""
    console.print("[bold cyan]Scanning metadata fields across datasets...[/bold cyan]")
    scanner = MetadataScanner()
    discovered = scanner.scan_all(limit_per_dataset=limit)

    console.print(f"[bold green]Discovered {len(discovered)} total tracks across sources.[/bold green]")
    console.print("Manifest written to: [bold]data/manifests/discovered.jsonl[/bold]")
    console.print("Report written to:   [bold]reports/files.json[/bold]")


@cli.command("detect")
@click.option("--limit", "-l", type=int, help="Limit tracks to evaluate")
@click.pass_context
def detect_cmd(ctx: click.Context, limit: Optional[int]) -> None:
    """Phase 3: Detect Vietnamese relevance using multi-evidence detectors and write candidates.jsonl."""
    console.print("[bold cyan]Running Vietnamese relevance detector on discovered tracks...[/bold cyan]")
    detector_phase = CandidateDetectorPhase()
    candidates = detector_phase.process_discovered_file(limit=limit)

    console.print(f"[bold green]Detected {len(candidates)} candidate tracks satisfying at least one Vietnamese evidence.[/bold green]")
    console.print("Manifest written to: [bold]data/manifests/candidates.jsonl[/bold]")
    console.print("Reports written to:  [bold]reports/candidates.json[/bold], [bold]reports/vietnamese_evidence.json[/bold]")


@cli.command("plan")
@click.option("--allow-full-archive", is_flag=True, default=False, help="Allow queuing full archive downloads")
@click.pass_context
def plan_cmd(ctx: click.Context, allow_full_archive: bool) -> None:
    """Phase 4: Build download queue for candidate tracks and print summary banner."""
    console.print("[bold cyan]Planning targeted downloads from candidates...[/bold cyan]")
    planner = DownloadPlanner()
    queue = planner.plan_downloads(allow_full_archive_download=allow_full_archive)

    console.print(f"[bold green]Created download queue with {len(queue)} items.[/bold green]")
    console.print("Manifest written to: [bold]data/manifests/download_queue.jsonl[/bold]")
    console.print("Report written to:   [bold]reports/download_queue.json[/bold]\n")

    # Generate full summary reports & display banner
    rep_gen = InspectionReportGenerator()
    rep_gen.generate_all_reports()
    rep_gen.print_section_30_banner()


@cli.command("download")
@click.option("--allow-full-archive", is_flag=True, default=False, help="Allow queuing full archive downloads")
@click.pass_context
def download_cmd(ctx: click.Context, allow_full_archive: bool) -> None:
    """Phase 5: Download and organize assets strictly for candidate tracks in queue."""
    from music_dataset.pipeline.targeted_downloader import TargetedDownloader

    console.print("[bold cyan]Executing targeted download and asset organization...[/bold cyan]")
    downloader = TargetedDownloader()
    res = downloader.process_queue(allow_full_archive=allow_full_archive)

    console.print("\n[bold green]Download & Asset Standardization Completed:[/bold green]")
    console.print(f"  - Tracks processed:    {res.get('processed', 0)}")
    console.print(f"  - Audio ingested:      {res.get('audio_downloaded', 0)}")
    console.print(f"  - Lyrics saved:        {res.get('lyrics_saved', 0)}")
    console.print(f"  - Artwork extracted:   {res.get('artwork_saved', 0)}")
    if res.get("blocked_archives"):
        console.print(f"  - Blocked large archives: {res.get('blocked_archives')} (use --allow-full-archive to override)")

    console.print("\n[bold]Standardized data written to:[/bold] [cyan]datasets/<dataset>/[audio, lyric, avt, label][/cyan]")


@cli.command("run")
@click.option("--dry-run", is_flag=True, default=False, help="Dry run without downloading")
@click.option("--allow-full-archive", is_flag=True, default=False, help="Allow full archive downloads")
@click.option("--limit", "-l", type=int, default=None, help="Limit tracks to inspect per dataset (default: all)")
@click.pass_context
def run_cmd(ctx: click.Context, dry_run: bool, allow_full_archive: bool, limit: Optional[int]) -> None:
    """Run the complete pipeline: inspect -> scan -> detect -> plan -> download -> validate."""
    console.print("[bold cyan]Executing Pipeline: inspect -> scan -> detect -> plan[/bold cyan]\n")

    # 1. Discover & Inspect
    discoverer = DatasetDiscoverer()
    discoverer.discover_all(print_output=True)

    # 2. Scan
    scanner = MetadataScanner()
    discovered = scanner.scan_all(limit_per_dataset=limit)

    # 3. Detect
    detector_phase = CandidateDetectorPhase()
    candidates = detector_phase.process_discovered_file(limit=limit)

    # 4. Plan
    planner = DownloadPlanner()
    queue = planner.plan_downloads(allow_full_archive_download=allow_full_archive)

    if dry_run:
        rep_gen = InspectionReportGenerator()
        rep_gen.generate_all_reports()

        console.print("\n[bold yellow]====================================[/bold yellow]")
        console.print("[bold yellow]DRY RUN PREVIEW (Không download gì)[/bold yellow]")
        console.print("[bold yellow]====================================[/bold yellow]\n")
        console.print(f"[bold]Archives:[/bold] 4 dataset manifests written to data/manifests/")
        console.print(f"[bold]Candidate tracks:[/bold] {len(candidates)}")

        reasons_count: dict = {}
        for c in candidates:
            for r in c.get("reasons", []):
                reasons_count[r] = reasons_count.get(r, 0) + 1

        console.print("\n[bold]Reasons:[/bold]")
        console.print(f"  Vietnamese lyrics:   {reasons_count.get('vietnamese_lyrics', 0)}")
        console.print(f"  Vietnamese artist:   {reasons_count.get('vietnamese_artist', 0)}")
        console.print(f"  Vietnamese title:    {reasons_count.get('vietnamese_title', 0)}")
        console.print(f"  Vietnamese metadata: {reasons_count.get('vietnamese_genre', 0) + reasons_count.get('vietnamese_annotation', 0) + reasons_count.get('vietnamese_country', 0)}")

        audio_would = sum(1 for q in queue if "audio" in q.get("assets", []) or q.get("audio_target"))
        lyrics_would = sum(1 for q in queue if "lyrics" in q.get("assets", []))
        artwork_would = sum(1 for q in queue if "artwork" in q.get("assets", []))

        console.print("\n[bold]Would download:[/bold]")
        console.print(f"  audio:   {audio_would}")
        console.print(f"  lyrics:  {lyrics_would}")
        console.print(f"  artwork: {artwork_would}\n")

        rep_gen.print_section_30_banner()
    else:
        # 5. Download & Ingest
        console.print("\n[bold cyan]Downloading and standardizing assets from queue...[/bold cyan]")
        from music_dataset.pipeline.targeted_downloader import TargetedDownloader
        downloader = TargetedDownloader()
        dl_res = downloader.process_queue(allow_full_archive=allow_full_archive)

        # 6. Validate
        console.print("\n[bold cyan]Validating standardized datasets...[/bold cyan]")
        validator = DatasetValidator(state_db=ctx.obj["state_db"])
        val_res = validator.validate_all()
        console.print(f"Validated tracks: {val_res.total_tracks_checked}, Valid: {val_res.valid_tracks}, Issues: {val_res.issues_count}")

        # 7. Reports
        rep_gen = InspectionReportGenerator()
        rep_gen.generate_all_reports()
        rep_gen.print_statistical_summary()
        rep_gen.print_section_30_banner()


@cli.command("report")
@click.pass_context
def report_cmd(ctx: click.Context) -> None:
    """Generate and display statistical report with percentage breakdowns."""
    rep_gen = InspectionReportGenerator()
    rep_gen.generate_all_reports()
    rep_gen.print_statistical_summary()
    rep_gen.print_section_30_banner()


if __name__ == "__main__":
    cli()
