from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "test-results" / "real-benchmark"
PNG_DIR = RESULTS / "png"
DATA = json.loads((RESULTS / "benchmark-results.json").read_text(encoding="utf-8"))

WIDTH, HEIGHT = 1600, 900
BG = "#0b1020"
PANEL = "#151c2f"
TEXT = "#f4f7ff"
MUTED = "#aab5cc"
GRID = "#29334b"
GREEN = "#38d39f"
BLUE = "#5aa7ff"
ORANGE = "#ffb454"
RED = "#ff6b7a"
PURPLE = "#a98bff"


def font(size: int, bold: bool = False):
    name = "seguisb.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def canvas(title: str, subtitle: str):
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.text((75, 55), title, fill=TEXT, font=font(42, True))
    draw.text((77, 112), subtitle, fill=MUTED, font=font(22))
    return image, draw


def panel(draw, box):
    draw.rounded_rectangle(box, radius=24, fill=PANEL)


def bar(draw, x, y, width, height, ratio, color, label, value):
    draw.text((x, y - 38), label, fill=TEXT, font=font(22))
    draw.rounded_rectangle((x, y, x + width, y + height), radius=height // 2, fill=GRID)
    fill_width = max(0, int(width * ratio))
    if fill_width:
        draw.rounded_rectangle((x, y, x + fill_width, y + height), radius=height // 2, fill=color)
    value_width = draw.textbbox((0, 0), value, font=font(22, True))[2]
    draw.text((x + width - value_width, y - 38), value, fill=TEXT, font=font(22, True))


def save(image, name):
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    image.save(PNG_DIR / name, quality=95)


def overview():
    image, draw = canvas("Otomasyon Test Özeti", "Gerçek saha koşusu + tam regresyon paketi")
    cards = [
        ("209", "Toplam test", BLUE),
        ("206", "Başarılı", GREEN),
        ("3", "Atlanan", ORANGE),
        ("0", "Manuel kontrol", PURPLE),
    ]
    for index, (value, label, color) in enumerate(cards):
        x = 75 + index * 375
        panel(draw, (x, 180, x + 330, 385))
        draw.text((x + 30, 215), value, fill=color, font=font(62, True))
        draw.text((x + 32, 305), label, fill=MUTED, font=font(24))
    panel(draw, (75, 440, 1525, 820))
    draw.text((115, 480), "Saha modu başarı oranları", fill=TEXT, font=font(28, True))
    modes = DATA["modes"]
    items = [
        ("URL Bulma", modes["url_discovery"]["completion_rate"], GREEN),
        ("Program v1", modes["program_v1"]["completion_rate"], RED),
        ("Program v2 — yeni alanlar", modes["program_v2"]["completion_rate"], BLUE),
        ("Birleşik akış", modes["combined"]["completion_rate"], ORANGE),
    ]
    for index, (label, ratio, color) in enumerate(items):
        bar(draw, 115, 565 + index * 70, 1260, 25, ratio, color, label, f"%{ratio * 100:.1f}")
    save(image, "01-test-ozeti.png")


def mode_outcomes():
    image, draw = canvas("Mod Bazında Test Kararları", "Kabul, manuel kontrol ve red dağılımı")
    panels = [
        ("URL Bulma", 4, 0, 0),
        ("Program v1", 0, 0, 4),
        ("Program v2 adayları", 5, 0, 13),
        ("Birleşik aşamalar", 4, 0, 1),
    ]
    for index, (name, accepted, manual, rejected) in enumerate(panels):
        y = 175 + index * 165
        panel(draw, (75, y, 1525, y + 135))
        draw.text((110, y + 25), name, fill=TEXT, font=font(27, True))
        total = max(accepted + manual + rejected, 1)
        x, width, h = 540, 820, 34
        current = x
        for count, color in ((accepted, GREEN), (manual, PURPLE), (rejected, RED)):
            segment = int(width * count / total)
            if segment:
                draw.rectangle((current, y + 38, current + segment, y + 38 + h), fill=color)
            current += segment
        draw.text((1390, y + 32), str(total), fill=TEXT, font=font(27, True))
        draw.text((110, y + 82), f"Kabul {accepted}   ·   Manuel {manual}   ·   Red {rejected}", fill=MUTED, font=font(21))
    draw.text((75, 850), "Yeşil: kabul   Mor: manuel   Kırmızı: red/tamamlanmayan", fill=MUTED, font=font(19))
    save(image, "02-mod-kararlari.png")


def manual_control():
    image, draw = canvas("Manuel Kontrol ve Güven Kararları", "Bu gerçek örneklemde manuel kuyruğa düşen kayıt bulunmadı")
    panel(draw, (75, 175, 1525, 790))
    draw.text((120, 220), "100 alan kararı", fill=TEXT, font=font(32, True))
    draw.text((120, 275), "Arkansas Baptist College · Program v2", fill=MUTED, font=font(22))
    values = [("Kanıtlı / yazılabilir", 68, GREEN), ("Manuel kontrol", 0, PURPLE), ("Düşük güvenle boş bırakıldı", 32, ORANGE)]
    for index, (label, count, color) in enumerate(values):
        y = 385 + index * 120
        bar(draw, 120, y, 1240, 38, count / 100, color, label, f"{count} alan")
    draw.text((120, 735), "Katı eşikler korunuyor: düşük güvenli değerler otomatik yazılmadı.", fill=MUTED, font=font(22))
    save(image, "03-manuel-kontrol.png")


def fill_improvement():
    image, draw = canvas("Doluluk İyileştirmesi", "Katı doğrulama kuralları değiştirilmeden v2 sonucu")
    panel(draw, (75, 175, 1525, 790))
    before = DATA["modes"]["program_v2"]["workbook_fill_before"]
    after = DATA["modes"]["program_v2"]["workbook_fill_after"]
    bar(draw, 120, 310, 1240, 48, before["rate"], PURPLE, "Önce", f"%{before['rate'] * 100:.2f} · {before['filled']} hücre")
    bar(draw, 120, 460, 1240, 48, after["rate"], GREEN, "Sonra", f"%{after['rate'] * 100:.2f} · {after['filled']} hücre")
    draw.text((120, 600), "+6 yeni hücre", fill=GREEN, font=font(48, True))
    draw.text((120, 670), "48 uygun alan boş kaldı · 294 mevcut hücre korundu", fill=MUTED, font=font(24))
    save(image, "04-doluluk-artisi.png")


if __name__ == "__main__":
    overview()
    mode_outcomes()
    manual_control()
    fill_improvement()
    print(PNG_DIR)
