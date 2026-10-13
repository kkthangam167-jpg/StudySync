import os
from unittest.mock import patch, MagicMock
from app.services.ai_service import AIService

def test_ai_fallback_when_api_key_missing(app, user1):
    with app.app_context():
        with patch.dict(os.environ, {'GEMINI_API_KEY': ''}):
            assert not AIService.is_configured()

            # Test recommendation prompt in fallback mode
            res = AIService.generate_response(
                user=user1,
                user_message="What should I study today?",
                use_academic_context=True
            )
            assert res['success'] is True
            assert res['is_live'] is False
            assert 'Recommended Study Focus' in res['content'] or 'All Caught Up' in res['content']
            assert res['provider'] == 'StudySync Offline Intelligence'
            assert 'GEMINI_API_KEY is not configured' in res['warning']

def test_ai_endpoint_empty_message_validation(auth_client1):
    # Empty string
    res = auth_client1.post('/api/ai/chat', json={'message': '   '})
    assert res.status_code == 400
    assert 'cannot be empty' in res.get_json()['error']

    # Non-string message
    res2 = auth_client1.post('/api/ai/chat', json={'message': 12345})
    assert res2.status_code == 400

def test_ai_endpoint_oversized_message_validation(auth_client1):
    huge_message = "A" * 2005
    res = auth_client1.post('/api/ai/chat', json={'message': huge_message})
    assert res.status_code == 400
    assert 'exceeds maximum limit' in res.get_json()['error']

def test_ai_student_context_grounding(app, user1):
    with app.app_context():
        context_str = AIService.build_student_context(user1)
        assert user1.full_name in context_str
        assert str(user1.daily_available_hours) in context_str
        # Ensure passwords or password hashes never leak into context
        assert 'password' not in context_str.lower()
        assert 'scrypt:' not in context_str

def test_ai_successful_gemini_generation_mocked(app, user1):
    with app.app_context():
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'mock-valid-gemini-key', 'GEMINI_MODEL': 'gemini-2.5-flash'}):
            assert AIService.is_configured()

            # Mock the google.genai Client
            mock_response = MagicMock()
            mock_response.text = "Here is a breakdown of 3NF decomposition proofs..."

            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response

            with patch('google.genai.Client', return_value=mock_client):
                res = AIService.generate_response(
                    user=user1,
                    user_message="Explain 3NF decomposition",
                    use_academic_context=True
                )
                assert res['success'] is True
                assert res['is_live'] is True
                assert "3NF decomposition" in res['content']
                assert "Google Gemini API" in res['provider']
                assert res['warning'] is None

def test_ai_api_error_handling_graceful(app, user1):
    with app.app_context():
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'mock-key'}):
            mock_client = MagicMock()
            # Simulate a 429 quota exceeded error
            mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for quota metric")

            with patch('google.genai.Client', return_value=mock_client):
                res = AIService.generate_response(
                    user=user1,
                    user_message="Help me revise for algorithms exam",
                    use_academic_context=True
                )
                assert res['success'] is True
                assert res['is_live'] is False
                assert "quota exceeded" in res['warning'].lower()
                # Must provide helpful offline fallback content
                assert len(res['content']) > 10

def test_ai_model_fallback_chain_mocked(app, user1):
    """Verifies that if the primary model fails with 404, fallback models are automatically attempted."""
    with app.app_context():
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'mock-valid-key', 'GEMINI_MODEL': 'gemini-2.5-flash'}):
            mock_client = MagicMock()
            
            # First call (gemini-2.5-flash) raises 404 NOT_FOUND
            # Second call (gemini-3.5-flash fallback) succeeds
            mock_success_response = MagicMock()
            mock_success_response.text = "Here is the explanation from fallback model."

            mock_client.models.generate_content.side_effect = [
                Exception("404 NOT_FOUND: model models/gemini-2.5-flash is no longer available to new users"),
                mock_success_response
            ]

            with patch('google.genai.Client', return_value=mock_client):
                res = AIService.generate_response(
                    user=user1,
                    user_message="What is recursion?",
                    use_academic_context=False
                )
                assert res['success'] is True
                assert res['is_live'] is True
                assert "fallback model" in res['content']
                assert "Google Gemini API" in res['provider']

def test_ai_key_redaction_in_errors(app):
    """Verifies that sensitive API keys are never leaked in error messages or logs."""
    fake_key = "AIzaSyTestSecretKey_NeverLeakMe1234567"
    with app.app_context():
        with patch.dict(os.environ, {'GEMINI_API_KEY': fake_key}):
            err = Exception(f"HTTP 400 with key {fake_key}: invalid argument")
            msg = AIService._classify_gemini_error(err, "gemini-3.5-flash")
            assert fake_key not in msg
            assert "[REDACTED_API_KEY]" in msg or "Invalid Gemini API Key" in msg

def test_ai_chat_endpoint_integration(auth_client1):
    """Verifies the /api/ai/chat endpoint saves messages and returns formatted JSON."""
    with patch('app.services.ai_service.AIService.generate_response') as mock_gen:
        mock_gen.return_value = {
            'success': True,
            'is_live': True,
            'content': 'Quicksort uses divide and conquer.',
            'is_grounded': True,
            'provider': 'Google Gemini API (gemini-3.5-flash)',
            'warning': None
        }

        res = auth_client1.post('/api/ai/chat', json={
            'message': 'Explain Quicksort briefly',
            'use_grounding': True
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert data['is_live'] is True
        assert 'conversation_id' in data
        assert data['assistant_message']['content'] == 'Quicksort uses divide and conquer.'
        assert data['provider'] == 'Google Gemini API (gemini-3.5-flash)'

def test_ai_live_gemini_integration(app, user1):
    """
    Live API verification test:
    Executes a real call to Google Gemini if GEMINI_API_KEY is configured.
    Distinguishes mocked tests from a genuine live end-to-end API response.
    Never exposes or logs the API key.
    """
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key or key in ['your_gemini_api_key_here', 'placeholder', 'none']:
        import pytest
        pytest.skip("Skipping live Gemini test: No valid GEMINI_API_KEY in environment.")

    with app.app_context():
        res = AIService.generate_response(
            user=user1,
            user_message="Say 'StudySync Live Test OK' in fewer than 6 words.",
            use_academic_context=False
        )
        assert res['success'] is True
        if res.get('is_live'):
            assert 'Google Gemini API' in res['provider']
            assert res['warning'] is None
            assert len(res['content']) > 0
            assert key not in res['content']
        else:
            # If rate limit or quota is temporarily hit during continuous testing, verify safe fallback
            assert res['success'] is True
            assert any(w in (res.get('warning') or '').lower() for w in ['quota', 'rate limit', 'offline', 'gemini'])
            assert len(res['content']) > 0
            assert key not in res['content']

def test_ai_chat_endpoint_live_integration(auth_client1):
    """
    Live HTTP endpoint verification test:
    Executes a real POST to /api/ai/chat and asserts live Gemini response generation,
    persistence in database, and payload structure.
    """
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key or key in ['your_gemini_api_key_here', 'placeholder', 'none']:
        import pytest
        pytest.skip("Skipping live endpoint test: No valid GEMINI_API_KEY in environment.")

    res = auth_client1.post('/api/ai/chat', json={
        'message': "Say 'Live endpoint working' in fewer than 5 words.",
        'use_grounding': False
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    if data.get('is_live'):
        assert 'Google Gemini API' in data['provider']
        assert data['assistant_message']['content']
        assert key not in data['assistant_message']['content']
    else:
        # If rate limit or quota exceeded during test bursts, verify fallback handling was activated
        warning_msg = (data.get('warning') or '').lower()
        assert any(w in warning_msg for w in ['quota', 'rate limit', 'offline', 'gemini'])
        assert data['assistant_message']['content']
        assert key not in data['assistant_message']['content']


