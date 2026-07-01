"""Chat Agent 工具 handler 模块。"""

from src.service.chat.tools.handlers.context_window import DEFINITION as CONTEXT_WINDOW
from src.service.chat.tools.handlers.drill_down import DEFINITION as DRILL_DOWN
from src.service.chat.tools.handlers.grep_chunks import DEFINITION as GREP_CHUNKS
from src.service.chat.tools.handlers.read_chunks import DEFINITION as READ_CHUNKS
from src.service.chat.tools.handlers.read_image_chunks import (
    DEFINITION as READ_IMAGE_CHUNKS,
)
from src.service.chat.tools.handlers.roll_up import DEFINITION as ROLL_UP
from src.service.chat.tools.handlers.search_knowledge_base import (
    DEFINITION as SEARCH_KNOWLEDGE_BASE,
)
from src.service.chat.tools.handlers.skeleton import DEFINITION as SKELETON
from src.service.chat.tools.handlers.skills_list import DEFINITION as SKILLS_LIST
from src.service.chat.tools.handlers.skill_view import DEFINITION as SKILL_VIEW

ALL_TOOL_DEFINITIONS = (
    CONTEXT_WINDOW,
    DRILL_DOWN,
    ROLL_UP,
    SKELETON,
    SEARCH_KNOWLEDGE_BASE,
    GREP_CHUNKS,
    READ_CHUNKS,
    READ_IMAGE_CHUNKS,
    SKILLS_LIST,
    SKILL_VIEW,
)
