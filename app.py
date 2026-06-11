"""
嵇康智能体 — Web 版 Flask 后端
支持 SSE 流式输出、会话管理、日志记录、Redis 分布式存储
"""

import asyncio
import json
import os
import time
import uuid

from flask import Flask, request, jsonify, Response, render_template

from jikang_core import JiKangSession
from session_store import create_store, SessionStore

app = Flask(__name__)

# ── 会话存储 ──
# 从环境变量读取 Redis 配置，未配置则自动降级为内存存储
REDIS_URL = os.environ.get("REDIS_URL")
_store: SessionStore = create_store(REDIS_URL)

# 本地内存缓存：减少 Redis 反序列化开销（热 session 保留）
_local_cache: dict[str, JiKangSession] = {}
LOCAL_CACHE_TTL_SECONDS = 300  # 本地缓存 5 分钟
_local_cache_time: dict[str, float] = {}

SESSION_TTL_SECONDS = 30 * 60  # Redis / 内存 TTL: 30 分钟


def _get_session(session_id: str) -> JiKangSession | None:
    """获取会话：先查本地缓存，再查持久化存储"""
    now = time.time()

    # 1. 本地缓存命中且未过期
    if session_id in _local_cache:
        if now - _local_cache_time.get(session_id, 0) < LOCAL_CACHE_TTL_SECONDS:
            return _local_cache[session_id]
        else:
            del _local_cache[session_id]
            _local_cache_time.pop(session_id, None)

    # 2. 从持久化存储恢复
    data = _store.get(session_id)
    if data is None:
        return None

    session = JiKangSession.from_dict(data)

    # 3. 写入本地缓存
    _local_cache[session_id] = session
    _local_cache_time[session_id] = now

    return session


def _save_session(session_id: str, session: JiKangSession) -> None:
    """保存会话到持久化存储和本地缓存"""
    _store.set(session_id, session.to_dict(), SESSION_TTL_SECONDS)
    _local_cache[session_id] = session
    _local_cache_time[session_id] = time.time()


def _delete_session(session_id: str) -> None:
    """删除会话"""
    _store.delete(session_id)
    _local_cache.pop(session_id, None)
    _local_cache_time.pop(session_id, None)


def _get_or_create_event_loop():
    """获取当前线程的事件循环，如不存在则创建"""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


# ── 路由 ──

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/init", methods=["POST"])
def api_init():
    """初始化新会话"""
    data = request.get_json(force=True) or {}
    mode = data.get("mode")
    identity = data.get("identity") or None
    qna_subtype = data.get("subtype") or data.get("qna_subtype") or None
    heart_voice = bool(data.get("heart_voice", False))

    # 前端中文值 → 后端英文值映射
    mode_map = {"xingqing": "personality", "wenda": "qna"}
    identity_map = {"好友": "friend", "仇敌": "enemy", "陌生人": "stranger"}
    subtype_map = {"原始版": "original", "深度版": "frontier"}

    mode = mode_map.get(mode, mode)
    identity = identity_map.get(identity, identity)
    qna_subtype = subtype_map.get(qna_subtype, qna_subtype)

    if mode not in ("personality", "qna"):
        return jsonify({"error": "无效的 mode，请选择 personality 或 qna"}), 400

    session_id = str(uuid.uuid4())

    session = JiKangSession(
        mode=mode,
        identity=identity,
        qna_subtype=qna_subtype,
        heart_voice=heart_voice,
    )

    _save_session(session_id, session)

    # 返回会话配置信息
    mode_name_cn = "性情版" if mode == "personality" else "问答版"
    identity_name_cn = {
        "friend": "好友",
        "enemy": "仇敌",
        "stranger": "陌生人",
    }.get(identity, "")
    qna_subtype_name_cn = {
        "original": "原始版",
        "frontier": "深度版",
    }.get(qna_subtype, "")

    return jsonify({
        "session_id": session_id,
        "mode": mode,
        "mode_name_cn": mode_name_cn,
        "identity": identity,
        "identity_name_cn": identity_name_cn,
        "qna_subtype": qna_subtype,
        "qna_subtype_name_cn": qna_subtype_name_cn,
        "heart_voice": heart_voice,
        "scene": "bamboo",
        "scene_name": "竹林",
    })


@app.route("/api/resume_session", methods=["POST"])
def api_resume_session():
    """根据历史记录配置和消息，创建新会话并导入历史消息，实现'继续对话'"""
    data = request.get_json(force=True) or {}
    mode = data.get("mode")
    identity = data.get("identity") or None
    qna_subtype = data.get("qna_subtype") or data.get("subtype") or None
    heart_voice = bool(data.get("heart_voice", False))
    messages = data.get("messages", [])

    # 前端中文值 → 后端英文值映射
    mode_map = {"xingqing": "personality", "wenda": "qna"}
    identity_map = {"好友": "friend", "仇敌": "enemy", "陌生人": "stranger"}
    subtype_map = {"原始版": "original", "深度版": "frontier"}

    mode = mode_map.get(mode, mode)
    identity = identity_map.get(identity, identity)
    qna_subtype = subtype_map.get(qna_subtype, qna_subtype)

    if mode not in ("personality", "qna"):
        return jsonify({"error": "无效的 mode，请选择 personality 或 qna"}), 400

    session_id = str(uuid.uuid4())

    session = JiKangSession(
        mode=mode,
        identity=identity,
        qna_subtype=qna_subtype,
        heart_voice=heart_voice,
    )

    # 导入历史消息
    imported_count = 0
    if isinstance(messages, list) and len(messages) > 0:
        imported_count = session.import_messages(messages)

    _save_session(session_id, session)

    # 返回会话配置信息
    mode_name_cn = "性情版" if mode == "personality" else "问答版"
    identity_name_cn = {
        "friend": "好友",
        "enemy": "仇敌",
        "stranger": "陌生人",
    }.get(identity, "")
    qna_subtype_name_cn = {
        "original": "原始版",
        "frontier": "深度版",
    }.get(qna_subtype, "")

    return jsonify({
        "session_id": session_id,
        "mode": mode,
        "mode_name_cn": mode_name_cn,
        "identity": identity,
        "identity_name_cn": identity_name_cn,
        "qna_subtype": qna_subtype,
        "qna_subtype_name_cn": qna_subtype_name_cn,
        "heart_voice": heart_voice,
        "scene": "bamboo",
        "scene_name": "竹林",
        "imported_count": imported_count,
    })


@app.route("/api/config", methods=["GET"])
def api_config():
    """获取当前会话配置"""
    session_id = request.args.get("session_id")
    session = _get_session(session_id) if session_id else None
    if session is None:
        return jsonify({"error": "会话不存在或已过期"}), 404

    # 刷新 TTL
    _store.touch(session_id, SESSION_TTL_SECONDS)

    mode_name_cn = "性情版" if session.mode == "personality" else "问答版"
    identity_name_cn = {
        "friend": "好友",
        "enemy": "仇敌",
        "stranger": "陌生人",
    }.get(session.identity, "")
    qna_subtype_name_cn = {
        "original": "原始版",
        "frontier": "深度版",
    }.get(session.qna_subtype, "")
    scene_name = {
        "bamboo": "竹林",
        "prison": "狱中",
        "death": "临刑前",
    }.get(session.scene, "竹林")

    return jsonify({
        "mode": session.mode,
        "mode_name_cn": mode_name_cn,
        "identity": session.identity,
        "identity_name_cn": identity_name_cn,
        "qna_subtype": session.qna_subtype,
        "qna_subtype_name_cn": qna_subtype_name_cn,
        "heart_voice": session.heart_voice,
        "scene": session.scene,
        "scene_name": scene_name,
    })


@app.route("/chat/stream", methods=["GET", "POST"])
def chat_stream():
    """SSE 流式对话端点（支持 GET 和 POST）"""
    if request.method == "POST":
        data = request.get_json(force=True) or {}
    else:
        data = request.args
    session_id = data.get("session_id")
    user_input = (data.get("user_input") or "").strip()

    session = _get_session(session_id) if session_id else None
    if session is None:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'text': '会话不存在或已过期，请重新开始对话'}, ensure_ascii=False)}\n\n"
        return Response(error_gen(), mimetype="text/event-stream")

    if not user_input:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'text': '输入不能为空'}, ensure_ascii=False)}\n\n"
        return Response(error_gen(), mimetype="text/event-stream")

    def generate_sse():
        """同步生成器，包装异步 chat()"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def async_chat():
            async for event in session.chat(user_input):
                yield event

        try:
            gen = async_chat()
            while True:
                try:
                    event = loop.run_until_complete(gen.__anext__())
                    event_type = event.get("type", "message")
                    data_line = f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                    yield data_line
                except StopAsyncIteration:
                    break
        except Exception as e:
            error_event = {"type": "error", "text": f"[服务端异常: {type(e).__name__}: {e}]"}
            yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        finally:
            loop.close()
            # 持久化更新后的会话状态（messages 已被 chat() 修改）
            _save_session(session_id, session)

    return Response(
        generate_sse(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


@app.route("/api/history", methods=["GET"])
def api_history():
    """获取当前会话的历史记录（不含 system prompt）"""
    session_id = request.args.get("session_id")
    session = _get_session(session_id) if session_id else None
    if session is None:
        return jsonify({"error": "会话不存在或已过期"}), 404

    # 刷新 TTL
    _store.touch(session_id, SESSION_TTL_SECONDS)

    # 过滤掉 system prompt，只返回对话内容
    history = [msg for msg in session.messages if msg.get("role") != "system"]
    return jsonify({"history": history})


@app.route("/api/import_history", methods=["POST"])
def api_import_history():
    """将历史对话消息导入当前会话，使嵇康能看到引用的历史上下文"""
    data = request.get_json(force=True) or {}
    session_id = data.get("session_id")
    messages = data.get("messages", [])

    session = _get_session(session_id) if session_id else None
    if session is None:
        return jsonify({"error": "会话不存在或已过期"}), 404

    if not isinstance(messages, list) or len(messages) == 0:
        return jsonify({"error": "消息列表为空"}), 400

    # 导入消息到会话
    count = session.import_messages(messages)

    # 持久化更新
    _save_session(session_id, session)

    return jsonify({
        "success": True,
        "imported": count,
        "session_id": session_id,
    })


# ── 启动入口 ──

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  嵇康智能体 Web 版")
    print(f"  访问地址: http://localhost:{port}")
    print("=" * 50)
    # threaded=True 支持并发 SSE 连接
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
