import io

from src.links import _generate_qr


def test_generate_qr():
    url = "http://localhost:8000/test123"
    buf = _generate_qr(url)

    assert isinstance(buf, io.BytesIO)
    assert buf.tell() == 0
    content = buf.read()
    assert content.startswith(b"\x89PNG")


def test_generate_qr_different_urls():
    url1 = "http://example.com/test1"
    url2 = "http://example.com/test2"

    buf1 = _generate_qr(url1)
    buf2 = _generate_qr(url2)

    content1 = buf1.read()
    content2 = buf2.read()

    assert content1 != content2
