"""速率限制测试。"""
import pytest
from app.core.security import RateLimiter


class TestRateLimiter:
    def test_allows_within_limit(self):
        rl = RateLimiter()
        rl._max_requests = 5
        rl._window = 60
        for _ in range(5):
            assert rl._memory_check("test-key").allowed

    def test_blocks_over_limit(self):
        rl = RateLimiter()
        rl._max_requests = 3
        rl._window = 60
        for _ in range(3):
            assert rl._memory_check("test-key").allowed
        assert not rl._memory_check("test-key").allowed

    def test_separate_keys(self):
        rl = RateLimiter()
        rl._max_requests = 2
        rl._window = 60
        assert rl._memory_check("user-a").allowed
        assert rl._memory_check("user-a").allowed
        assert not rl._memory_check("user-a").allowed
        assert rl._memory_check("user-b").allowed
        assert rl._memory_check("user-b").allowed

    def test_sanitize_truncates(self):
        from app.core.security import sanitize_llm_input
        result = sanitize_llm_input("x" * 20000)
        assert len(result) <= 16000

    def test_sanitize_blocks_special_tokens(self):
        from app.core.security import sanitize_llm_input
        result = sanitize_llm_input("hello <|bad|> world")
        assert "[BLOCKED:" in result
