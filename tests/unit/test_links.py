from src.links import generate_short_code


def test_generate_short_code():
    code = generate_short_code()
    assert len(code) == 6
    assert code.isalnum()
    assert code.isascii()


def test_generate_short_code_uniqueness():
    codes = {generate_short_code() for _ in range(100)}
    assert len(codes) > 1
