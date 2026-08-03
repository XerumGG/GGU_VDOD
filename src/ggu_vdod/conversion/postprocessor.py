"""yt-dlp post-processing adapter for local FFmpeg conversions."""

import os

from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor
from yt_dlp.utils import replace_extension


class LocalMediaConvertorPP(FFmpegPostProcessor):
    """Convert a finished file locally to the selected container/codec."""

    def __init__(self, downloader, target_ext, output_args=None, fallback_args=None):
        super().__init__(downloader)
        self.target_ext = target_ext.casefold()
        self.output_args = list(output_args or [])
        self.fallback_args = list(fallback_args or [])

    def run(self, info):
        source_path = info["filepath"]
        source_ext = (info.get("ext") or os.path.splitext(source_path)[1][1:]).casefold()
        requires_conversion = source_ext != self.target_ext or bool(self.output_args)
        if not requires_conversion:
            self.to_screen(f"Keeping existing {self.target_ext.upper()} media file: {source_path}")
            return [], info

        same_extension = source_ext == self.target_ext
        temporary_path = replace_extension(
            source_path,
            f"ggu-converted.{self.target_ext}" if same_extension else self.target_ext,
            source_ext,
        )
        destination = temporary_path
        args = self.output_args or self.fallback_args or ["-c", "copy"]
        self.to_screen(f"Converting {source_ext.upper()} to {self.target_ext.upper()}: {destination}")
        try:
            self.run_ffmpeg(source_path, destination, args)
            if same_extension:
                os.replace(temporary_path, source_path)
                destination = source_path
                files_to_delete = []
            else:
                files_to_delete = [source_path]
        finally:
            if same_extension and os.path.isfile(temporary_path):
                try:
                    os.remove(temporary_path)
                except OSError:
                    pass

        info["filepath"] = destination
        info["format"] = info["ext"] = self.target_ext
        return files_to_delete, info
