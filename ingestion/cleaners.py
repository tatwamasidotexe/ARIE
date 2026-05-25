"""
Text cleaners for ingestion pipelines.

Retrieval-quality goal: embedding models (e.g. BAAI/bge-base-en-v1.5) map noisy
whitespace, HTML entities, and markup artifacts into unstable vectors. RSS/XML
pollution previously contaminated the corpus — these steps strip transport noise
while preserving technical meaning (equations in plaintext, terminology, casing).
"""
from __future__ import annotations

import html
import re
import unicodedata

# Control chars and zero-width / BOM junk break tokenizers and add no semantics.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ZERO_WIDTH = re.compile(r"[\u200b-\u200d\ufeff\u2060]")

# Atom/XML sometimes leaves tags in summary fields; strip without NLP-style rewriting.
_XML_TAGS = re.compile(r"<[^>]+>")

# Collapse runs of whitespace (including newlines from arXiv API formatting).
_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def unescape_html_entities(text: str) -> str:
    """Decode &amp; &lt; etc. Entities change token boundaries and hurt recall."""
    if not text:
        return ""
    return html.unescape(text)


def strip_xml_markup(text: str) -> str:
    """Remove leftover tags from Atom/XML. Tags are not semantic for embeddings."""
    if not text:
        return ""
    return _XML_TAGS.sub(" ", text)


def remove_unicode_junk(text: str) -> str:
    """Drop control and zero-width chars. Keeps valid Unicode math/symbols intact."""
    if not text:
        return ""
    text = _CONTROL_CHARS.sub("", text)
    text = _ZERO_WIDTH.sub("", text)
    # Normalize compatibility forms (e.g. fullwidth digits) without lowercasing.
    return unicodedata.normalize("NFKC", text)


def normalize_whitespace(text: str) -> str:
    """
    Flatten arXiv's newline-padded titles/abstracts to single spaces.

    Excessive newlines create false paragraph boundaries in chunk-less embedding;
    repeated spaces dilute dense vectors without adding meaning.
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _MULTI_NEWLINE.sub("\n\n", text)
    lines = [ _MULTI_SPACE.sub(" ", line).strip() for line in text.split("\n") ]
    text = "\n".join(line for line in lines if line)
    return re.sub(r"\s+", " ", text).strip()


def clean_arxiv_text(text: str) -> str:
    """
    Full cleaning pipeline for arXiv title/abstract fields.

    Order matters: unescape before tag strip, junk removal before whitespace fold.
    Does not lowercase, stem, or strip LaTeX — preserves technical content.
    """
    if not text:
        return ""
    text = unescape_html_entities(text)
    text = strip_xml_markup(text)
    text = remove_unicode_junk(text)
    text = normalize_whitespace(text)
    return text


def clean_title(title: str) -> str:
    """Titles are short; same pipeline avoids inconsistent title vs abstract noise."""
    return clean_arxiv_text(title)


def clean_abstract(abstract: str) -> str:
    """Abstracts are the primary embedding body — must be maximally clean."""
    return clean_arxiv_text(abstract)