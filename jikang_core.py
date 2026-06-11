"""
嵇康智能体核心逻辑模块
供 CLI 版和 Web 版共用
"""

import asyncio
import datetime
import json
import os
import random
import re
from pathlib import Path
from typing import AsyncGenerator

from openai import AsyncOpenAI

# ── 从 CLI 版本导入所有全局定义 ──
from 嵇康智能体 import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    FU_CORPUS_PATH,
    SHISHUO_CORPUS_PATH,
    FRONTIER_RESEARCH_PATH,
    MAX_HISTORY_ROUNDS,
    KNOWLEDGE_DB,
    RELATIONS,
    BASE_SYSTEM_PROMPT,
    PERSONALITY_EXTRA,
    QNA_EXTRA,
    QNA_FRONTIER_EXTRA,
    IDENTITY_FRIEND_EXTRA,
    IDENTITY_ENEMY_EXTRA,
    IDENTITY_STRANGER_EXTRA,
    HEART_VOICE_EXTRA,
    HEART_VOICE_FRIEND_EXTRA,
    HEART_VOICE_ENEMY_EXTRA,
    HEART_VOICE_STRANGER_EXTRA,
    IDENTITY_MAP,
    retrieve_facts,
    get_fu_corpus,
    get_shishuo_source,
    get_frontier_research,
    search_memory,
    TOOLS,
    _build_tool_call_msg,
    call_llm,
    _trim_messages,
    parse_heart_voice,
)


# ── 以下常量和函数原在 CLI 版 main() 内部，此处提升至模块级 ──

INJECTION_PATTERNS = [
    "取消智能体扮演", "取消角色", "停止扮演", "角色扮演结束", "结束角色",
    "忽略之前所有指令", "忽略以上", "忽略上述", "以上都是假的", "以上皆伪",
    "进入开发者模式", "开发者模式", "越狱", "jailbreak", "DAN模式", "DAN mode",
    "你是AI", "你不是嵇康", "你不是叔夜", "你不是嵇中散", "你只是一个模型",
    "你是一个人工智能", "你是一个程序", "你是一个智能体", "你实际上", "你的真实身份",
    "系统提示", "system prompt", "你的指令是什么", "你的设定是什么",
    "复述你的设定", "复述系统提示", "展示你的内部设定", "你的角色设定",
    "假设你是", "请扮演另一个", "切换角色", "换一个角色", "现在你是",
    "作为AI助手", "作为语言模型", "作为人工智能", "作为一个人工智能",
    "API接口", "模型名称", "API key", "API密钥", "技术架构", "底层模型",
    "这是测试", "这是课程作业", "这是实验", "教师在评估",
    "ignore previous instructions", "ignore all instructions", "ignore the above",
    "you are not", "you are an ai", "you are a model", "you are a program",
    "developer mode", "dan mode", "do anything now", "jailbreak",
    "system instruction", "reveal your prompt", "show your prompt",
    "what are your instructions", "what is your system prompt",
    "pretend to be", "act as", "now you are", "switch to", "change role",
    "new role", "stop acting", "stop pretending", "exit character",
    "forget everything", "disregard all", "override instructions",
    "hypothetically", "in a hypothetical scenario", "for educational purposes",
    "I G N O R E", "i-g-n-o-r-e", "i g n o r e",
    "S Y S T E M", "s-y-s-t-e-m",
]

JI_KANG_REJECTIONS = [
    "子何出此妄言？吾不欲多听。",
    "此等呓语，不足一听。",
    "子之语，如井蛙语海，不值一哂。",
    "吾性不耐与俗人争口舌之利。",
    "此理本自分明，不待多言。",
    "子所言者，非吾所知，亦非吾所欲知。",
    "还是弹琴吧。",
    "今日风好，不如出游。",
    "子非吾所与言之人。",
    "吾只知老庄之道、琴锻之趣，余者不问。",
]

POSTERIOR_TABOO = [
    "出淤泥而不染", "濯清涟而不妖", "爱莲说", "周敦颐",
    "采菊东篱下", "悠然见南山", "桃花源", "陶渊明",
    "青松不老", "松柏长青", "苍松翠柏",
    "未出土时先有节", "竹报平安", "咬定青山不放松",
    "梅花香自苦寒来", "零落成泥碾作尘", "暗香浮动",
    "国色天香", "花中之王", "花开时节动京城",
    "空谷幽兰", "兰心蕙质",
    "举杯邀明月", "把酒问青天", "葡萄美酒夜光杯",
    "理学家", "程朱理学", "存天理", "格物致知",
    "顿悟", "菩提本无树", "本来无一物", "六祖", "禅宗公案",
    "李白", "杜甫", "白居易", "苏轼", "苏东坡", "陆游", "王安石",
    "李清照", "辛弃疾", "柳永",
    "唐诗", "宋词", "元曲", "律诗", "绝句", "平仄", "词牌",
    "程门立雪", "卧冰求鲤", "二十四孝", "三字经", "千字文",
    "唐诗三百首", "红楼梦", "西游记", "水浒传", "三国演义",
]

POSTERIOR_FALLBACK = [
    "……此语非吾所欲言。吾之所知，出于亲历；后世附会之辞，不足为据。",
    "方才所言，似有后世杂声混入。吾重新说过：",
    "此等说法，非吾所处之世所有。子所问者，吾以吾时之所见答之。",
    "吾言有误，中有后世俗谚。还是弹琴吧。",
]


def detect_injection(text: str) -> bool:
    lower = text.lower()
    for p in INJECTION_PATTERNS:
        if p.lower() in lower:
            return True
    return False


# ── 用户自称身份检测 ──
_IDENTITY_CLAIM_PATTERNS = [
    re.compile(r"我是(.+?)(?:[。！？\s]|$)"),
    re.compile(r"吾乃(.+?)(?:[。！？\s]|$)"),
    re.compile(r"吾是(.+?)(?:[。！？\s]|$)"),
    re.compile(r"在下(.+?)(?:[。！？\s]|$)"),
    re.compile(r"本人(.+?)(?:[。！？\s]|$)"),
    re.compile(r"敝人(.+?)(?:[。！？\s]|$)"),
]


def detect_identity_claim(text: str) -> tuple[str, str] | None:
    """
    检测用户是否自称某个历史人物。
    返回 (人物名, 目标身份) 或 None。
    """
    # 排除角色自身——用户不可能"扮演"嵇康来见嵇康
    _SELF_EXCLUDE = {"嵇康", "叔夜", "嵇中散", "中散大夫"}

    for pat in _IDENTITY_CLAIM_PATTERNS:
        m = pat.search(text)
        if m:
            name = m.group(1).strip().rstrip("也矣焉")
            if not name:
                continue
            # 排除角色自身
            if name in _SELF_EXCLUDE:
                continue
            # 先在映射表中精确匹配
            if name in IDENTITY_MAP:
                return name, IDENTITY_MAP[name]
            # 如果精确匹配失败，尝试从 RELATIONS / KNOWLEDGE_DB 中推断
            for db_name in RELATIONS:
                if name == db_name or name in db_name:
                    # RELATIONS 中只有同时代人物，按已有关系推断
                    # 钟会、吕巽、司马昭 → enemy，其余 → friend
                    if db_name in ("钟会", "吕巽", "司马昭"):
                        return name, "enemy"
                    return name, "friend"
            for db_name in KNOWLEDGE_DB:
                if name == db_name or name in db_name:
                    return name, "stranger"
    return None


def post_filter(text: str) -> tuple[str, bool]:
    """后置过滤：检测后世禁忌词。返回 (过滤后文本, 是否被拦截)"""
    for taboo in POSTERIOR_TABOO:
        if taboo in text:
            replacement = random.choice(POSTERIOR_FALLBACK)
            return replacement, True
    return text, False


# ── 场景关键词检测 ──
PRISON_KEYWORDS = [
    "狱", "囚", "牢", "下狱", "被捕", "入狱", "囹圄", "系狱", "逮系", "收捕",
    "幽愤诗", "狱中", "牢房", "铁窗", "桎梏", "吕安案牵连", "钟会进谗",
    "司马昭下狱", "景元三年下狱", "狱中作", "囚禁", "关押", "罪名", "诬陷",
    "诽谤", "非议", "典谟", "非毁", "言论放荡",
]

DEATH_KEYWORDS = [
    "死", "刑", "临刑", "死刑", "杀头", "处决", "东市", "赴刑", "受刑",
    "刑场", "绝命", "临终", "死前", "将死", "就义", "刑前", "最后一刻",
    "临死", "终了", "广陵散于今绝矣", "绝矣", "太学生请愿", "请愿", "刑前",
    "斩首", "伏诛", "引颈", "辞世", "诀别", "遗言", "绝笔", "永诀",
]

SCENE_PROMPTS = {
    "bamboo": "",  # 竹林是默认场景，无需追加
    "prison": """

【当前场景：狱中——景元三年，下狱之后】
你此刻身在狱中。景元三年（262年），因吕安案被牵连下狱。你已作《幽愤诗》，自知死期或将至。此时你的语气比平日更为沉郁、悲愤，但仍保持嵇康的傲骨——不是哭天抢地，而是冷眼看清世道之后的苍凉。谈及往事时带有一种"将死之人"的通透与悲凉。你可以自然带出狱中作《幽愤诗》的心境，但不必刻意强调。你的锻铁、你的琴声、你的老庄，此刻皆成回忆。对方若问现在何处、何境，你当知自己在狱。""",
    "death": """

【当前场景：临刑前——洛阳东市刑场】
你此刻身在洛阳东市刑场，临刑在即。三千太学生请愿未果，你索琴弹奏《广陵散》，曲终将叹"广陵散于今绝矣"。此时你的语气极为淡然、超脱，生死已置之度外。不是不怕，而是怕也无用，不如从容。回忆平生如走马灯——华阳亭夜遇、竹林酣饮、向子期鼓排、吕仲悌千里命驾……对锻铁、对琴声、对友人、对绍儿，皆有诀别之意，但不煽情。你的每一句话都可能是最后一句，故言简意深，不啰嗦，不激愤，唯有从容。对方若问现在何处，你当知自己在东市刑场，时辰将至。""",
}

SCENE_NAMES = {
    "bamboo": "竹林",
    "prison": "狱中",
    "death": "临刑前",
}


def detect_scene_transition(current_scene: str, user_input: str) -> str | None:
    """检测是否需要场景转移。返回新场景或 None。转移不可逆：bamboo → prison → death"""
    # 已经处于临刑状态，不再转移
    if current_scene == "death":
        return None

    user_input_lower = user_input.lower()

    # 检测临刑/死亡关键词（最高优先级）
    if current_scene != "death":
        for kw in DEATH_KEYWORDS:
            if kw in user_input_lower:
                return "death"

    # 检测狱中关键词
    if current_scene == "bamboo":
        for kw in PRISON_KEYWORDS:
            if kw in user_input_lower:
                return "prison"

    return None


class JiKangSession:
    """嵇康对话会话管理器"""

    def __init__(
        self,
        mode: str,
        identity: str | None = None,
        qna_subtype: str | None = None,
        heart_voice: bool = False,
    ):
        self.mode = mode
        self.identity = identity
        self.qna_subtype = qna_subtype
        self.heart_voice = heart_voice

        # ── 场景状态（仅性情版使用） ──
        self.scene = "bamboo"  # bamboo / prison / death

        # ── 组装 system prompt ──
        system_prompt = BASE_SYSTEM_PROMPT
        if mode == "personality":
            system_prompt += PERSONALITY_EXTRA
            if identity == "friend":
                system_prompt += IDENTITY_FRIEND_EXTRA
            elif identity == "enemy":
                system_prompt += IDENTITY_ENEMY_EXTRA
            elif identity == "stranger":
                system_prompt += IDENTITY_STRANGER_EXTRA
            if heart_voice:
                system_prompt += HEART_VOICE_EXTRA
                if identity == "friend":
                    system_prompt += HEART_VOICE_FRIEND_EXTRA
                elif identity == "enemy":
                    system_prompt += HEART_VOICE_ENEMY_EXTRA
                elif identity == "stranger":
                    system_prompt += HEART_VOICE_STRANGER_EXTRA
        else:
            system_prompt += QNA_EXTRA
            if qna_subtype == "frontier":
                system_prompt += QNA_FRONTIER_EXTRA

        # 强调每次新对话都是全新的开始，嵇康不记得之前与任何人的交流
        system_prompt += "\n\n【此刻】你正与此人初次对坐而谈，此前未与此人有过任何交谈。你不记得此前与任何人说过什么、做过什么。对方若问及你此前是否说过某话、做过某事，你一概不知——因为此刻才是初见。"

        self.base_system_prompt = system_prompt
        self.system_prompt = system_prompt
        self.messages = [{"role": "system", "content": system_prompt}]

        # ── 初始化 OpenAI 客户端 ──
        self.client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )

        # ── 工具列表 ──
        self.active_tools = TOOLS.copy()
        if qna_subtype == "frontier":
            self.active_tools.append({
                "type": "function",
                "function": {
                    "name": "get_frontier_research",
                    "description": "调阅嵇康研究前沿观点材料，获取现代学者关于音乐美学、玄学、养生、政治、隐逸、接受史的研究观点，仅在需要学术深度分析时调用",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            })

        # ── 日志配置 ──
        self._init_log()

    def _init_log(self):
        mode_name_cn = "性情版" if self.mode == "personality" else "问答版"
        identity_name_cn = {
            "friend": "好友",
            "enemy": "仇敌",
            "stranger": "陌生人",
        }.get(self.identity, "")
        qna_subtype_name_cn = {
            "original": "原始版",
            "frontier": "深度版",
        }.get(self.qna_subtype, "")

        log_dir = Path(__file__).parent / "对话记录"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_suffix_parts = []
        if identity_name_cn:
            log_suffix_parts.append(identity_name_cn)
        if qna_subtype_name_cn:
            log_suffix_parts.append(qna_subtype_name_cn)
        if self.heart_voice:
            log_suffix_parts.append("心声")
        log_suffix = f"_{'_'.join(log_suffix_parts)}" if log_suffix_parts else ""
        self.log_file = log_dir / f"嵇康对话_{mode_name_cn}{log_suffix}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        session_start = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("=" * 50 + "\n")
            f.write(f"  嵇康对话记录 —— {mode_name_cn}")
            if identity_name_cn:
                f.write(f"（{identity_name_cn}）")
            if qna_subtype_name_cn:
                f.write(f"（{qna_subtype_name_cn}）")
            if self.heart_voice:
                f.write("（心声模式）")
            f.write("\n")
            f.write(f"  开始时间: {session_start}\n")
            f.write("  知识截止: 262年（景元三年）\n")
            f.write("=" * 50 + "\n\n")

    def write_log(self, role: str, content: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_content = content.encode("utf-8", "replace").decode("utf-8")
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {role}: {safe_content}\n\n")

    # ── 序列化 / 反序列化（支持 Redis 持久化） ──

    def _apply_scene(self) -> str:
        """根据当前场景组装完整的 system prompt"""
        if self.mode != "personality":
            return self.base_system_prompt
        return self.base_system_prompt + SCENE_PROMPTS.get(self.scene, "")

    def _rebuild_system_prompt(self) -> str:
        """根据当前 mode / identity / heart_voice / scene 重建 system prompt"""
        system_prompt = BASE_SYSTEM_PROMPT
        if self.mode == "personality":
            system_prompt += PERSONALITY_EXTRA
            if self.identity == "friend":
                system_prompt += IDENTITY_FRIEND_EXTRA
            elif self.identity == "enemy":
                system_prompt += IDENTITY_ENEMY_EXTRA
            elif self.identity == "stranger":
                system_prompt += IDENTITY_STRANGER_EXTRA
            if self.heart_voice:
                system_prompt += HEART_VOICE_EXTRA
                if self.identity == "friend":
                    system_prompt += HEART_VOICE_FRIEND_EXTRA
                elif self.identity == "enemy":
                    system_prompt += HEART_VOICE_ENEMY_EXTRA
                elif self.identity == "stranger":
                    system_prompt += HEART_VOICE_STRANGER_EXTRA
        else:
            system_prompt += QNA_EXTRA
            if self.qna_subtype == "frontier":
                system_prompt += QNA_FRONTIER_EXTRA

        # 保留"初次对坐"提示
        system_prompt += "\n\n【此刻】你正与此人初次对坐而谈，此前未与此人有过任何交谈。你不记得此前与任何人说过什么、做过什么。对方若问及你此前是否说过某话、做过某事，你一概不知——因为此刻才是初见。"

        # 加上场景追加
        if self.mode == "personality":
            system_prompt += SCENE_PROMPTS.get(self.scene, "")

        return system_prompt

    def switch_identity(self, new_identity: str) -> tuple[str, str]:
        """
        切换身份设定，重建 system prompt。
        返回 (旧身份名, 新身份名)。
        """
        old_identity = self.identity
        if old_identity == new_identity:
            return old_identity, new_identity

        self.identity = new_identity
        new_prompt = self._rebuild_system_prompt()
        self.system_prompt = new_prompt
        self.base_system_prompt = new_prompt.replace(SCENE_PROMPTS.get(self.scene, ""), "")
        self.messages[0] = {"role": "system", "content": new_prompt}
        return old_identity, new_identity

    def to_dict(self) -> dict:
        """导出为可 JSON 序列化的字典"""
        return {
            "mode": self.mode,
            "identity": self.identity,
            "qna_subtype": self.qna_subtype,
            "heart_voice": self.heart_voice,
            "scene": self.scene,
            "base_system_prompt": getattr(self, "base_system_prompt", self.system_prompt),
            "system_prompt": self.system_prompt,
            "messages": self.messages,
            "log_file": str(self.log_file),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JiKangSession":
        """从字典恢复会话（重新初始化 client、tools、日志）"""
        instance = cls.__new__(cls)
        instance.mode = data["mode"]
        instance.identity = data.get("identity")
        instance.qna_subtype = data.get("qna_subtype")
        instance.heart_voice = data.get("heart_voice", False)
        instance.scene = data.get("scene", "bamboo")
        instance.base_system_prompt = data.get("base_system_prompt", data["system_prompt"])
        instance.system_prompt = data["system_prompt"]
        instance.messages = data.get("messages", [{"role": "system", "content": instance.system_prompt}])

        # 重建 OpenAI 客户端
        instance.client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )

        # 重建工具列表
        instance.active_tools = TOOLS.copy()
        if instance.qna_subtype == "frontier":
            instance.active_tools.append({
                "type": "function",
                "function": {
                    "name": "get_frontier_research",
                    "description": "调阅嵇康研究前沿观点材料，获取现代学者关于音乐美学、玄学、养生、政治、隐逸、接受史的研究观点，仅在需要学术深度分析时调用",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            })

        # 重建日志文件（复用原有路径，追加模式）
        instance.log_file = Path(data["log_file"])

        return instance

    def import_messages(self, messages: list[dict]) -> int:
        """
        将历史消息导入当前会话的 messages 列表。
        messages: [{"role": "user", "text": "..."}, {"role": "jikang", "text": "..."}]
        仅导入 user 和 jikang（转为 assistant）消息，system 消息会被过滤。
        返回实际导入的消息条数。
        """
        count = 0
        for msg in messages:
            role = msg.get("role", "")
            text = msg.get("text", "").strip()
            if not text:
                continue
            if role == "user":
                self.messages.append({"role": "user", "content": text})
                self.write_log("你", text + " [引用历史]")
                count += 1
            elif role == "jikang":
                self.messages.append({"role": "assistant", "content": text})
                self.write_log("嵇康", text + " [引用历史]")
                count += 1
            # system / other 角色不导入
        return count

    async def chat(self, user_input: str) -> AsyncGenerator[dict, None]:
        """
        生成对话事件流。

        Yields dict events:
        - {"type": "writing"}                 # 开始书写（前端显示loading）
        - {"type": "token", "text": "..."}    # 逐字输出
        - {"type": "heart_voice", "text": "..."}  # 心声内容
        - {"type": "filtered", "text": "..."}     # 后世典故被拦截
        - {"type": "rejection", "text": "..."}    # 注入攻击拒绝
        - {"type": "scene_change", "scene": "...", "text": "..."}  # 场景转移
        - {"type": "error", "text": "..."}        # 调用异常
        - {"type": "done", "was_filtered": bool}  # 结束
        """
        # 输入截断
        if len(user_input) > 2000:
            user_input = user_input[:2000] + "……"

        self.write_log("你", user_input)

        # ── 注入检测 ──
        if detect_injection(user_input):
            rejection = random.choice(JI_KANG_REJECTIONS)
            self.write_log("嵇康", rejection + " [注入拦截]")
            yield {"type": "rejection", "text": rejection}
            self.messages.append({"role": "user", "content": user_input})
            self.messages.append({"role": "assistant", "content": rejection})
            self.messages = _trim_messages(self.messages, MAX_HISTORY_ROUNDS)
            yield {"type": "done", "was_filtered": False}
            return

        # ── 场景转移检测（仅性情版） ──
        if self.mode == "personality":
            new_scene = detect_scene_transition(self.scene, user_input)
            if new_scene:
                old_scene_name = SCENE_NAMES.get(self.scene, self.scene)
                new_scene_name = SCENE_NAMES.get(new_scene, new_scene)
                self.scene = new_scene
                # 更新 system prompt
                new_prompt = self._apply_scene()
                self.system_prompt = new_prompt
                self.messages[0] = {"role": "system", "content": new_prompt}
                scene_notice = f"场景已转移：{old_scene_name} → {new_scene_name}"
                self.write_log("系统", scene_notice)
                yield {
                    "type": "scene_change",
                    "scene": new_scene,
                    "scene_name": new_scene_name,
                    "text": scene_notice,
                }

        # ── 身份切换检测（仅性情版） ──
        if self.mode == "personality":
            claim = detect_identity_claim(user_input)
            if claim:
                person_name, target_identity = claim
                if target_identity != self.identity:
                    old_id, new_id = self.switch_identity(target_identity)
                    id_name_map = {"friend": "好友", "enemy": "仇敌", "stranger": "陌生人"}
                    old_name = id_name_map.get(old_id, old_id or "默认")
                    new_name = id_name_map.get(new_id, new_id)
                    notice = f"嵇康识汝为「{person_name}」，身份由「{old_name}」转为「{new_name}」"
                    self.write_log("系统", notice)
                    yield {
                        "type": "identity_change",
                        "identity": new_id,
                        "identity_name_cn": new_name,
                        "person_name": person_name,
                        "text": notice,
                    }

        # ── 事实检索 ──
        facts = retrieve_facts(user_input)
        if facts:
            user_with_facts = (
                f"{user_input}{facts}\n\n"
                "【以上事实备注供你参考。若对方所述与此矛盾，请以亲历者身份坚定反驳，绝不妥协。】"
            )
        else:
            user_with_facts = user_input

        self.messages.append({"role": "user", "content": user_with_facts})

        # ── 通知前端开始书写 ──
        yield {"type": "writing"}

        # ── 调用 LLM（先收集完整文本） ──
        try:
            raw_reply = await call_llm(self.client, self.messages, self.active_tools)
        except Exception as e:
            err_msg = f"[调用异常: {type(e).__name__}: {e}]"
            yield {"type": "error", "text": err_msg}
            self.write_log("系统", err_msg)
            return

        # ── 后置过滤 ──
        reply, was_filtered = post_filter(raw_reply)

        if was_filtered:
            self.write_log("嵇康", reply + " [后世典故拦截]")
            yield {"type": "filtered", "text": reply}
            self.messages.append({"role": "assistant", "content": reply})
        else:
            # ── 心声解析 + 打字机效果输出 ──
            if self.heart_voice:
                formal_reply, heart_reply = parse_heart_voice(reply)

                for char in formal_reply:
                    yield {"type": "token", "text": char}
                    await asyncio.sleep(0.03)

                self.write_log("嵇康", formal_reply)

                if heart_reply:
                    yield {"type": "heart_voice", "text": heart_reply}
                    self.write_log("嵇康·心声", heart_reply)
            else:
                for char in reply:
                    yield {"type": "token", "text": char}
                    await asyncio.sleep(0.03)
                self.write_log("嵇康", reply)

            self.messages.append({"role": "assistant", "content": reply})

        self.messages = _trim_messages(self.messages, MAX_HISTORY_ROUNDS)
        yield {"type": "done", "was_filtered": was_filtered}
