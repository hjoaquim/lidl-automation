# /// script
# requires-python = ">=3.12"
# dependencies = ["google-api-python-client", "google-auth"]
# ///
"""Push charts/*.png, each with its caption from charts/*.txt, into the Google Slides deck. Run: uv run slides.py

One blank slide per chart, inserted after the title slide: image on top, caption right below it.
Re-runnable: slides from a previous run (object IDs starting with PREFIX) are deleted first.
Auth: Application Default Credentials, see README.
"""

import struct
from pathlib import Path

import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

PRESENTATION_ID = "11yvCsDXdu4wxoAbgfQk4QJRvHkE_HWycWZelO1BYlh8"
CHARTS = Path("charts")
PREFIX = "auto_"
SCOPES = ["https://www.googleapis.com/auth/presentations", "https://www.googleapis.com/auth/drive.file"]

PT = 12700  # EMU per point
MARGIN, GAP, CAPTION_H, CAPTION_PT = 20 * PT, 6 * PT, 48 * PT, 11


def emu(v):
    return {"magnitude": v, "unit": "EMU"}


creds, _ = google.auth.default(scopes=SCOPES)
slides = build("slides", "v1", credentials=creds).presentations()
drive = build("drive", "v3", credentials=creds)

deck = slides.get(presentationId=PRESENTATION_ID, fields="pageSize,slides.objectId").execute()
page_w, page_h = deck["pageSize"]["width"]["magnitude"], deck["pageSize"]["height"]["magnitude"]

old = [s["objectId"] for s in deck["slides"] if s["objectId"].startswith(PREFIX)]
if old:
    slides.batchUpdate(
        presentationId=PRESENTATION_ID, body={"requests": [{"deleteObject": {"objectId": o}} for o in old]}
    ).execute()

pngs = sorted(CHARTS.glob("*.png"))
if not pngs:
    raise SystemExit(f"No charts in {CHARTS}/, run charts.py first")

# Slides only inserts images from a URL Google can fetch, so each PNG goes to Drive with a link-only
# share for the duration of the insert. Slides stores its own copy; the Drive files are deleted after.
uploaded = []
try:
    for png in pngs:
        file_id = drive.files().create(
            body={"name": f"{PREFIX}{png.name}"}, media_body=MediaFileUpload(png, mimetype="image/png"), fields="id"
        ).execute()["id"]
        uploaded.append(file_id)
        drive.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()

    requests = []
    for i, (png, file_id) in enumerate(zip(pngs, uploaded)):
        slide, image, caption = f"{PREFIX}slide_{i}", f"{PREFIX}image_{i}", f"{PREFIX}caption_{i}"
        px_w, px_h = struct.unpack(">II", png.read_bytes()[16:24])  # PNG IHDR width/height

        # Fit the image into the page minus margins and caption, then center image + caption vertically.
        scale = min((page_w - 2 * MARGIN) / px_w, (page_h - 2 * MARGIN - GAP - CAPTION_H) / px_h)
        w, h = px_w * scale, px_h * scale
        x, y = (page_w - w) / 2, (page_h - h - GAP - CAPTION_H) / 2

        requests += [
            {"createSlide": {"objectId": slide, "insertionIndex": 1 + i, "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
            {
                "createImage": {
                    "objectId": image,
                    "url": f"https://drive.google.com/uc?export=download&id={file_id}",
                    "elementProperties": {
                        "pageObjectId": slide,
                        "size": {"width": emu(w), "height": emu(h)},
                        "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "EMU"},
                    },
                }
            },
            {
                "createShape": {
                    "objectId": caption,
                    "shapeType": "TEXT_BOX",
                    "elementProperties": {
                        "pageObjectId": slide,
                        "size": {"width": emu(w), "height": emu(CAPTION_H)},
                        "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y + h + GAP, "unit": "EMU"},
                    },
                }
            },
            {"insertText": {"objectId": caption, "text": png.with_suffix(".txt").read_text().strip()}},
            {"updateTextStyle": {"objectId": caption, "style": {"fontSize": {"magnitude": CAPTION_PT, "unit": "PT"}}, "fields": "fontSize"}},
        ]
    slides.batchUpdate(presentationId=PRESENTATION_ID, body={"requests": requests}).execute()
finally:
    for file_id in uploaded:
        drive.files().delete(fileId=file_id).execute()

print(f"Inserted {len(pngs)} slides: https://docs.google.com/presentation/d/{PRESENTATION_ID}/edit")
