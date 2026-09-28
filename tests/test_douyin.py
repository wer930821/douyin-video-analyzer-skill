import pytest

from app.douyin import DouyinError, validate_douyin_url


def test_accepts_short_douyin_url():
    assert validate_douyin_url("https://v.douyin.com/abc123/") == "https://v.douyin.com/abc123/"


def test_accepts_full_douyin_url():
    url = "https://www.douyin.com/video/1234567890"
    assert validate_douyin_url(url) == url


def test_rejects_tiktok():
    with pytest.raises(DouyinError):
        validate_douyin_url("https://www.tiktok.com/@x/video/123")


def test_rejects_non_http():
    with pytest.raises(DouyinError):
        validate_douyin_url("ftp://v.douyin.com/abc")
