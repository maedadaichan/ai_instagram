"""
台本JSON(content/*.json)から、動き・BGM・効果音つきのリール動画を生成するスクリプト。

Chromeなどのブラウザは不要で、Pillow + numpy + imageio-ffmpeg だけで動くため、
クラウドルーチンからも実行できる。BGMと効果音はこのスクリプト内で合成するので著作権の問題がない。

台本の形式は docs/content_playbook.md を参照。

使い方:
    python reel_builder.py content/week4_verdict.json
"""

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import wave

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1080
HEIGHT = 1920
FPS = 30
SAMPLE_RATE = 44100
BPM = 120
BEAT = 60 / BPM  # シーンの切り替えを拍に合わせるため、秒数はこの倍数に丸める

# Instagramの画面下部・右側のUIに隠れない範囲
TEXT_WIDTH = 900
TEXT_CENTER_X = 520
TEXT_CENTER_Y = 830

WHITE = (255, 255, 255)
GRAY = (154, 163, 171)
LIGHT = (214, 219, 224)
RED = (255, 64, 64)
GREEN = (46, 204, 113)
DARK = (17, 17, 17)

FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts", "NotoSansJP-VF.ttf")
FONT_CACHE = {}


def get_font(size: int, weight: int = 900) -> ImageFont.FreeTypeFont:
    key = (size, weight)
    if key not in FONT_CACHE:
        font = ImageFont.truetype(FONT_PATH, size)
        font.set_variation_by_axes([weight])
        FONT_CACHE[key] = font
    return FONT_CACHE[key]


def parse_runs(line: str, color: tuple) -> list:
    """「通常[赤字]通常」を [(文字列, 色), ...] に分解する"""
    runs = []
    rest = line
    while rest:
        start = rest.find("[")
        end = rest.find("]", start)
        if start == -1 or end == -1:
            runs.append((rest, color))
            break
        if start > 0:
            runs.append((rest[:start], color))
        runs.append((rest[start + 1:end], RED))
        rest = rest[end + 1:]
    return runs


def visible_text(text: str) -> str:
    return text.replace("[", "").replace("]", "")


def split_marked_lines(text: str) -> list:
    """改行をまたぐ[赤字]も、行ごとに閉じ直して色が切れないようにする"""
    lines = []
    is_red = False
    for raw in text.split("\n"):
        prefix = "[" if is_red else ""
        is_red = (raw.count("[") + (1 if is_red else 0)) > raw.count("]")
        lines.append(prefix + raw + ("]" if is_red else ""))
    return lines


def render_text(text: str, size: int, weight: int = 900, color: tuple = WHITE, line_height: float = 1.35) -> Image.Image:
    """複数行のテキストをRGBA画像にする。幅に収まらない時は文字を小さくする"""
    lines = split_marked_lines(text)
    longest = max(lines, key=lambda s: get_font(size, weight).getlength(visible_text(s)))
    longest_width = get_font(size, weight).getlength(visible_text(longest))
    if longest_width > TEXT_WIDTH:
        size = int(size * TEXT_WIDTH / longest_width)

    font = get_font(size, weight)
    step = int(size * line_height)
    image_w = TEXT_WIDTH + 40
    image_h = step * len(lines) + size // 2
    image = Image.new("RGBA", (image_w, image_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    y = 0
    for line in lines:
        x = (image_w - font.getlength(visible_text(line))) / 2
        for run_text, run_color in parse_runs(line, color):
            draw.text((x + 3, y + 4), run_text, font=font, fill=(0, 0, 0, 170))
            draw.text((x, y), run_text, font=font, fill=run_color + (255,))
            x += font.getlength(run_text)
        y += step
    return image


def render_pill(text: str, size: int, fill: tuple, text_color: tuple = WHITE, pad: tuple = (56, 26), weight: int = 900) -> Image.Image:
    """帯・判定スタンプ用の角丸ラベル"""
    lines = text.split("\n")
    font = get_font(size, weight)
    max_width = TEXT_WIDTH - pad[0] * 2
    longest_width = max(font.getlength(line) for line in lines)
    if longest_width > max_width:
        size = int(size * max_width / longest_width)
        font = get_font(size, weight)
        longest_width = max(font.getlength(line) for line in lines)
    step = int(size * 1.4)
    w = int(longest_width + pad[0] * 2)
    h = int(step * len(lines) + pad[1] * 2)
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=32, fill=fill + (255,))
    y = pad[1] - int(size * 0.08)
    for line in lines:
        x = (w - font.getlength(line)) / 2
        draw.text((x, y), line, font=font, fill=text_color + (255,))
        y += step
    return image


class Element:
    """シーン内の1パーツ。appear秒に飛び込むように表示される"""

    def __init__(self, image: Image.Image, y: int, appear: float = 0.0, slam: bool = False):
        self.image = image
        self.x = TEXT_CENTER_X - image.width // 2
        self.y = y
        self.appear = appear
        self.slam = slam

    def draw(self, canvas: Image.Image, t: float) -> None:
        elapsed = t - self.appear
        if elapsed < 0:
            return
        duration = 0.14
        if elapsed >= duration:
            canvas.alpha_composite(self.image, (self.x, self.y))
            return
        progress = 1 - (1 - elapsed / duration) ** 3
        start_scale = 1.7 if self.slam else 1.16
        scale = start_scale + (1 - start_scale) * progress
        w = max(1, int(self.image.width * scale))
        h = max(1, int(self.image.height * scale))
        scaled = self.image.resize((w, h), Image.BILINEAR)
        scaled.putalpha(scaled.getchannel("A").point(lambda a: int(a * min(1.0, 0.35 + progress))))
        px = self.x + (self.image.width - w) // 2
        py = self.y + (self.image.height - h) // 2
        paste_clipped(canvas, scaled, px, py)


def paste_clipped(canvas: Image.Image, image: Image.Image, x: int, y: int) -> None:
    """キャンバスからはみ出しても落ちないように合成する"""
    left, top = max(0, -x), max(0, -y)
    right = min(image.width, canvas.width - x)
    bottom = min(image.height, canvas.height - y)
    if right <= left or bottom <= top:
        return
    canvas.alpha_composite(image.crop((left, top, right, bottom)), (max(0, x), max(0, y)))


def stack(blocks: list, gap: int = 56) -> list:
    """[(画像, 出現秒, slam)] を縦中央に並べ、Elementのリストにする"""
    total = sum(b[0].height for b in blocks) + gap * (len(blocks) - 1)
    y = TEXT_CENTER_Y - total // 2
    elements = []
    for image, appear, slam in blocks:
        elements.append(Element(image, y, appear, slam))
        y += image.height + gap
    return elements


class Scene:
    """台本の1シーン。sound は音声合成に渡す (秒, 種類) のリスト"""

    def __init__(self, spec: dict):
        self.spec = spec
        self.kind = spec["type"]
        self.elements = []
        self.sounds = [(0.0, "whoosh")]
        self.shake_at = None
        self.chat = None
        self.duration = 2.0
        getattr(self, f"build_{self.kind}")(spec)
        sec = float(spec.get("sec", self.duration))
        self.duration = max(1, round(sec / BEAT)) * BEAT

    def build_hook(self, spec: dict) -> None:
        # 最初のフレームから全文を見せる(サムネイルにも使われるため、出現アニメーションを付けない)
        blocks = [(render_text(spec["text"], 118), -1.0, False)]
        if spec.get("sub"):
            blocks.append((render_text(spec["sub"], 50, 700, LIGHT), 0.5, False))
            self.sounds.append((0.5, "pop"))
        self.elements = stack(blocks)
        self.duration = 2.0

    def build_text(self, spec: dict) -> None:
        blocks = [(render_text(spec["text"], 84), 0.0, False)]
        if spec.get("sub"):
            blocks.append((render_text(spec["sub"], 52, 700, LIGHT), 0.5, False))
            self.sounds.append((0.5, "pop"))
        self.elements = stack(blocks)
        self.duration = 2.0

    def build_prompt(self, spec: dict) -> None:
        """白い箱に、実際に打つ一言を見せる"""
        blocks = [
            (render_text(spec["text"], 52, 700, LIGHT), 0.0, False),
            (render_pill(spec["prompt"], 64, WHITE, DARK), 0.4, True),
        ]
        self.sounds.append((0.4, "stamp"))
        self.elements = stack(blocks)
        self.duration = 2.5

    def build_verdict(self, spec: dict) -> None:
        """「アリ/ナシ」の判定。stampは0.6秒遅らせて、見る人に一瞬考えさせる"""
        good = spec.get("good", True)
        blocks = [
            (render_text(spec["label"], 84), 0.0, False),
            (render_pill(spec["stamp"], 120, GREEN if good else RED, pad=(72, 24)), 1.0, True),
        ]
        if spec.get("sub"):
            blocks.append((render_text(spec["sub"], 52, 700, LIGHT), 1.0, False))
        self.sounds.append((1.0, "stamp"))
        self.shake_at = 1.0
        self.elements = stack(blocks)
        self.duration = 3.0

    def build_ab(self, spec: dict) -> None:
        """AとBの二択。見る人に選ばせる"""
        blocks = [
            (render_text(spec["text"], 72), 0.0, False),
            (render_pill("A  " + spec["a"], 58, (58, 66, 74)), 0.5, True),
            (render_pill("B  " + spec["b"], 58, (58, 66, 74)), 1.0, True),
        ]
        if spec.get("sub"):
            blocks.append((render_text(spec["sub"], 52, 700, LIGHT), 1.5, False))
        self.sounds += [(0.5, "pop"), (1.0, "pop")]
        self.elements = stack(blocks, gap=44)
        self.duration = 3.0

    def build_chat(self, spec: dict) -> None:
        """AIチャット画面のイメージ。一言を打つと回答が順に出る"""
        user = spec["user"]
        ai_lines = spec["ai"]
        type_sec = len(user) / 12
        reply_at = type_sec + 0.5
        self.chat = ChatPanel(user, ai_lines, type_sec, reply_at)
        self.sounds += [(i / 12, "tick") for i in range(0, len(user), 2)]
        self.sounds += [(reply_at + i * 0.35, "pop") for i in range(len(ai_lines))]
        self.duration = reply_at + len(ai_lines) * 0.35 + 1.0

    def draw(self, canvas: Image.Image, t: float) -> None:
        if self.chat:
            self.chat.draw(canvas, t)
        for element in self.elements:
            element.draw(canvas, t)


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    lines = []
    current = ""
    for ch in text:
        if ch == "\n" or font.getlength(current + ch) > max_width:
            lines.append(current)
            current = "" if ch == "\n" else ch
        else:
            current += ch
    if current:
        lines.append(current)
    return lines


class ChatPanel:
    """特定のサービスに見えない、汎用のチャット画面"""

    LEFT, TOP, RIGHT, BOTTOM = 70, 340, 970, 1200

    def __init__(self, user: str, ai_lines: list, type_sec: float, reply_at: float):
        self.user = user
        self.ai_lines = ai_lines
        self.type_sec = type_sec
        self.reply_at = reply_at
        self.user_font = get_font(54, 700)
        self.ai_font = get_font(52, 700)
        self.panel = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(self.panel)
        draw.rounded_rectangle((self.LEFT, self.TOP, self.RIGHT, self.BOTTOM), radius=40, fill=(32, 36, 41, 255), outline=(70, 78, 86, 255), width=3)
        draw.text((self.LEFT + 48, self.TOP + 34), "AIチャット", font=get_font(36, 700), fill=GRAY + (255,))

    def draw(self, canvas: Image.Image, t: float) -> None:
        canvas.alpha_composite(self.panel)
        draw = ImageDraw.Draw(canvas)
        inner_left = self.LEFT + 44
        inner_right = self.RIGHT - 44

        typed = self.user[: int(min(1.0, t / max(self.type_sec, 0.01)) * len(self.user))]
        lines = wrap_text(typed or " ", self.user_font, inner_right - inner_left - 90)
        full_lines = wrap_text(self.user, self.user_font, inner_right - inner_left - 90)
        bubble_h = len(full_lines) * 76 + 44
        bubble_top = self.TOP + 110
        bubble_w = max(self.user_font.getlength(line) for line in full_lines) + 72
        draw.rounded_rectangle((inner_right - bubble_w, bubble_top, inner_right, bubble_top + bubble_h), radius=30, fill=(255, 64, 64, 255))
        y = bubble_top + 16
        for line in lines:
            draw.text((inner_right - bubble_w + 36, y), line, font=self.user_font, fill=WHITE + (255,))
            y += 76

        y = bubble_top + bubble_h + 60
        if t < self.reply_at:
            if t > self.type_sec:
                dots = "・" * (1 + int(t * 6) % 3)
                draw.text((inner_left, y), dots, font=self.ai_font, fill=GRAY + (255,))
            return
        shown = int((t - self.reply_at) / 0.35) + 1
        for line in self.ai_lines[:shown]:
            for wrapped in wrap_text(line, self.ai_font, inner_right - inner_left):
                draw.text((inner_left, y), wrapped, font=self.ai_font, fill=WHITE + (255,))
                y += 74
            y += 26


def make_background() -> Image.Image:
    """暗い放射グラデーション。少し大きめに作り、動かして使う"""
    w, h = WIDTH + 200, HEIGHT + 200
    ys, xs = np.mgrid[0:h, 0:w]
    distance = np.sqrt(((xs - w / 2) / w) ** 2 + ((ys - h * 0.4) / h) ** 2)
    glow = np.clip(1 - distance * 1.7, 0, 1)[..., None]
    pixels = np.array([13, 15, 17]) + glow * np.array([26, 29, 32])
    return Image.fromarray(pixels.astype(np.uint8), "RGB")


def render_video(scenes: list, series: str, raw_out) -> None:
    background = make_background()
    series_image = render_text(series, 34, 700, GRAY)
    handle_image = render_text("@ai__daisuke", 34, 700, GRAY)
    total = sum(s.duration for s in scenes)
    elapsed = 0.0
    frame_no = 0
    for scene in scenes:
        for i in range(int(round(scene.duration * FPS))):
            t = i / FPS
            global_t = elapsed + t
            ox = int(100 + 70 * math.sin(global_t * 0.9))
            oy = int(100 + 70 * math.cos(global_t * 0.7))
            canvas = background.crop((ox, oy, ox + WIDTH, oy + HEIGHT)).convert("RGBA")
            scene.draw(canvas, t)

            # 切り替わり後もゆっくり寄り続けて、静止画に見えないようにする
            zoom = 1 + 0.035 * (t / scene.duration)
            if zoom > 1.001:
                w, h = int(WIDTH / zoom), int(HEIGHT / zoom)
                left, top = (WIDTH - w) // 2, (HEIGHT - h) // 2
                canvas = canvas.resize((WIDTH, HEIGHT), Image.BILINEAR, box=(left, top, left + w, top + h))
            if scene.shake_at is not None and 0 <= t - scene.shake_at < 0.2:
                amount = int(16 * (1 - (t - scene.shake_at) / 0.2))
                dx = amount if frame_no % 2 else -amount
                canvas = Image.fromarray(np.roll(np.array(canvas), dx, axis=1), "RGBA")

            canvas.alpha_composite(series_image, (TEXT_CENTER_X - series_image.width // 2, 200))
            canvas.alpha_composite(handle_image, (TEXT_CENTER_X - handle_image.width // 2, 1420))
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((70, 270, 970, 277), fill=(58, 66, 74, 255))
            draw.rectangle((70, 270, 70 + int(900 * global_t / total), 277), fill=RED + (255,))
            raw_out.write(canvas.convert("RGB").tobytes())
            frame_no += 1
        elapsed += scene.duration


def envelope(length: int, decay: float) -> np.ndarray:
    return np.exp(-np.arange(length) / SAMPLE_RATE * decay)


def add(track: np.ndarray, start_sec: float, sound: np.ndarray, gain: float) -> None:
    start = int(start_sec * SAMPLE_RATE)
    if start >= len(track):
        return
    end = min(len(track), start + len(sound))
    track[start:end] += sound[: end - start] * gain


def tone(freq: float, sec: float, decay: float, rich: bool = True) -> np.ndarray:
    n = int(sec * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    wave_data = np.sin(2 * np.pi * freq * t)
    if rich:
        wave_data += 0.4 * np.sin(4 * np.pi * freq * t) + 0.2 * np.sin(6 * np.pi * freq * t)
    return wave_data * envelope(n, decay)


def make_sfx(rng: np.random.Generator) -> dict:
    n = int(0.18 * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    sweep = np.sin(2 * np.pi * (500 * t + 2500 * t * t))
    whoosh_noise = rng.normal(0, 1, int(0.22 * SAMPLE_RATE))
    fade = np.sin(np.linspace(0, np.pi, len(whoosh_noise))) ** 2
    thud_n = int(0.3 * SAMPLE_RATE)
    thud_t = np.arange(thud_n) / SAMPLE_RATE
    return {
        "pop": sweep * envelope(n, 28) * 0.5,
        "tick": rng.normal(0, 1, int(0.02 * SAMPLE_RATE)) * envelope(int(0.02 * SAMPLE_RATE), 300) * 0.25,
        "whoosh": np.convolve(whoosh_noise, np.ones(30) / 30, mode="same") * fade * 2.2,
        "stamp": np.sin(2 * np.pi * (150 * thud_t - 170 * thud_t * thud_t)) * envelope(thud_n, 13) * 1.1,
    }


def make_audio(scenes: list, seed_text: str) -> np.ndarray:
    """拍に合わせたBGMと効果音を合成する。投稿ごとに調とメロディを少し変える"""
    seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    total = sum(s.duration for s in scenes)
    music = np.zeros(int((total + 0.1) * SAMPLE_RATE))
    root = 110.0 * 2 ** (rng.integers(-2, 4) / 12)
    # 明るすぎず集中できる進行。各コードは半音の数で表す
    progressions = [[0, 8, 3, 10], [0, 5, 8, 7], [0, 3, 8, 10]]
    progression = progressions[int(rng.integers(0, len(progressions)))]
    minor = [0, 3, 7, 12, 15]
    melody = rng.choice(minor, size=32)

    kick_n = int(0.25 * SAMPLE_RATE)
    kick_t = np.arange(kick_n) / SAMPLE_RATE
    kick = np.sin(2 * np.pi * (120 * kick_t - 100 * kick_t * kick_t)) * envelope(kick_n, 16)
    hat = rng.normal(0, 1, int(0.05 * SAMPLE_RATE)) * envelope(int(0.05 * SAMPLE_RATE), 110)
    clap = rng.normal(0, 1, int(0.12 * SAMPLE_RATE)) * envelope(int(0.12 * SAMPLE_RATE), 34)

    eighth = BEAT / 2
    steps = int(total / eighth) + 1
    for step in range(steps):
        at = step * eighth
        chord = progression[(step // 8) % len(progression)]
        chord_root = root * 2 ** (chord / 12)
        if step % 2 == 0:
            add(music, at, kick, 0.75)
        if step % 4 == 2:
            add(music, at, clap, 0.16)
        add(music, at, hat, 0.09 if step % 2 else 0.05)
        if step % 2 == 0 or step % 8 == 3:
            add(music, at, tone(chord_root / 2, 0.42, 6), 0.3)
        note = chord_root * 2 * 2 ** (int(melody[step % len(melody)]) / 12)
        if step % 8 in (0, 3, 6):
            add(music, at, tone(note, 0.32, 9), 0.11)

    sfx = np.zeros_like(music)
    effects = make_sfx(rng)
    elapsed = 0.0
    for scene in scenes:
        for at, name in scene.sounds:
            add(sfx, elapsed + at, effects[name], 0.5)
        elapsed += scene.duration

    mix = music + sfx
    fade_len = int(0.3 * SAMPLE_RATE)
    mix[-fade_len:] *= np.linspace(1, 0, fade_len)
    return mix / max(np.max(np.abs(mix)), 1e-6) * 0.8


def write_wav(path: str, samples: np.ndarray) -> None:
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm.tobytes())


def build(spec_path: str) -> str:
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    scenes = [Scene(s) for s in spec["scenes"]]
    total = sum(s.duration for s in scenes)
    root_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(root_dir, spec["output"])
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmp_dir:
        wav_path = os.path.join(tmp_dir, "audio.wav")
        write_wav(wav_path, make_audio(scenes, os.path.basename(spec_path)))
        cmd = [
            ffmpeg_exe,
            "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{WIDTH}x{HEIGHT}",
            "-r", str(FPS),
            "-i", "pipe:0",
            "-i", wav_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "21",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        render_video(scenes, spec["series"], process.stdin)
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("ffmpegが失敗しました")

    print(f"動画を作成しました: {spec['output']} ({total:.1f}秒)")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="台本JSONからリール動画を生成する")
    parser.add_argument("specs", nargs="+", help="台本JSONのパス")
    args = parser.parse_args()
    for spec_path in args.specs:
        if not os.path.exists(spec_path):
            print(f"台本が見つかりません: {spec_path}", file=sys.stderr)
            return 1
        build(spec_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
