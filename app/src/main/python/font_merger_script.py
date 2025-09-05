#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
دمج الخطوط مع معاينة عالية الجودة - نسخة معدلة للتطبيقات والتشغيل الآلي
Font merger with high-quality preview - Modified for Apps & Automation
"""

import os
import sys
import shutil
import tempfile
import argparse
import time
import traceback
from fontTools.ttLib import TTFont
from fontTools.merge import Merger
from fontTools.subset import main as subset_main
from PIL import Image, ImageDraw, ImageFont, features
import arabic_reshaper

# محاولة استيراد uharfbuzz (أكثر شيوعاً في البيئات المحدودة)
try:
    import uharfbuzz as hb
except ImportError:
    hb = None

# --- Constants ---
EN_PREVIEW = "The quick brown fox jumps over the lazy dog. 1234567890"
AR_PREVIEW = "سمَات مجّانِية، إختر منْ بين أكثر من ١٠٠ سمة مجانية او انشئ سماتك الخاصة هُنا في هذا التطبيق النظيف الرائع، وأظهر الابداع.١٢٣٤٥٦٧٨٩٠"

# --- Global variable for log file path ---
LOG_FILE = None

# ---------- Logging ----------
def setup_logging(base_dir):
    """إعداد ملف السجل بناءً على المجلد الأساسي."""
    global LOG_FILE
    logs_dir = os.path.join(base_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    base_name = "merge_log"
    counter = 1
    log_file = os.path.join(logs_dir, f"{base_name}.txt")
    while os.path.exists(log_file):
        log_file = os.path.join(logs_dir, f"{base_name}_{counter}.txt")
        counter += 1
    LOG_FILE = log_file

    # كتابة رأس السجل
    ts = time.strftime("%Y-%m-%d %I:%M:%S %p")
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"{ts} - بدء دمج الخطوط\n")
            f.write("="*30 + "\n")
    except Exception as e:
        print(f"ERROR: Failed to create log file: {e}")

def write_log_line(line):
    """كتابة سطر في ملف السجل."""
    if not LOG_FILE:
        print("WARNING: Log file not initialized.")
        return
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{line}\n")
    except Exception as e:
        print(f"ERROR: Failed to write to log file: {e}")

# ---------- Font Utilities ----------
def has_cff(font_path):
    """التحقق مما إذا كان الخط يحتوي على جداول CFF (مما يدل على أنه OTF)."""
    try:
        with TTFont(font_path) as f:
            return "CFF " in f or "CFF2" in f
    except Exception:
        return False

def convert_otf_to_ttf(font_path, temp_dir):
    """
    تحويل الخطوط بصيغة OTF (CFF) إلى TTF باستخدام fontTools فقط.
    """
    base, ext = os.path.splitext(os.path.basename(font_path))
    
    # التحقق مما إذا كان التحويل ضرورياً
    if ext.lower() != ".otf" and not has_cff(font_path):
        write_log_line(f"FontTools: No conversion needed for {base}{ext}.")
        return font_path

    # إنشاء مسار للملف المحول في المجلد المؤقت
    out_path = os.path.join(temp_dir, f"{base}_converted.ttf")
    
    try:
        font = TTFont(font_path)
        # إزالة نكهة الخط (flavor) يجبر fontTools على تحويله إلى TTF (glyf) عند الحفظ
        font.flavor = None
        font.save(out_path)
        write_log_line(f"FontTools: Converted {os.path.basename(font_path)} to TTF format.")
        return out_path
    except Exception as e:
        write_log_line(f"ERROR: FontTools failed to convert {os.path.basename(font_path)}: {e}")
        raise RuntimeError(f"Failed to convert {font_path} to TTF.") from e

def try_unify_units(paths):
    """توحيد قيمة unitsPerEm لجميع الخطوط."""
    fonts = [TTFont(p) for p in paths]
    units = [f['head'].unitsPerEm for f in fonts]
    target_upem = max(units)
    
    for i, font in enumerate(fonts):
        current_upem = font['head'].unitsPerEm
        if current_upem == target_upem:
            continue
            
        scale = float(target_upem) / float(current_upem)
        write_log_line(f"FontTools: Scaling {os.path.basename(paths[i])} from {current_upem} to {target_upem} UPM.")
        
        try:
            # توسيع الجداول
            if 'glyf' in font:
                for glyph in font['glyf'].glyphs.values():
                    if glyph.isComposite():
                         glyph.transform((scale, 0, 0, scale, 0, 0))
                    else:
                        for j, (x, y) in enumerate(glyph.coordinates):
                            glyph.coordinates[j] = (round(x * scale), round(y * scale))
            
            if 'hmtx' in font:
                for glyph_name, (width, lsb) in font['hmtx'].metrics.items():
                    font['hmtx'].metrics[glyph_name] = (round(width * scale), round(lsb * scale))
            
            if 'vmtx' in font:
                for glyph_name, (height, tsb) in font['vmtx'].metrics.items():
                    font['vmtx'].metrics[glyph_name] = (round(height * scale), round(tsb * scale))
            
            if 'hhea' in font:
                font['hhea'].ascent = round(font['hhea'].ascent * scale)
                font['hhea'].descent = round(font['hhea'].descent * scale)
            
            if 'OS/2' in font:
                os2 = font['OS/2']
                os2.usWinAscent = round(os2.usWinAscent * scale)
                os2.usWinDescent = abs(round(os2.usWinDescent * scale)) # يجب أن تكون موجبة
                os2.sTypoAscender = round(os2.sTypoAscender * scale)
                os2.sTypoDescender = round(os2.sTypoDescender * scale)

            font['head'].unitsPerEm = target_upem
            font.save(paths[i])

        except Exception as e:
            write_log_line(f"WARN: Scaling failed for {os.path.basename(paths[i])}: {e}")
    
    return paths

# ---------- Subsetting ----------
def subset_font(font_path, unicodes, temp_dir):
    """تقليص حجم الخط ليحتوي فقط على الحروف المحددة."""
    base = os.path.splitext(os.path.basename(font_path))[0]
    out_path = os.path.join(temp_dir, f"{base}_subset.ttf")
    
    # حفظ واستعادة sys.argv الأصلي
    original_argv = sys.argv
    try:
        # بناء قائمة المعلمات لـ pyftsubset
        sys.argv = [
            "pyftsubset",
            font_path,
            f"--unicodes={unicodes}",
            f"--output-file={out_path}",
            "--no-hinting",
            "--ignore-missing-unicodes"
        ]
        subset_main()
    except SystemExit:
        # pyftsubset تخرج بـ SystemExit عند النجاح
        pass
    except Exception as e:
        write_log_line(f"WARN: Subsetting failed for {os.path.basename(font_path)}: {e}")
        return font_path # إرجاع المسار الأصلي في حالة الفشل
    finally:
        sys.argv = original_argv # استعادة sys.argv دائماً
        
    if os.path.exists(out_path):
        write_log_line(f"pyftsubset: Successfully subsetted {os.path.basename(font_path)}.")
        return out_path
    
    write_log_line(f"WARN: Subset output file not found for {os.path.basename(font_path)}.")
    return font_path

def clean_up_languages(ar_path, en_path, temp_dir):
    """
    تنقية الخطوط: الخط العربي يحتوي فقط على الحروف العربية، والخط الإنجليزي على الحروف اللاتينية الأساسية.
    """
    # نطاقات اليونيكود للغة العربية + الأرقام
    arabic_ranges = ",".join([
        "U+0600-06FF", "U+0750-077F", "U+08A0-08FF",
        "U+FB50-FDFF", "U+FE70-FEFF", "U+0660-0669"
    ])
    # نطاق ASCII الأساسي للحروف والأرقام والعلامات
    ascii_range = "U+0020-007E"
    
    ar_subset = subset_font(ar_path, arabic_ranges, temp_dir)
    en_subset = subset_font(en_path, ascii_range, temp_dir)
    
    return ar_subset, en_subset
    
# ---------- Unique output name ----------
def get_unique_path(path):
    """الحصول على مسار فريد للملف لتجنب الكتابة فوق ملف موجود."""
    base, ext = os.path.splitext(path)
    counter = 1
    new_path = path
    while os.path.exists(new_path):
        new_path = f"{base}_{counter}{ext}"
        counter += 1
    return new_path

# ---------- Preview Creation ----------
def wrap_text_to_lines(text, font, max_width, is_ar=False, draw=None):
    """تقسيم النص إلى أسطر لتناسب عرض معين."""
    if draw is None:
        # إنشاء كائن رسم مؤقت إذا لم يتم توفيره
        draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        
    lines = []
    # التعامل مع النص العربي ككتلة واحدة في كل سطر
    if is_ar:
        words = text.split(' ')
        current_line = ""
        for word in words:
            # إضافة الكلمة التالية وتجربة قياسها
            test_line = (current_line + ' ' + word).strip()
            bbox = draw.textbbox((0, 0), test_line, font=font, direction="rtl", language="ar")
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line) # إضافة السطر الأخير
        return lines

    # التعامل مع النص الإنجليزي كلمة بكلمة
    return [line.strip() for line in text.splitlines() for wrapped_line in [line] for word_list in [wrapped_line.split(' ')] for line in [word_list.pop(0)] if word_list for line in (lambda l, w: [l] + w if draw.textlength(l, font=font) <= max_width else l.split())(line, []) for word in word_list if (lambda l, w: l if draw.textlength(l + ' ' + w, font=font) <= max_width else (lines.append(l), w))(line, word)]

def create_preview(merged_ttf, out_jpg, bg_color, text_color):
    """إنشاء صورة معاينة عالية الجودة للخط المدمج."""
    W, H = 3200, 1440  # دقة عالية مناسبة
    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font_size = 150 # حجم خط ابتدائي
        
        # محاولة تحميل الخط
        try:
            font = ImageFont.truetype(merged_ttf, font_size)
        except Exception as e:
            write_log_line(f"WARN: Could not load merged font for preview: {e}. Using default.")
            font = ImageFont.load_default()

        # حساب منطقة النص (90% من عرض الصورة)
        max_w = int(W * 0.9)
        padding_y = int(H * 0.1)
        
        # --- النص الإنجليزي (الجزء العلوي) ---
        # استخدام التفاف بسيط للنص الإنجليزي
        en_lines = [
            "The quick brown fox jumps",
            "over the lazy dog.",
            "1234567890"
        ]
        
        y = padding_y
        for line in en_lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            x = (W - line_width) / 2
            draw.text((x, y), line, font=font, fill=text_color)
            y += line_height + int(font_size * 0.2) # تباعد بين الأسطر

        # --- النص العربي (الجزء السفلي) ---
        reshaped_ar = arabic_reshaper.reshape(AR_PREVIEW)
        bidi_ar = get_display(reshaped_ar)
        
        # التفاف النص العربي
        ar_lines = wrap_text_to_lines(bidi_ar, font, max_w, is_ar=True, draw=draw)
        
        # حساب الارتفاع الكلي للنص العربي للتموضع
        total_ar_height = sum(draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] for line in ar_lines)
        total_ar_height += (len(ar_lines) - 1) * int(font_size * 0.2)
        
        # البدء من منتصف النصف السفلي من الصورة
        y = (H / 2) + ((H / 2) - total_ar_height) / 2

        for line in ar_lines:
            bbox = draw.textbbox((0, 0), line, font=font, direction="rtl", language="ar")
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            x = (W - line_width) / 2
            draw.text((x, y), line, font=font, fill=text_color, direction="rtl", language="ar")
            y += line_height + int(font_size * 0.2)
            
        img.save(out_jpg, "JPEG", quality=95, dpi=(300, 300))
        write_log_line(f"Pillow: Created preview image at {os.path.basename(out_jpg)}.")
        return True

    except Exception as ex:
        write_log_line(f"ERROR: Preview creation failed: {ex}\n{traceback.format_exc()}")
        return False

# ---------- Main Execution ----------
def main(args):
    # إعداد المجلدات وملف السجل
    base_dir = args.output_dir
    os.makedirs(os.path.join(base_dir, "previews"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "merged"), exist_ok=True)
    setup_logging(base_dir)
    
    # استخدام مجلد مؤقت آمن
    temp_dir = tempfile.mkdtemp(prefix="font_merge_", dir=os.path.join(base_dir, "temp_processing"))
    
    try:
        print("Starting font merge process...")
        write_log_line("=== Font Merge Process Started ===")

        ar_path = args.arabic_font
        en_path = args.english_font

        if not os.path.exists(ar_path):
            raise FileNotFoundError(f"Arabic font not found: {ar_path}")
        if not os.path.exists(en_path):
            raise FileNotFoundError(f"English font not found: {en_path}")
            
        # نسخ الخطوط إلى المجلد المؤقت للعمل عليها
        ar_temp = shutil.copy(ar_path, temp_dir)
        en_temp = shutil.copy(en_path, temp_dir)

        # 1. تحويل الخطوط إلى TTF إذا لزم الأمر
        print("Step 1/6: Converting fonts to TTF (if needed)...")
        ar_ttf = convert_otf_to_ttf(ar_temp, temp_dir)
        en_ttf = convert_otf_to_ttf(en_temp, temp_dir)

        # 2. توحيد unitsPerEm
        print("Step 2/6: Unifying font metrics (unitsPerEm)...")
        try:
            ar_unified, en_unified = try_unify_units([ar_ttf, en_ttf])
        except Exception as e:
            write_log_line(f"WARN: Failed to unify unitsPerEm, proceeding anyway. Error: {e}")
            ar_unified, en_unified = ar_ttf, en_ttf

        # 3. تنقية اللغات (اختياري لكن موصى به)
        print("Step 3/6: Subsetting fonts to keep relevant glyphs...")
        ar_clean, en_clean = clean_up_languages(ar_unified, en_unified, temp_dir)

        # 4. دمج الخطوط باستخدام fontTools
        print("Step 4/6: Merging Arabic and English fonts...")
        out_name = f"{os.path.splitext(os.path.basename(ar_path))[0]}_{os.path.splitext(os.path.basename(en_path))[0]}.ttf"
        merged_path_temp = os.path.join(temp_dir, out_name)
        
        merger = Merger()
        merged_font = merger.merge([ar_clean, en_clean])
        merged_font.save(merged_path_temp)
        write_log_line("FontTools: Fonts merged successfully.")

        # نقل الخط المدمج إلى المجلد النهائي
        final_font_path = get_unique_path(os.path.join(base_dir, "merged", os.path.basename(merged_path_temp)))
        shutil.move(merged_path_temp, final_font_path)

        # 5. إنشاء صور المعاينة
        print("Step 5/6: Creating preview images...")
        preview_name = os.path.splitext(os.path.basename(final_font_path))[0]
        
        # Preview 1 (White background)
        preview_path_white = get_unique_path(os.path.join(base_dir, "previews", f"{preview_name}_white.jpg"))
        create_preview(final_font_path, preview_path_white, bg_color="white", text_color="black")
        
        # Preview 2 (Dark background)
        preview_path_dark = get_unique_path(os.path.join(base_dir, "previews", f"{preview_name}_dark.jpg"))
        create_preview(final_font_path, preview_path_dark, bg_color="#121212", text_color="white")
        
        print("Step 6/6: Process finished successfully.")
        write_log_line("=== Process Finished Successfully ===")
        print("\n--- Outputs ---")
        print(f"Merged Font: {final_font_path}")
        print(f"White Preview: {preview_path_white}")
        print(f"Dark Preview: {preview_path_dark}")
        
    except Exception as e:
        error_msg = f"FATAL ERROR: {e}"
        print(error_msg)
        write_log_line(error_msg)
        write_log_line(traceback.format_exc())
        sys.exit(1) # الخروج برمز خطأ
        
    finally:
        # تنظيف المجلد المؤقت دائماً
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("Temporary files cleaned up.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge Arabic and English fonts and create high-quality previews.")
    parser.add_argument("arabic_font", help="Path to the Arabic font file.")
    parser.add_argument("english_font", help="Path to the English font file.")
    parser.add_argument("output_dir", help="The base directory for all outputs (merged, previews, logs).")
    
    # إنشاء مجلد مؤقت للمعالجة داخل مجلد الإخراج
    # هذا يضمن أن تكون الملفات المؤقتة في مكان معروف
    args = parser.parse_args()
    temp_processing_dir = os.path.join(args.output_dir, "temp_processing")
    os.makedirs(temp_processing_dir, exist_ok=True)
    
    main(args)
