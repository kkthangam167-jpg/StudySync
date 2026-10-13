import time
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from app import db
from app.models import ChatConversation, ChatMessage
from app.services.ai_service import AIService

ai_bp = Blueprint('ai', __name__)

MAX_MESSAGE_LENGTH = 2000
RATE_LIMIT_SECONDS = 1.0  # Minimum delay between messages per user session

@ai_bp.route('/ai-assistant')
@login_required
def index():
    user_id = current_user.id
    conversations = ChatConversation.query.filter_by(user_id=user_id).order_by(ChatConversation.updated_at.desc()).all()

    # Active conversation
    active_id = request.args.get('conversation_id')
    active_conversation = None
    if active_id and active_id.isdigit():
        active_conversation = ChatConversation.query.filter_by(id=int(active_id), user_id=user_id).first()

    # If no conversation active, pick the newest or create one
    if not active_conversation and conversations:
        active_conversation = conversations[0]

    messages = []
    if active_conversation:
        messages = active_conversation.messages.all()

    is_ai_configured = AIService.is_configured()
    model_name = AIService.get_model_name()

    return render_template(
        'ai/index.html',
        conversations=conversations,
        active_conversation=active_conversation,
        messages=messages,
        is_ai_configured=is_ai_configured,
        model_name=model_name
    )


@ai_bp.route('/api/ai/conversations', methods=['POST'])
@login_required
def create_conversation():
    data = request.get_json(silent=True) or {}
    title = data.get('title', 'New Study Session').strip() if isinstance(data, dict) else 'New Study Session'
    if not title or len(title) > 100:
        title = 'New Study Session'

    conv = ChatConversation(user_id=current_user.id, title=title)
    db.session.add(conv)
    db.session.commit()
    return jsonify({'success': True, 'conversation': conv.to_dict()})


@ai_bp.route('/api/ai/conversations/<int:conv_id>/delete', methods=['POST'])
@login_required
def delete_conversation(conv_id):
    conv = ChatConversation.query.filter_by(id=conv_id, user_id=current_user.id).first_or_404()
    db.session.delete(conv)
    db.session.commit()
    return jsonify({'success': True})


@ai_bp.route('/api/ai/chat', methods=['POST'])
@login_required
def send_message():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid request format. JSON body required.'}), 400

    user_message = data.get('message', '')
    if not isinstance(user_message, str):
        return jsonify({'error': 'Message must be text.'}), 400

    user_message = user_message.strip()
    if not user_message:
        return jsonify({'error': 'Message cannot be empty.'}), 400

    if len(user_message) > MAX_MESSAGE_LENGTH:
        return jsonify({
            'error': f'Message exceeds maximum limit of {MAX_MESSAGE_LENGTH} characters (current: {len(user_message)}).'
        }), 400

    # Rate limiting burst check
    now_ts = time.time()
    last_req_ts = session.get('last_ai_request_ts', 0)
    if now_ts - last_req_ts < RATE_LIMIT_SECONDS:
        return jsonify({'error': 'Please wait a moment before sending another message.'}), 429
    session['last_ai_request_ts'] = now_ts

    conv_id = data.get('conversation_id')
    use_grounding = bool(data.get('use_grounding', True))

    # Retrieve or create conversation
    conv = None
    if conv_id and str(conv_id).isdigit():
        conv = ChatConversation.query.filter_by(id=int(conv_id), user_id=current_user.id).first()

    if not conv:
        # Generate initial title from first few words
        words = user_message.split()
        title_snippet = " ".join(words[:5]) if words else "Study Session"
        conv = ChatConversation(user_id=current_user.id, title=title_snippet[:40])
        db.session.add(conv)
        db.session.flush()

    # Save User message
    user_msg_record = ChatMessage(
        conversation_id=conv.id,
        sender='user',
        content=user_message,
        is_grounded=use_grounding
    )
    db.session.add(user_msg_record)

    # Gather past messages for multi-turn conversational context
    history_records = conv.messages.order_by(ChatMessage.created_at.desc()).limit(8).all()
    history = [{'sender': m.sender, 'content': m.content} for m in reversed(history_records)]

    # Generate response via AIService
    ai_result = AIService.generate_response(
        user=current_user,
        user_message=user_message,
        conversation_history=history,
        use_academic_context=use_grounding
    )

    assistant_msg_record = ChatMessage(
        conversation_id=conv.id,
        sender='assistant',
        content=ai_result['content'],
        is_grounded=ai_result.get('is_grounded', False)
    )
    db.session.add(assistant_msg_record)
    conv.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'success': True,
        'conversation_id': conv.id,
        'is_live': ai_result.get('is_live', False),
        'provider': ai_result.get('provider'),
        'user_message': user_msg_record.to_dict(),
        'assistant_message': assistant_msg_record.to_dict(),
        'warning': ai_result.get('warning')
    })
