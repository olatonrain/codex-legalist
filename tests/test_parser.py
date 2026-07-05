from legalis.parser import extract_text


class TestParser:
    def test_extract_text_from_txt(self):
        content = b"The defendant stole a car."
        result = extract_text(content, "test.txt")
        assert "defendant" in result

    def test_extract_text_from_empty_file(self):
        content = b""
        result = extract_text(content, "test.txt")
        assert result == ""

    def test_extract_text_unknown_extension(self):
        content = b"Some content"
        result = extract_text(content, "test.unknown")
        assert "Some content" in result or result == ""
