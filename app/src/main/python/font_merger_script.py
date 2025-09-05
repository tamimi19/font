# -*- coding: utf-8 -*-
import os
import sys
import traceback
import shutil
import tempfile
from fontTools.ttLib import TTFont
try:
    from fontTools.varLib.instancer import instantiateVariableFont
except Exception:
    try:
        from fontTools.varLib.mutator import instantiateVariableFont
    except Exception:
        instantiateVariableFont = None

from fontTools.merge import Merger
from fontTools.subset import main as subset_main
from PIL import Image, ImageDraw, ImageFont, features
import arabic_reshaper
from bidi.algorithm import get_display

# For Chaquopy, FONT_DIR should be handled by Android code
# and passed as an argument.
FONT_DIR = "/sdcard/fonts"
TEMP_DIR = "/sdcard/fonts/temp_processing"
EN_PREVIEW = "The quick brown fox jumps over the lazy dog. 1234567890"
AR_PREVIEW = "سمَات مجّانِية، إختر منْ بين أكثر من ١٠٠ سمة مجانية او انشئ سماتك الخاصة هُنا في هذا التطبيق النظيف الرائع، وأظهر الابداع.١٢٣٤٥٦٧٨٩٠"

# ---------- Logging and Status ----------
logs = []
def log(msg):
    logs.append(str(msg))

# ---------- Utilities ----------
def copy_to_temp(src_path, temp_dir):
    """نسخ الملف إلى المجلد المؤقت"""
    filename = os.path.basename(src_path)
    dst_path = os.path.join(temp_dir, filename)
    shutil.copy2(src_path, dst_path)
    return dst_path

def convert_otf_to_ttf(path, temp_files):
    base, ext = os.path.splitext(path)
    try:
        font = TTFont(path)
    except Exception as ex:
        log(f"خطأ فتح الخط {path}: {ex}")
        raise RuntimeError(f"Cannot open font {path}: {ex}")
    needs_conv = False
    if ext.lower() == ".otf":
        needs_conv = True
    if "CFF " in font.keys() or "CFF2" in font.keys():
        needs_conv = True
    if not needs_conv:
        return path
    out = base + "_to_ttf.ttf"
    try:
        font.flavor = None
        font.save(out)
        temp_files.append(out)
        log(f"fontTools: Saved {os.path.basename(path)} as TTF")
        return out
    except Exception as ex:
        log(f"فشل تحويل عن طريق fontTools: {ex}")
        raise RuntimeError(f"Failed to convert {path} to TTF: {ex}")

# ---------- UnitsPerEm unification ----------
def try_unify_units(paths):
    fonts = []
    for p in paths:
        fonts.append(TTFont(p))
    units = [f['head'].unitsPerEm for f in fonts]
    target = max(units)
    for idx, f in enumerate(fonts):
        old = f['head'].unitsPerEm
        if old == target:
            continue
        scale = float(target) / float(old)
        log(f"fontTools: Unified unitsPerEm from {old} to {target}")
        try:
            if 'glyf' in f.keys():
                glyf = f['glyf']
                for gname in glyf.keys():
                    glyph = glyf[gname]
                    try:
                        if glyph.isComposite():
                            glyph.transform((scale, 0, 0, scale, 0, 0))
                            continue
                    except Exception:
                        pass
                    try:
                        coords, endPts, flags = glyph.getCoordinates(glyf)
                        for i in range(len(coords)):
                            x, y = coords[i]
                            coords[i] = (int(round(x * scale)), int(round(y * scale)))
                        try:
                            glyph.recalcBounds(glyf)
                        except Exception:
                            pass
                    except Exception:
                        pass
            try:
                hmtx = f['hmtx'].metrics
                for gname, (adv, lsb) in list(hmtx.items()):
                    hmtx[gname] = (int(round(adv * scale)), int(round(lsb * scale)))
            except Exception:
                pass
            if 'OS/2' in f.keys():
                try:
                    os2 = f['OS/2']
                    if hasattr(os2, 'usWinAscent'):
                        os2.usWinAscent = int(round(os2.usWinAscent * scale))
                        os2.usWinDescent = int(round(os2.usWinDescent * scale))
                except Exception:
                    pass
            if 'hhea' in f.keys():
                try:
                    f['hhea'].ascent = int(round(getattr(f['hhea'], 'ascent', 0) * scale))
                    f['hhea'].descent = int(round(getattr(f['hhea'], 'descent', 0) * scale))
                except Exception:
                    pass
            f['head'].unitsPerEm = int(target)
        except Exception as ex:
            log(f"[WARN] Scaling outlines failed: {ex}. Trying metrics-only.")
            try:
                hmtx = f['hmtx'].metrics
                for gname, (adv, lsb) in list(hmtx.items()):
                    hmtx[gname] = (int(round(adv * scale)), int(round(lsb * scale)))
                if 'OS/2' in f.keys():
                    os2 = f['OS/2']
                    if hasattr(os2, 'usWinAscent'):
                        os2.usWinAscent = int(round(os2.usWinAscent * scale))
                        os2.usWinDescent = int(round(os2.usWinDescent * scale))
                if 'hhea' in f.keys():
                    f['hhea'].ascent = int(round(getattr(f['hhea'], 'ascent', 0) * scale))
                    f['hhea'].descent = int(round(getattr(f['hhea'], 'descent', 0) * scale))
                f['head'].unitsPerEm = int(target)
            except Exception as ex2:
                log(f"[WARN] Metric-only scaling failed: {ex2}")
        try:
            f.save(paths[idx])
        except Exception as ex:
            log(f"[WARN] Saving scaled font failed: {ex}")
    return paths

# ---------- Subsetting ----------
def subset_keep(path, unicodes, temp_files):
    base, _ = os.path.splitext(path)
    out = base + "_sub.ttf"
    saved_argv = sys.argv[:]
    try:
        sys.argv = ["pyftsubset", path, f"--unicodes={unicodes}", f"--output-file={out}", "--no-hinting"]
        subset_main()
    except SystemExit:
        pass
    except Exception as ex:
        log(f"[WARN] Subset failed for {os.path.basename(path)}: {ex}")
        sys.argv = saved_argv
        return path
    finally:
        sys.argv = saved_argv
    if os.path.exists(out):
        temp_files.append(out)
        log(f"pyftsubset: Subset font")
        return out
    return path

def clean_languages(ar_path, en_path, temp_files):
    arabic_ranges = ",".join([
        "U+0600-06FF", "U+0750-077F", "U+08A0-08FF",
        "U+FB50-FDFF", "U+FE70-FEFF", "U+0660-0669"
    ])
    ascii_range = "U+0020-007F"
    ar_out = subset_keep(ar_path, arabic_ranges, temp_files)
    en_out = subset_keep(en_path, ascii_range, temp_files)
    return ar_out, en_out

# ---------- Unique output name ----------
def unique_name(path):
    base, ext = os.path.splitext(path)
    cand = path
    i = 1
    while os.path.exists(cand):
        cand = f"{base}_{i}{ext}"
        i += 1
    return cand

# ---------- Merge with fontTools ----------
def merge_fonts_with_fonttools(paths, out):
    try:
        merger = Merger()
        merged = merger.merge(paths)
        merged.save(out)
        log(f"fontTools.merge: Merged fonts")
        return out
    except Exception as ex:
        log(f"[ERROR] fontTools.merge failed: {ex}")
        raise RuntimeError(f"Merge failed: {ex}")

# ---------- Text wrapping helper ----------
def wrap_text_to_lines(text, font, max_width, is_ar=False, draw=None):
    """
    Wrap text into lines that fit max_width.
    For Arabic, use original text and measure with direction='rtl'.
    """
    if draw is None:
        draw = ImageDraw.Draw(Image.new("RGB", (10,10)))
    words = text.split(" ")
    lines = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip() if cur else w
        if is_ar:
            bbox = draw.textbbox((0,0), trial, font=font, direction="rtl", language="ar")
        else:
            bbox = draw.textbbox((0,0), trial, font=font)
        w_px = bbox[2] - bbox[0]
        if w_px <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            if is_ar:
                single_bbox = draw.textbbox((0,0), w, font=font, direction="rtl", language="ar")
            else:
                single_bbox = draw.textbbox((0,0), w, font=font)
            if single_bbox[2] - single_bbox[0] > max_width:
                part = ""
                for ch in w:
                    trial2 = part + ch
                    if is_ar:
                        bbox2 = draw.textbbox((0,0), trial2, font=font, direction="rtl", language="ar")
                    else:
                        bbox2 = draw.textbbox((0,0), trial2, font=font)
                    if bbox2[2] - bbox2[0] <= max_width:
                        part = trial2
                    else:
                        if part:
                            lines.append(part)
                        part = ch
                if part:
                    cur = part
                else:
                    cur = ""
            else:
                cur = w
    if cur:
        lines.append(cur)
    return lines

# ---------- Preview creation (high resolution) ----------
def create_preview(merged_ttf, out_jpg, bg_color="white", text_color="black"):
    W, H = 6400, 2880
    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    try:
        has_raqm = features.check_feature("raqm")
        log(f"Pillow has Raqm support: {has_raqm}")
        base_size = 330
        try:
            font_en = ImageFont.truetype(merged_ttf, base_size)
            font_ar = ImageFont.truetype(merged_ttf, base_size)
        except Exception:
            font_en = ImageFont.load_default()
            font_ar = ImageFont.load_default()

        max_w = int(W * 0.9)
        size = base_size
        while True:
            try:
                font_en = ImageFont.truetype(merged_ttf, size)
            except Exception:
                font_en = ImageFont.load_default()
            bbox = draw.textbbox((0,0), EN_PREVIEW, font=font_en)
            w = bbox[2] - bbox[0]
            if w >= W * 0.85 or size >= 1500:
                break
            size += 75
        size = int(size * 0.9)

        try:
            font_en = ImageFont.truetype(merged_ttf, size)
            font_ar = ImageFont.truetype(merged_ttf, size)
        except Exception:
            font_en = ImageFont.load_default()
            font_ar = ImageFont.load_default()

        en_lines = wrap_text_to_lines(EN_PREVIEW, font_en, max_w, is_ar=False, draw=draw)
        if has_raqm:
            ar_text = AR_PREVIEW
            use_rtl = True
        else:
            reshaped_ar = arabic_reshaper.reshape(AR_PREVIEW)
            ar_text = get_display(reshaped_ar)
            use_rtl = False

        ar_lines = wrap_text_to_lines(ar_text, font_ar, max_w, is_ar=use_rtl, draw=draw)
        spacing = int(size * 0.2)
        en_total_h = 0
        for ln in en_lines:
            bbox = draw.textbbox((0,0), ln, font=font_en)
            en_total_h += (bbox[3] - bbox[1]) + spacing
        en_total_h -= spacing
        ar_total_h = 0
        for ln in ar_lines:
            if use_rtl:
                bbox = draw.textbbox((0,0), ln, font=font_ar, direction="rtl", language="ar")
            else:
                bbox = draw.textbbox((0,0), ln, font=font_ar)
            ar_total_h += (bbox[3] - bbox[1]) + spacing
        ar_total_h -= spacing

        start_en_y = max(20, (H//2 - en_total_h) // 2)
        y = start_en_y
        for ln in en_lines:
            bbox = draw.textbbox((0,0), ln, font=font_en)
            w = bbox[2] - bbox[0]
            x = (W - w) / 2
            draw.text((x, y), ln, font=font_en, fill=text_color)
            y += (bbox[3] - bbox[1]) + spacing

        start_ar_y = H//2 + max(20, (H//2 - ar_total_h) // 2)
        start_ar_y -= 100
        y = start_ar_y
        for ln in ar_lines:
            if use_rtl:
                bbox = draw.textbbox((0,0), ln, font=font_ar, direction="rtl", language="ar")
                w = bbox[2] - bbox[0]
                x = (W - w) / 2
                draw.text((x, y), ln, font=font_ar, fill=text_color, direction="rtl", language="ar")
            else:
                bbox = draw.textbbox((0,0), ln, font=font_ar)
                w = bbox[2] - bbox[0]
                x = (W - w) / 2
                draw.text((x, y), ln, font=font_ar, fill=text_color)
            y += (bbox[3] - bbox[1]) + spacing

        img.save(out_jpg, "JPEG", quality=95, dpi=(600, 600))
        log(f"Pillow: Created high-quality preview")
        return True
    except Exception as ex:
        log(f"[WARN] Preview creation failed: {ex}")
        try:
            f_default = ImageFont.load_default()
            draw.text((100, 500), EN_PREVIEW, font=f_default, fill=text_color)
            try:
                draw.text((100, H//2 + 500), AR_PREVIEW, font=f_default, fill=text_color, direction="rtl", language="ar")
            except:
                reshaped_ar = arabic_reshaper.reshape(AR_PREVIEW)
                bidi_ar = get_display(reshaped_ar)
                draw.text((100, H//2 + 500), bidi_ar, font=f_default, fill=text_color)

            img.save(out_jpg, "JPEG", quality=95)
            log(f"Pillow: Created fallback preview")
            return False
        except Exception as ex2:
            log(f"[WARN] Fallback preview creation failed: {ex2}")
            return False

# Main function to be called from Android
def merge_fonts_android(arabic_font, english_font):
    """
    دمج الخطوط مع معاينة عالية الجودة
    Font merger with high-quality preview
    """
    try:
        global logs
        logs = []
        log("=== بدء دمج الخطوط ===")
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs(os.path.join(FONT_DIR, "previews"), exist_ok=True)
        os.makedirs(os.path.join(FONT_DIR, "merged"), exist_ok=True)
        os.makedirs(os.path.join(FONT_DIR, "logs"), exist_ok=True)
        
        LOG_FILE = os.path.join(FONT_DIR, "logs", "merge_log.txt")
        try:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write(f"Log started: {time.strftime('%Y-%m-%d %I:%M:%S %p')}\n")
        except:
            pass

        processing_dir = tempfile.mkdtemp(dir=TEMP_DIR)
        
        if not os.path.isdir(FONT_DIR):
            log(f"[ERROR] مجلد الخطوط غير موجود: {FONT_DIR}")
            return "\n".join(logs)

        a_path = os.path.join(FONT_DIR, arabic_font)
        e_path = os.path.join(FONT_DIR, english_font)

        if not os.path.exists(a_path):
            log(f"[ERROR] الخط العربي غير موجود: {a_path}")
            return "\n".join(logs)
        if not os.path.exists(e_path):
            log(f"[ERROR] الخط الإنجليزي غير موجود: {e_path}")
            return "\n".join(logs)
        
        a_temp = copy_to_temp(a_path, processing_dir)
        e_temp = copy_to_temp(e_path, processing_dir)

        temp_files = []
        
        a_ttf = convert_otf_to_ttf(a_temp, temp_files)
        e_ttf = convert_otf_to_ttf(e_temp, temp_files)
        
        a_ttf, e_ttf = try_unify_units([a_ttf, e_ttf])
        a_clean, e_clean = clean_languages(a_ttf, e_ttf, temp_files)

        outname = os.path.splitext(os.path.basename(a_path))[0] + "_" + os.path.splitext(os.path.basename(e_path))[0] + ".ttf"
        outpath = unique_name(os.path.join(processing_dir, outname))
        merged_path = merge_fonts_with_fonttools([a_clean, e_clean], outpath)

        preview_name = os.path.splitext(os.path.basename(merged_path))[0] + ".jpg"
        preview_path = unique_name(os.path.join(FONT_DIR, "previews", os.path.basename(preview_name)))
        create_preview(merged_path, preview_path)

        preview_121212_name = os.path.splitext(os.path.basename(merged_path))[0] + "_121212.jpg"
        preview_121212_path = unique_name(os.path.join(FONT_DIR, "previews", os.path.basename(preview_121212_name)))
        create_preview(merged_path, preview_121212_path, bg_color=(18,18,18), text_color="white")

        final_font_path = unique_name(os.path.join(FONT_DIR, "merged", os.path.basename(merged_path)))
        shutil.move(merged_path, final_font_path)

        log("✓ Successful!")
        return "\n".join(logs)

    except Exception as e:
        log(f"✗ Failed: {str(e)}")
        log(traceback.format_exc())
        return "\n".join(logs)
    finally:
        try:
            shutil.rmtree(processing_dir, ignore_errors=True)
        except:
            pass
