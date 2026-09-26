#!/usr/bin/env python3
"""
Instagram export -> Hugo travel posts.
Supports feed posts, carousels, videos, and reels.
Uses Google Gemini API for free structured-data fallback parsing.
"""
import base64
import hashlib
import io
import json
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PENDING_FILE = REPO_ROOT / "instagram-import" / "pending.txt"
MANIFEST_FILE = REPO_ROOT / "instagram-import-manifest.json"
QUARANTINE_DIR = REPO_ROOT / "instagram-import" / "quarantine"
CONTENT_TRAVEL = REPO_ROOT / "content" / "travel"
WORKDIR = Path("/tmp/instagram-import")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO_EXTS = {".mp4", ".mov"}


# ---------------------------------------------------------------- utilities

def fix_ig_mojibake(text: str) -> str:
    """Fixes Meta's Latin-1 / UTF-8 double-encoding bug."""
    if not text:
        return ""
    try:
        return text.encode("latin1").decode("utf8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def slugify(text: str, fallback: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or fallback


def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        return json.loads(MANIFEST_FILE.read_text())
    return {"processed": []}


def save_manifest(manifest: dict) -> None:
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def extract_drive_id(pending_text: str) -> str:
    pending_text = pending_text.strip()
    m = re.search(r"[-\w]{25,}", pending_text)
    if not m:
        raise SystemExit("Could not find a Google Drive file ID in instagram-import/pending.txt")
    return m.group(0)


# --------------------------------------------------------- Google Drive dl

def download_from_drive(file_id: str, dest: Path) -> None:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    key_b64 = os.environ.get("GDRIVE_SA_KEY_B64")
    if not key_b64:
        raise SystemExit("GDRIVE_SA_KEY_B64 secret is not set.")
    key_info = json.loads(base64.b64decode(key_b64))
    creds = service_account.Credentials.from_service_account_info(
        key_info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    service = build("drive", "v3", credentials=creds)
    request = service.files().get_media(fileId=file_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        downloader = MediaIoBaseDownload(f, request, chunksize=64 * 1024 * 1024)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"  downloaded {int(status.progress() * 100)}%")


# ------------------------------------------------------------- IG parsing

def extract_location(post: dict) -> str:
    """Finds location metadata wherever Meta stored it."""
    candidates = [
        post.get("location"),
        post.get("location_data"),
    ]
    if isinstance(post.get("media"), list) and post["media"]:
        candidates.append(post["media"][0].get("location"))

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return fix_ig_mojibake(candidate.strip())
        elif isinstance(candidate, dict):
            name = candidate.get("name") or candidate.get("address")
            if name:
                return fix_ig_mojibake(name.strip())
    return ""


def strict_parse_post(post: dict, export_root: Path) -> dict:
    """Extracts media, captions, timestamps, and location from feed posts and reels."""
    media_items = []

    # 1. Feed posts / carousels
    if "media" in post and isinstance(post["media"], list):
        media_items = post["media"]
    # 2. Reels format: { "title": "...", "creation_timestamp": ..., "uri": "..." }
    elif "uri" in post:
        media_items = [post]
    # 3. Alternative reels wrapper format: { "media": { "uri": ... } }
    elif "media" in post and isinstance(post["media"], dict):
        media_items = [post["media"]]

    if not media_items:
        raise ValueError("no media found in post")

    media_files = []
    for m in media_items:
        uri = m.get("uri")
        if not uri:
            continue
        src = export_root / uri
        if not src.exists():
            raise FileNotFoundError(f"media file missing from export: {uri}")

        caption_text = m.get("title") or m.get("caption") or ""
        media_files.append({
            "path": src,
            "timestamp": m.get("creation_timestamp"),
            "caption": fix_ig_mojibake(caption_text),
            "is_video": src.suffix.lower() in VIDEO_EXTS,
        })

    if not media_files:
        raise ValueError("no resolvable media in post")

    caption = (
        fix_ig_mojibake(post.get("title", ""))
        or fix_ig_mojibake(post.get("caption", ""))
        or media_files[0]["caption"]
    )

    timestamps = [m["timestamp"] for m in media_files if m.get("timestamp")]
    if not timestamps and post.get("creation_timestamp"):
        timestamps = [post["creation_timestamp"]]

    ts = min(timestamps) if timestamps else None
    if ts is None:
        raise ValueError("no timestamp found")

    return {
        "caption": caption,
        "timestamp": int(ts),
        "location": extract_location(post),
        "media_files": media_files,
    }


def ai_parse_post(post: dict) -> dict | None:
    """Free Gemini fallback for schema drift."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None

    prompt = (
        "Extract only what is present in this Instagram export object. "
        "Return ONLY a raw JSON object with keys: "
        '"caption" (string), "timestamp" (integer unix seconds or null), '
        '"location" (string), "media_uris" (list of string relative file paths).\n\n'
        f"Export object:\n{json.dumps(post)[:8000]}"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )
        data = json.loads(response.text)
        if not data.get("media_uris") or not data.get("timestamp"):
            return None
        return data
    except Exception as e:
        print(f"  Gemini fallback failed: {e}")
        return None


def resolve_ai_result(data: dict, export_root: Path) -> dict | None:
    media_files = []
    for uri in data["media_uris"]:
        src = export_root / uri
        if not src.exists():
            return None
        media_files.append({
            "path": src,
            "timestamp": data["timestamp"],
            "caption": "",
            "is_video": src.suffix.lower() in VIDEO_EXTS,
        })
    return {
        "caption": data.get("caption", ""),
        "timestamp": int(data["timestamp"]),
        "location": data.get("location", ""),
        "media_files": media_files,
    }


# ------------------------------------------------------------- Hugo output

def stable_post_id(post: dict) -> str:
    uris = []
    if "media" in post and isinstance(post["media"], list):
        uris = [m.get("uri", "") for m in post["media"]]
    elif "uri" in post:
        uris = [post.get("uri", "")]
    elif "media" in post and isinstance(post["media"], dict):
        uris = [post["media"].get("uri", "")]
    
    clean_uris = sorted(filter(None, uris))
    if not clean_uris:
        return ""
    return hashlib.sha256("|".join(clean_uris).encode()).hexdigest()[:16]

import subprocess
import json

TARGET_MAX_MB = 65  # Target comfortably under 100 MB
MAX_VIDEO_BYTES = 80 * 1024 * 1024

def get_video_duration(path: Path) -> float:
    """Returns video duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", str(path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0:
        data = json.loads(res.stdout)
        return float(data.get("format", {}).get("duration", 0))
    return 0.0

def compress_video(src: Path, dest: Path) -> None:
    """Compresses video to 720p with a hard ceiling on size."""
    duration = get_video_duration(src)
    
    # Calculate a safe bitrate ceiling if duration is known
    # Bitrate (bits/sec) = (Target Size in Bytes * 8) / duration
    if duration > 0:
        target_bits_total = TARGET_MAX_MB * 1024 * 1024 * 8
        target_bitrate = int(target_bits_total / duration)
        # Cap video bitrate; reserve ~128k for audio
        video_bitrate = max(target_bitrate - 128_000, 300_000)
        max_rate_str = f"{video_bitrate}"
        buf_size_str = f"{video_bitrate * 2}"
    else:
        max_rate_str = "2500k"
        buf_size_str = "5000k"

    print(f"    Compressing {src.name} (Duration: {duration:.1f}s, Cap: {max_rate_str})...")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vf", "scale=-2:720",
        "-vcodec", "libx264",
        "-crf", "26",
        "-maxrate", max_rate_str,
        "-bufsize", buf_size_str,
        "-preset", "fast",
        "-acodec", "aac",
        "-b:a", "128k",
        str(dest)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    # Emergency safety check: if still over 95 MB, re-encode with a lower CRF
    if dest.exists() and dest.stat().st_size > 95 * 1024 * 1024:
        print(f"    File still near limit ({dest.stat().st_size / (1024*1024):.1f} MB), applying aggressive compression...")
        emergency_cmd = [
            "ffmpeg", "-y",
            "-i", str(dest),
            "-vf", "scale=-2:480",
            "-vcodec", "libx264",
            "-crf", "30",
            "-preset", "faster",
            str(dest) + ".tmp.mp4"
        ]
        subprocess.run(emergency_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if Path(str(dest) + ".tmp.mp4").exists():
            shutil.move(str(dest) + ".tmp.mp4", dest)

def write_hugo_post(parsed: dict, post_id: str) -> None:
    dt = datetime.fromtimestamp(parsed["timestamp"], tz=timezone.utc)
    
    # Priority: Location -> Caption first line -> Date
    first_caption_line = parsed["caption"].split("\n")[0].strip() if parsed["caption"] else ""
    if parsed["location"]:
        title = parsed["location"]
        slug_seed = parsed["location"]
    elif first_caption_line:
        title = first_caption_line[:60]
        slug_seed = first_caption_line[:40]
    else:
        title = f"Post on {dt:%B %d, %Y}"
        slug_seed = f"post-{post_id[:8]}"

    slug = slugify(slug_seed, post_id[:8])
    bundle_dir = CONTENT_TRAVEL / f"{dt:%Y}" / f"{dt:%m}" / f"{dt:%d}" / slug
    
    n = 2
    base_dir = bundle_dir
    while bundle_dir.exists():
        bundle_dir = base_dir.parent / f"{base_dir.name}-{n}"
        n += 1
    bundle_dir.mkdir(parents=True)

    gallery_lines = []
    video_tags = []

    for i, m in enumerate(parsed["media_files"], start=1):
        ext = m["path"].suffix.lower()
        out_name = f"{i:02d}{ext}"
        dest_file = bundle_dir / out_name

        if m["is_video"]:
            # If the video exceeds 80MB, compress it using ffmpeg
            if m["path"].stat().st_size > MAX_VIDEO_BYTES:
                compress_video(m["path"], dest_file)
            else:
                shutil.copyfile(m["path"], dest_file)

            video_tags.append(
                f'<video controls preload="metadata" style="width:100%; border-radius:8px; margin: 12px 0;">'
                f'<source src="{out_name}" type="video/mp4">'
                f'Your browser does not support the video tag.'
                f'</video>'
            )
        else:
            shutil.copyfile(m["path"], dest_file)
            caption = m["caption"].replace("|", "-").strip()
            gallery_lines.append(f"{out_name} | {caption}" if caption else out_name)

    cover_name = f"01{parsed['media_files'][0]['path'].suffix.lower()}"

    frontmatter = (
        "---\n"
        f'title: "{title.replace(chr(34), chr(39))}"\n'
        f"date: {dt:%Y-%m-%d}\n"
        "draft: false\n"
        f'location: "{parsed["location"].replace(chr(34), chr(39))}"\n'
        "tags: []\n"
        f"instagram_import_id: {post_id}\n"
        "cover:\n"
        f'  image: "{cover_name}"\n'
        '  alt: "Post cover"\n'
        "  relative: true\n"
        "---\n\n"
    )

    body = ""
    if parsed["caption"]:
        body += f"{parsed['caption'].strip()}\n<!--more-->\n\n"
    else:
        body += "<!--more-->\n\n"

    if gallery_lines:
        body += "{{< gallery >}}\n"
        body += "\n".join(gallery_lines)
        body += "\n{{< /gallery >}}\n\n"

    if video_tags:
        body += "\n".join(video_tags) + "\n"

    (bundle_dir / "index.md").write_text(frontmatter + body)
    print(f"  wrote {bundle_dir.relative_to(REPO_ROOT)}")


def write_quarantine(post: dict, post_id: str, reason: str) -> None:
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    out = QUARANTINE_DIR / f"{post_id}.json"
    out.write_text(json.dumps({"reason": reason, "post": post}, indent=2, default=str))
    print(f"  quarantined {post_id}: {reason}")


# ------------------------------------------------------------------- main

def find_target_json_files(export_root: Path) -> list[Path]:
    """Finds all posts.json, posts_*.json, and reels.json files."""
    patterns = ["posts.json", "posts_*.json", "reels.json"]
    found = []
    for pattern in patterns:
        found.extend(export_root.rglob(pattern))
    return sorted(set(found))


def main() -> None:
    if not PENDING_FILE.exists() or not PENDING_FILE.read_text().strip():
        print("pending.txt is empty, nothing to do.")
        return

    file_id = extract_drive_id(PENDING_FILE.read_text())
    manifest = load_manifest()
    processed_ids = set(manifest["processed"])

    if WORKDIR.exists():
        shutil.rmtree(WORKDIR)
    WORKDIR.mkdir(parents=True)
    zip_path = WORKDIR / "export.zip"

    print(f"Downloading Drive file {file_id} ...")
    download_from_drive(file_id, zip_path)

    print("Extracting ...")
    export_root = WORKDIR / "extracted"
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(export_root)
    zip_path.unlink()

    json_files = find_target_json_files(export_root)
    if not json_files:
        raise SystemExit("No posts or reels JSON files found in export.")

    new_count = 0
    for jf in json_files:
        print(f"Reading {jf.name} ...")
        try:
            raw_content = json.loads(jf.read_text())
        except json.JSONDecodeError:
            raw_content = json.loads(jf.read_text(encoding="utf-8", errors="ignore"))

        if isinstance(raw_content, dict):
            # Reels files or wrapped items
            posts = (
                raw_content.get("items")
                or raw_content.get("ig_reels_media")
                or raw_content.get("media")
                or [raw_content]
            )
        else:
            posts = raw_content

        for post in posts:
            if not isinstance(post, dict):
                continue

            post_id = stable_post_id(post)
            if not post_id or post_id in processed_ids:
                continue

            parsed = None
            try:
                parsed = strict_parse_post(post, export_root)
            except Exception as e:
                print(f"  strict parse failed for {post_id} ({e}), trying Gemini fallback ...")
                ai_data = ai_parse_post(post)
                if ai_data:
                    parsed = resolve_ai_result(ai_data, export_root)

            if parsed is None:
                write_quarantine(post, post_id, "could not parse with strict or AI fallback")
                processed_ids.add(post_id)
                continue

            write_hugo_post(parsed, post_id)
            processed_ids.add(post_id)
            new_count += 1

    manifest["processed"] = sorted(processed_ids)
    save_manifest(manifest)
    PENDING_FILE.write_text("")
    shutil.rmtree(WORKDIR, ignore_errors=True)

    print(f"Done. {new_count} new item(s) written.")


if __name__ == "__main__":
    main()