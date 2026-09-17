"""
複数の静止画(スライド)を、Instagramリール用の縦型動画(9:16)に変換するスクリプト。

各画像を指定秒数だけ表示するスライドショーをffmpegで生成する。
BGM等は付けない(著作権フリー音源を別途用意すれば拡張可能)。

依存: pip install imageio-ffmpeg (システムにffmpegが無くても動く)

使い方:
    python make_reel.py --images images/slide1.png images/slide2.png images/slide3.png \
        --output images/week2_reel.mp4 --seconds-per-slide 3
"""

import argparse
import os
import subprocess
import sys
import tempfile

import imageio_ffmpeg

WIDTH = 1080
HEIGHT = 1920


def build_video(image_paths: list, output_path: str, seconds_per_slide: float) -> None:
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmp_dir:
        list_path = os.path.join(tmp_dir, "concat_list.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            for path in image_paths:
                abs_path = os.path.abspath(path).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
                f.write(f"duration {seconds_per_slide}\n")
            # 最後の画像だけduration指定が無視される仕様への対策(最後をもう一度書く)
            last_abs = os.path.abspath(image_paths[-1]).replace("\\", "/")
            f.write(f"file '{last_abs}'\n")

        vf = (
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=white,"
            f"format=yuv420p"
        )

        cmd = [
            ffmpeg_exe,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-vf", vf,
            "-r", "30",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed:\n{result.stderr}")


def main() -> int:
    parser = argparse.ArgumentParser(description="スライド画像からリール用縦型動画を作成する")
    parser.add_argument("--images", nargs="+", required=True, help="スライド画像のパス(表示順)")
    parser.add_argument("--output", required=True, help="出力する動画ファイルパス(.mp4)")
    parser.add_argument("--seconds-per-slide", type=float, default=3.0, help="1枚あたりの表示秒数")
    args = parser.parse_args()

    for p in args.images:
        if not os.path.exists(p):
            print(f"画像が見つかりません: {p}", file=sys.stderr)
            return 1

    build_video(args.images, args.output, args.seconds_per_slide)
    print(f"動画を作成しました: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
