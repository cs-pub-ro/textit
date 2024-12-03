from typing import List
import bisect
import pypdfium2
import sys
import argparse
import numpy as np
import logging
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import pairwise_distances
from scipy import stats
import tempfile
import os
import re
import string
import ocrmypdf
import itertools
import tempfile
import logging
import traceback
import subprocess

from textit.metadata import Metadata
from textit.helpers import Result, format_exception, getLogger



logger = getLogger()

# If we have to cluster too many items, it will take too much, so don't even
# try.
CLUSTERING_THRESHOLD = 4000

# Characters that are "OK" to be extracted from a Romanian text.
# XXX Besides the obvious ones, the rest are added based on observations on
# arbitrary (manually selected) samples.
#
# If there aren't enough "OK" characters, the ocr will be invoked, which is
# expensive and riddled with potential exceptions.
# So we would like to invoke it as less as possible; thus we will include some
# foreign languages and hope that the contents will be later cleared down the
# pipeline by langid.
# Hungarian is a common language that might sneak in, so for now we add those.
MATH_SYMBOLS = "∀∁∂∃∄∅∆∇∈∉∊∋∌∍∎∏∐∑−∓∔∕∖∗∘∙√∛∜∝∞∟∠∡∢∣∤∥∦∧∨∩∪∫∬∭∮∯∰∱∲∳∴∵∶∷∸∹∺∻∼∽∾∿≀≁≂≃≄≅≆≇≈≉≊≋≌≍≎≏≐≑≒≓≔≕≖≗≘≙≚≛≜≝≞≟≠≡≢≣≤≥≦≧≨≩≪≫≬≭≮≯≰≱≲≳≴≵≶≷≸≹≺≻≼≽≾≿⊀⊁⊂⊃⊄⊅⊆⊇⊈⊉⊊⊋⊌⊍⊎⊏⊐⊑⊒⊓⊔⊕⊖⊗⊘⊙⊚⊛⊜⊝⊞⊟⊠⊡⊢⊣⊤⊥⊦⊧⊨⊩⊪⊫⊬⊭⊮⊯⊰⊱⊲⊳⊴⊵⊶⊷⊸⊹⊺⊻⊼⊽⊾⊿⋀⋁⋂⋃⋄⋅⋆⋇⋈⋉⋊⋋⋌⋍⋎⋏⋐⋑⋒⋓⋔⋕⋖⋗⋘⋙⋚⋛⋜⋝⋞⋟⋠⋡⋢⋣⋤⋥⋦⋧⋨⋩⋪⋫⋬⋭⋮⋯⋰⋱⋲⋳⋴⋵⋶⋷⋸⋹⋺⋻⋼⋽⋾⋿ΑαΒβΓγΔδΕεΖζΗηΘθΙιΚκΛλΜμΝνΞξΟοΠπΡρΣσ/ςΤτΥυΦφΧχΨψΩω"

# That is the UA, RU and SR alphabets, joined together, set-ified, then united
OK_CHARS = set(string.printable + "ăĂâÂîÎșȘțȚşŞŢţ©–…·►◄«»°¬—×›•❤←→„”" + \
        MATH_SYMBOLS + \
        "шћТҐИфбоувЗЕњнГЂџСсђЛхЁмЊырПеКжцчШНЈФлаВЏэидзптгєкъРіУЭљЋБХЇЙґЮАщЖьЄёЪюМяјЦїЬОІЧйЫДЉЩЯ" + \
        "ÁÉÍÓÖŐÚÜŰáéíóöőúüű")  # Hungarian-specific characters


def fix_diacritics(text: str) -> str:
    correct_diacritics = {
            "ã": "ă",
            "Ã": "Ă",
            "º": "ș",
            "ª": "Ș",
            "þ": "ț",
            "Þ": "Ț",
            "\x02": "-",
    }

    for (w, c) in correct_diacritics.items():
        text = text.replace(w, c)

    return text


def remove_references(input_text):
    output_text = re.sub(r"( ?(\[[0-9]+((-?[0-9]+)?(, ?[0-9]+)*)\])+)|( ?\([0-9]+((-?[0-9]+)?(, ?[0-9]+)*)\))|( ?\([^\)]*[0-9][0-9][0-9][0-9].?\))", "", input_text)
    return output_text


def clamp(value, smallest, largest):
    # Fastest way, probably: https://stackoverflow.com/a/22902954
    if value < smallest:
        return smallest
    elif value > largest:
        return largest

    return value

def same_line(bb1, bb2):
    """Determines if two boxes should be considered on the same line."""
    l1, b1, r1, t1 = bb1
    l2, b2, r2, t2 = bb2

    # TODO explain later
    if r2 < l1:
        return False

    len1 = t1 - b1
    len2 = t2 - b2
    oll = max(b1, b2)
    olh = min(t1, t2)
    ol_len = max(0, olh - oll)

    olthresh1 = len1 * 0.5
    olthresh2 = len2 * 0.5
    return ol_len >= olthresh1 - 2 or ol_len >= olthresh2 - 2


def get_encompassing_bbox(bboxes):
    """Get the minimal box that surrounds all input boxes."""
    minl, minb = None, None
    maxr, maxt = None, None
    for l, b, r, t in bboxes:
        if minl is None or l < minl:
            minl = l
        if minb is None or b < minb:
            minb = b
        if maxr is None or r > maxr:
            maxr = r
        if maxt is None or t > maxt:
            maxt = t

    return minl, minb, maxr, maxt


def rectangle_distance(rect1, rect2):
    """Used by the clustering algorithm.

    This is **not** the intuitive concept of Euclidean distance between the
    rectangles' centers, but rather it is the minimum distance between any two
    points that belong to the rectangles (e.g. if two rectangles touch, the
    distance is 0.

    """
    left1, bottom1, right1, top1 = rect1
    left2, bottom2, right2, top2 = rect2

    if right1 < left2:
        horizontal_dist = left2 - right1
    elif right2 < left1:
        horizontal_dist = left1 - right2
    else:
        horizontal_dist = 0

    if top1 < bottom2:
        vertical_dist = bottom2 - top1
    elif top2 < bottom1:
        vertical_dist = bottom1 - top2
    else:
        vertical_dist = 0

    return horizontal_dist + vertical_dist


class Page(object):
    def __init__(self, pdf_path, pdf_page, pnumber):
        self.page = pdf_page
        self.pnumber = pnumber
        self.pdf_path = pdf_path
        self._line_boxes = None
        self._text = None
        self._text_page = None
        self._broken = None

    def get_line_boxes(self):
        if self._line_boxes is None:
            self._compute_text_boxes()
            self._compute_lines()

        return self._line_boxes

    def get_text(self):
        if self._text is None:
            line_boxes = self.get_line_boxes()
            if line_boxes:
                self._text = "\n".join(text for _, lines in line_boxes for _, text in lines)
            else:
                self._text = ""

        return self._text

    def is_empty(self):
        return not self.get_text()

    def is_broken(self):
        if self._broken is None:
            text = self.get_text()
            if not text:
                self._broken = False
            else:
                total_chars = len(text)
                n_ok_chars = sum((c in OK_CHARS) for c in text)
                self._broken = (n_ok_chars / total_chars) < 0.95

        return self._broken

    def get_size(self):
        return self.page.get_size()

    def _compute_text_boxes(self):
        self.boxes = []
        self._compute_bboxes_sorted()
        if not self.bboxes:
            self._broken = True
            return

        if len(self.bboxes) > CLUSTERING_THRESHOLD:
            # Just give up and consider everything to be in the same area.
            self.eps = 1
            clusters = {0: self.bboxes}
        else:
            self._compute_epsilon()
            labels = self._perform_dbscan()

            clusters = {}
            for rect, label in zip(self.bboxes, labels):
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(rect)

        for _, bboxes in clusters.items():
            big_box = get_encompassing_bbox(bboxes)
            self.boxes.append((big_box, bboxes))

    def _compute_lines(self):
        def get_text_in_bbox(bbox):
            if self._text_page is None:
                self._text_page = self.page.get_textpage()

            return self._text_page.get_text_bounded(*bbox)

        def update_lines(lines, current_line_boxes):
            big_box = get_encompassing_bbox(current_line_boxes)
            text = get_text_in_bbox(big_box)
            text = fix_diacritics(text)
            lines.append((big_box, text))

        self._line_boxes = []
        if not self.bboxes:
            return

        for big_box, bboxes in self.boxes:
            lines = []
            current_line_boxes = [bboxes[0]]
            for prev, bbox in zip(bboxes, bboxes[1:]):
                if same_line(prev, bbox):
                    current_line_boxes.append(bbox)
                else:
                    update_lines(lines, current_line_boxes)
                    current_line_boxes = [bbox]

            if current_line_boxes:
                update_lines(lines, current_line_boxes)

            self._line_boxes.append((big_box, lines))

    def _compute_bboxes_sorted(self):
        def bbox_sort_key(bbox):
            l, b, r, t = bbox
            return (-t, l, b, r)

        self.bboxes = []
        bboxes_set = set()  # to keep them unique
        try:
            for obj in self.page.get_objects():
                if obj.type == 1:  # text type
                    bbox = obj.get_pos()
                    if bbox not in bboxes_set:
                        bisect.insort(self.bboxes, bbox, key=bbox_sort_key)
                        bboxes_set.add(bbox)
        except pypdfium2._helpers.misc.PdfiumError as e:
            se = str(e)
            logger.warning(f"Couldn't get page objects for page {self.pnumber} ({repr(self.pdf_path)})")
            if se == "Failed to get number of page objects.":
                return

            raise e

    def _perform_dbscan(self):
        distances = pairwise_distances(self.bboxes, metric=rectangle_distance)
        db = DBSCAN(eps=self.eps, min_samples=1, metric='precomputed').fit(distances)
        labels = db.labels_
        return labels

    def _compute_epsilon(self):
        """Highly bizarre and heuristic."""
        def same_line(bb1, bb2):
            """A more relaxed version; verified empirically."""
            _, b1, _, t1 = bb1
            _, b2, _, t2 = bb2
            m1 = (b1 + t1) / 2
            m2 = (b2 + t2) / 2
            return b1 <= m2 <= t1 or b2 <= m1 <= t2

        distances = []
        for bb1 in self.bboxes:
            mind = None
            for bb2 in self.bboxes:
                if same_line(bb1, bb2):
                    continue

                d = rectangle_distance(bb1, bb2)
                if mind is None or d < mind:
                    mind = d

            if mind is not None:
                bisect.insort(distances, mind)

        if not distances:
            self.eps = 1
            return

        mode = stats.mode(distances)
        if mode[1] < 5:
            l = len(distances)
            m = l // 2
            eps = distances[m] * 1.2 # hackish
        else:
            eps = mode[0] * 1.5

        self.eps = clamp(eps, 5, 15)


class PdfProcessor(object):
    def __init__(self, pdf_path, page_range=None):
        self.pdf_path = pdf_path
        self._pdf = None
        self._page_range = page_range
        self._pages = None
        self._broken = None
        self._contents = None
        self._text = None

    def get_pages(self):
        """Idempotent function."""
        def fix_page_range():
            step = 1
            if self._page_range is None:
                start, stop = 0, self._page_count
            else:
                if type(self._page_range) == int:
                    start, stop = self._page_range, self._page_range + 1
                else:
                    start = self._page_range.start
                    stop = self._page_range.stop
                    step = self._page_range.step

                start = clamp(start, 0, self._page_count - 1)
                stop = clamp(stop, 0, self._page_count - 1)

            self._page_range = range(start, stop, step)

        if self._pdf is None:
            self._pdf = pypdfium2.PdfDocument(self.pdf_path)
            self._page_count = len(self._pdf)
            fix_page_range()

            self._pages = []
            for i in self._page_range:
                try:
                    self._pages.append(Page(self.pdf_path, self._pdf[i], i))
                except pypdfium2._helpers.misc.PdfiumError as e:
                    se = str(e)
                    if se == "Failed to load page.":
                        logger.warning(f"Failed to load page {i} ({repr(self.pdf_path)})")

        return self._pages

    def get_contents(self):
        if self._contents is None:
            self._contents = []
            for page in self.get_pages():
                self._contents.append((page.pnumber, page.get_size(), page.get_line_boxes()))

        return self._contents

    def broken_pdf(self):
        if self._broken is None:
            # check that most pages had high-quality text
            broken_pages = 0
            empty_pages = 0
            pages = self.get_pages()
            for page in pages[:10]:
                if page.is_broken():
                    broken_pages += 1
                elif page.is_empty():
                    empty_pages += 1

            broken_threshold = min(3, self._page_count)
            empty_threshold = min(3, self._page_count)
            logger.debug(f"Broken pages: {broken_pages}/{self._page_count}")
            self._broken = broken_pages >= broken_threshold or \
                           empty_pages >= empty_threshold

        return self._broken


def apply_ocr(pdf_path, page_range=None):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_output:
        temp_output_path = temp_output.name
        try:
            ocrmypdf.ocr(pdf_path, temp_output_path, l='ron',
                         invalidate_digital_signatures=True,
                         force_ocr=True,
                         progress_bar=False,
                         deskew=True,
                         max_image_mpixels=900,
                         )
        except ocrmypdf.exceptions.SubprocessOutputError as e:
            _, _, fname, _ = traceback.extract_tb(e.__traceback__)[-1]
            logger.warning(f"FUNCTION {fname} FAILED!")
            if fname == "get_deskew":
                ocrmypdf.ocr(pdf_path, temp_output_path, l='ron',
                             invalidate_digital_signatures=True,
                             force_ocr=True,
                             progress_bar=False,
                             deskew=False,
                             max_image_mpixels=900,
                             )
            else:
                raise e

        proc = PdfProcessor(temp_output_path, page_range)

    return proc


def decrypt_pdf(inpath, outpath):
    subprocess.run(["qpdf", "--decrypt", inpath, outpath])


def process_pdf(pdf_path, page_range=None):
    proc = PdfProcessor(pdf_path, page_range)
    procmeta = {}
    if proc.broken_pdf():
        procmeta["ocr"] = True
        try:
            proc = apply_ocr(pdf_path, page_range)
        except ocrmypdf.exceptions.EncryptedPdfError:
            procmeta["decrypted"] = True
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_output:
                temp_output_path = temp_output.name
                decrypt_pdf(pdf_path, temp_output_path)
                proc = apply_ocr(temp_output_path, page_range)

    return proc, procmeta


def line_cleaner(doc_info):
    def ends_in_punctuation(line):
        if not line:
            return False

        end_punctuation = {
                ".", "!", "?", "...", ":", ";", "…",
                }
        end_quotes = {"\"", "”", "»"}

        stripped_line = line.strip()
        endch = stripped_line[-1]
        if endch in end_punctuation:
            return True

        if endch in end_quotes:
            if len(line) == 1:
                return False

            return stripped_line[-2] in end_punctuation

        return False

    def get_text_left_margin(lines):
        s = 0
        for (l, _, _, _), _ in lines:
            s += l

        return s / len(lines)

    def quality_stats(line_box, tleft_margin, bbox, text):
        result = {}

        char_count = len(text)
        result["char_count"] = char_count
        words = text.split()
        wordcount = len(words)

        capwordcount = 0
        lowwordcount = 0
        nonwordcount = 0
        for word in words:
            if not word:
                continue

            if word[0].isupper():
                capwordcount += 1
            elif word[0].islower():
                lowwordcount += 1
            else:
                nonwordcount += 1

        result["word_count"] = wordcount
        result["nonword_ratio"] = nonwordcount / wordcount if wordcount else 0
        result["lowercase_ratio"] = lowwordcount / wordcount if wordcount else 0

        ok_count = len([c for c in text if c in OK_CHARS])
        result["ok_chars_ratio"] = ok_count / char_count if char_count else 0

        left_margin, _, right_margin, _ = line_box
        box_width = right_margin - left_margin
        max_indent = 0.1 * box_width
        l, b, r, t = bbox
        result["line_indent"] = abs(l - left_margin) >= 2
        result["too_left"] = abs(l - left_margin) >= max_indent
        result["ends_abruptly"] = abs(r - right_margin) >= 25  # FIXME
        result["punctuation"] = ends_in_punctuation(text)
        result["paragraph_start"] = text[0].isupper() or text[0] in {"-", "—"} if text else False

        return result

    result_lines = []
    paragraphs = []
    paragraph = []
    paragraph_started = False
    for pnumber, psize, boxes in doc_info:
        for line_box, lines in boxes:
            tleft_margin = get_text_left_margin(lines)
            qstats = []
            for bbox, text in lines:
                text = text.strip()
                qs = quality_stats(line_box, tleft_margin, bbox, text)
                qstats.append(qs)
                if qs["ok_chars_ratio"] <= 0.95 or \
                   qs["nonword_ratio"] >= 0.35 or \
                   qs["lowercase_ratio"] < 0.35 or \
                   (qs["ends_abruptly"] and not qs["punctuation"]) or \
                   qs["too_left"]:
                    continue

                if qs["paragraph_start"]:
                    paragraph_started = True

                if paragraph_started:
                    if qs["ends_abruptly"] and qs["punctuation"]:
                        paragraph.append(text)
                        paragraphs.append("".join(paragraph))
                        paragraph = []
                        paragraph_started = False
                    else:
                        # 0x2 is a common OCR artifact for an end-of-line dash.
                        if text[-1] in {"—", "-", chr(2)}:
                            paragraph.append(text[:-1])
                        else:
                            paragraph.append(text + " ")

    if paragraph:
        paragraphs.append("".join(paragraph))

    text = "\n".join(paragraphs)
    text = remove_references(text)

    return text.splitlines()


def pdf_handler(file_path: str, metadata: Metadata) -> tuple[Result[List[str]], Metadata]:
    ocrmypdf.configure_logging(ocrmypdf.Verbosity.quiet)
    try:
        proc, procmeta = process_pdf(file_path)
        for k, v in procmeta.items():
            setattr(metadata, k, v)

        doc_info = proc.get_contents()
        extracted_text = line_cleaner(doc_info)
        return (Result.ok(extracted_text), metadata)
    except Exception as e:
        se = str(e)
        if se == "Failed to load document (PDFium: Incorrect password error).":
            metadata.drop_reason = "unknown_encryption_password"
        elif se in {"Failed to load document (PDFium: Data format error).",
                "Failed to load document (PDFium: Success)."}:
            metadata.drop_reason = "broken-pdf"

        estr = format_exception(e)
        return (Result.err(f"Error extracting text from PDF at '{file_path}':{estr}"), metadata)


if __name__ == "__main__":
    import sys
    assert len(sys.argv) == 3
    pdf_path = sys.argv[1]
    result, metadata = pdf_handler(pdf_path, Metadata())
    print("Metadata:\n", metadata)
    with open(sys.argv[2], "w") as fout:
        fout.write("\n".join(result.unwrap()))
