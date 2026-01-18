"""Tests for file context functionality (-F flag)."""

import os
import sys
import tempfile
import shutil
from pathlib import Path
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_cli.cli import _should_skip_file, _read_file_context, _MAX_FILE_SIZE, _MAX_TOTAL_SIZE, _BINARY_EXTENSIONS


class TestBinaryDetection:
    """Test binary file detection."""

    def test_known_binary_extensions(self):
        """Known binary extensions are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for ext in ['.png', '.jpg', '.zip', '.exe', '.so']:
                path = Path(tmpdir) / f'test{ext}'
                path.write_bytes(b'fake content')
                assert _should_skip_file(path), f"Should skip {ext}"

    def test_text_extensions_not_skipped(self):
        """Text extensions are not skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for ext in ['.txt', '.py', '.js', '.md', '.json']:
                path = Path(tmpdir) / f'test{ext}'
                path.write_text('text content')
                assert not _should_skip_file(path), f"Should not skip {ext}"

    def test_null_byte_detection(self):
        """Files with null bytes are detected as binary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'test.bin'
            path.write_bytes(b'text\x00with\x00nulls')
            assert _should_skip_file(path)

    def test_large_file_skipped(self, capsys):
        """Files larger than MAX_FILE_SIZE are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'large.txt'
            # Write a file larger than _MAX_FILE_SIZE
            path.write_bytes(b'x' * (_MAX_FILE_SIZE + 1))
            assert _should_skip_file(path)
            captured = capsys.readouterr()
            assert 'larger than' in captured.err

    def test_binary_extensions_constant(self):
        """Binary extensions set is comprehensive."""
        assert '.pyc' in _BINARY_EXTENSIONS
        assert '.so' in _BINARY_EXTENSIONS
        assert '.dll' in _BINARY_EXTENSIONS
        assert '.exe' in _BINARY_EXTENSIONS
        assert '.png' in _BINARY_EXTENSIONS
        assert '.jpg' in _BINARY_EXTENSIONS
        assert '.jpeg' in _BINARY_EXTENSIONS
        assert '.gif' in _BINARY_EXTENSIONS
        assert '.zip' in _BINARY_EXTENSIONS
        assert '.pdf' in _BINARY_EXTENSIONS
        assert '.sqlite' in _BINARY_EXTENSIONS


class TestFileContextReading:
    """Test file context reading and formatting."""

    def test_single_file(self):
        """Single file is read with XML-style header."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            path = Path('test.txt')
            path.write_text('Hello, world!')
            result = _read_file_context(['test.txt'])
            assert '<file path="test.txt">' in result
            assert 'Hello, world!' in result
            assert '</file>' in result

    def test_comma_separated_files(self):
        """Comma-separated files are all read."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path('file1.txt').write_text('content1')
            Path('file2.py').write_text('content2')
            result = _read_file_context(['file1.txt,file2.py'])
            assert '<file path="file1.txt">' in result
            assert '<file path="file2.py">' in result
            assert 'content1' in result
            assert 'content2' in result

    def test_duplicate_files_skipped(self):
        """Duplicate file references are only included once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path('dup.txt').write_text('content')
            result = _read_file_context(['dup.txt,dup.txt'])
            # Should only have one opening tag
            assert result.count('<file path="dup.txt">') == 1

    def test_directory_reading(self):
        """Directory reads all files (non-recursive, skips hidden)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path('test_dir').mkdir()
            Path('test_dir/a.txt').write_text('file a')
            Path('test_dir/b.py').write_text('file b')
            Path('test_dir/.hidden').write_text('hidden')
            Path('test_dir/subdir').mkdir()
            Path('test_dir/subdir/nested.txt').write_text('nested')

            result = _read_file_context(['test_dir'])
            assert 'file a' in result
            assert 'file b' in result
            assert 'hidden' not in result  # Hidden files skipped
            assert 'nested' not in result  # Subdirectories not recursed

    def test_directory_skips_binaries(self):
        """Directory mode skips binary files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path('test_dir').mkdir()
            Path('test_dir/text.txt').write_text('text')
            Path('test_dir/binary.png').write_bytes(b'fake image')

            result = _read_file_context(['test_dir'])
            assert 'text' in result
            assert 'binary.png' not in result

    def test_path_traversal_blocked(self):
        """Paths outside CWD are blocked."""
        original_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                os.chdir(tmpdir)
                Path('inside.txt').write_text('inside')
                # Try to reference parent directory
                with pytest.raises(SystemExit):
                    _read_file_context(['../etc/passwd'])
        finally:
            os.chdir(original_cwd)

    def test_nonexistent_file_error(self):
        """Nonexistent files cause error exit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            with pytest.raises(SystemExit):
                _read_file_context(['nonexistent.txt'])

    def test_relative_paths_in_output(self):
        """Output uses relative paths, not absolute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path('test.txt').write_text('content')
            result = _read_file_context(['test.txt'])
            # Should not contain absolute path
            assert tmpdir not in result
            assert os.sep + 'test.txt"' in result or 'test.txt">' in result

    def test_empty_file(self):
        """Empty files are included with empty content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path('empty.txt').write_text('')
            result = _read_file_context(['empty.txt'])
            assert '<file path="empty.txt">' in result
            assert '</file>' in result

    def test_file_with_special_characters(self):
        """Files with special characters are handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path('special.txt').write_text('Line 1\nLine 2\n"quoted"\n<tags>')
            result = _read_file_context(['special.txt'])
            assert 'Line 1' in result
            assert 'quoted' in result
            assert 'tags' in result


class TestSizeLimits:
    """Test size limit enforcement."""

    def test_total_size_limit(self, capsys):
        """Total size limit is enforced."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            # Create files that exceed total limit
            Path('file1.txt').write_bytes(b'x' * (_MAX_TOTAL_SIZE // 2))
            Path('file2.txt').write_bytes(b'x' * (_MAX_TOTAL_SIZE // 2))
            Path('file3.txt').write_text('should be skipped')

            result = _read_file_context(['file1.txt,file2.txt,file3.txt'])
            captured = capsys.readouterr()
            # Should get warning about limit
            assert 'limit' in captured.err.lower() or 'skipping' in captured.err.lower()

    def test_max_file_size_constant(self):
        """Size constants are properly defined."""
        assert _MAX_FILE_SIZE == 1024 * 1024  # 1 MB
        assert _MAX_TOTAL_SIZE == 5 * 1024 * 1024  # 5 MB


class TestEncodingHandling:
    """Test encoding robustness."""

    def test_non_utf8_file(self):
        """Non-UTF-8 files are handled with errors='replace'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path('mixed.txt').write_bytes(b'valid utf8 \xc3\xa9 invalid \xff byte')
            # Should not crash, should replace invalid bytes
            result = _read_file_context(['mixed.txt'])
            assert 'valid utf8' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
