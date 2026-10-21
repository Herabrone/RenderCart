from collections.abc import Callable, Sequence
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfReader

from rendercart.registry.models import ToolManifest, ToolOutput

_MAX_BATCH_RESULT_BYTES = 500_000_000


def credits_for_inputs(tool: ToolManifest, input_paths: Sequence[Path]) -> int:
    """Charge each document's page bands independently, as separate runs would."""
    return sum(
        tool.credits_for_pages(len(PdfReader(path, strict=True).pages)) for path in input_paths
    )


def execution_timeout(tool: ToolManifest, input_count: int, *, batch_mode: bool) -> int:
    if not batch_mode:
        return tool.timeout_s
    run_count = input_count // 2 if tool.slug == "merge-pdf" else input_count
    return min(tool.timeout_s * max(1, run_count), 86_400)


def _groups(tool: ToolManifest, input_paths: Sequence[Path]) -> list[list[Path]]:
    if tool.slug == "merge-pdf":
        if len(input_paths) % 2:
            raise ValueError("batch_merge_requires_file_pairs")
        return [list(input_paths[index : index + 2]) for index in range(0, len(input_paths), 2)]
    return [[path] for path in input_paths]


def run_batch(
    tool: ToolManifest,
    input_paths: Sequence[Path],
    output_dir: Path,
    options: dict[str, object],
    progress: Callable[[int], None] | None = None,
) -> ToolOutput:
    if not tool.batchable or tool.runner is None:
        raise ValueError("batch_mode_not_supported")
    if len(input_paths) < 2 or len(input_paths) > tool.batch_max_files:
        raise ValueError("batch_file_count_out_of_range")
    groups = _groups(tool, input_paths)
    archive_path = output_dir / "batch-results.zip"
    total_size = 0
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for index, group in enumerate(groups, start=1):
            item_dir = output_dir / f"batch-item-{index:03d}"
            item_dir.mkdir(mode=0o700)
            if progress:
                progress(50 + int(35 * (index - 1) / len(groups)))
            result = tool.runner(input_paths=group, output_dir=item_dir, **options)
            if not isinstance(result, ToolOutput):
                raise ValueError("invalid_tool_output")
            if result.locked_path is not None:
                raise ValueError("locked_results_not_supported_in_batch")
            result_path = result.path.resolve()
            if not result_path.is_relative_to(item_dir.resolve()) or not result_path.is_file():
                raise ValueError("invalid_batch_output_path")
            result_size = result_path.stat().st_size
            if result_size <= 0:
                raise ValueError("empty_output")
            total_size += result_size
            if total_size > _MAX_BATCH_RESULT_BYTES:
                raise ValueError("batch_output_too_large")
            if tool.slug == "merge-pdf":
                label = f"merge-{index:03d}"
            else:
                label = f"{index:03d}-{group[0].stem[:80]}"
            safe_filename = Path(result.filename).name
            archive.write(result_path, arcname=f"{label}/{safe_filename}")
    return ToolOutput(archive_path, archive_path.name, "application/zip")
