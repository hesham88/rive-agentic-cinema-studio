"""Tests for the Marketplace fetcher.

No network here — a test that needs a live CDN is a monitor, not a test. What
is covered is everything that can go wrong without the network noticing: slug
parsing, URL derivation, the Rive fingerprint check that stops an HTML error
page being saved as a corrupt asset, and the attribution record that CC BY
requires.
"""

import pytest

from genassets.marketplace import (
    ATTRIBUTION_FILE,
    FetchedFile,
    MarketplaceError,
    runtime_url,
    slug_from_url,
)

SLUG = "1714-4322-rives-animated-emojis"


class TestSlug:
    @pytest.mark.parametrize("url", [
        SLUG,
        f"https://rive.app/community/files/{SLUG}/",
        f"https://rive.app/community/files/{SLUG}",
        f"https://public.rive.app/community/runtime-files/{SLUG}.riv",
    ])
    def test_extracts_from_every_url_shape(self, url):
        assert slug_from_url(url) == SLUG

    def test_rejects_a_url_with_no_slug(self):
        with pytest.raises(MarketplaceError, match="no marketplace slug"):
            slug_from_url("https://rive.app/marketplace/")

    def test_the_error_shows_the_expected_shape(self):
        # A slug is not guessable, so the message has to demonstrate one.
        with pytest.raises(MarketplaceError, match="1714-4322"):
            slug_from_url("nonsense")


class TestRuntimeUrl:
    def test_derives_the_direct_url_from_a_slug(self):
        assert runtime_url(SLUG) == (
            f"https://public.rive.app/community/runtime-files/{SLUG}.riv")

    def test_a_page_url_gives_the_same_answer(self):
        # This is what makes bulk fetching one request per file rather than two.
        assert runtime_url(f"https://rive.app/community/files/{SLUG}/") == runtime_url(SLUG)


class TestFetchedFile:
    def _file(self, data=b"RIVE\x07\x00\x00", title="Rive's Animated Emojis"):
        return FetchedFile(
            slug=SLUG, bytes=data,
            page_url=f"https://rive.app/community/files/{SLUG}/",
            runtime_url=runtime_url(SLUG), title=title,
        )

    def test_recognises_a_rive_file(self):
        assert self._file().is_rive

    def test_rejects_an_html_error_page(self):
        # The CDN answers some requests with HTML; saving that as a .riv gives
        # a file that fails to load with no useful error.
        assert not self._file(b"<!DOCTYPE html>").is_rive

    def test_reports_its_size(self):
        assert self._file(b"RIVE" + b"\x00" * 96).size == 100

    def test_save_writes_the_file(self, tmp_path):
        path = self._file().save(tmp_path)
        assert path.name == f"{SLUG}.riv"
        assert path.read_bytes()[:4] == b"RIVE"

    def test_save_writes_attribution(self, tmp_path):
        self._file().save(tmp_path)
        record = (tmp_path / ATTRIBUTION_FILE).read_text(encoding="utf-8")
        assert "CC BY" in record
        assert SLUG in record
        assert "Rive's Animated Emojis" in record

    def test_attribution_does_not_duplicate_on_refetch(self, tmp_path):
        f = self._file()
        f.save(tmp_path)
        f.save(tmp_path)
        record = (tmp_path / ATTRIBUTION_FILE).read_text(encoding="utf-8")
        assert record.count(f"`{SLUG}.riv`") == 1

    def test_attribution_accumulates_across_files(self, tmp_path):
        self._file().save(tmp_path)
        other = FetchedFile(
            slug="850-1653-smiley-switch", bytes=b"RIVE\x07",
            page_url="https://rive.app/community/files/850-1653-smiley-switch/",
            runtime_url=runtime_url("850-1653-smiley-switch"), title="Smiley Switch",
        )
        other.save(tmp_path)
        record = (tmp_path / ATTRIBUTION_FILE).read_text(encoding="utf-8")
        assert SLUG in record and "smiley-switch" in record

    def test_a_titleless_file_still_records_a_row(self, tmp_path):
        self._file(title="").save(tmp_path)
        assert SLUG in (tmp_path / ATTRIBUTION_FILE).read_text(encoding="utf-8")
