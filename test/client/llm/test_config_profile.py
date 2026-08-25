#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""配置档案：公共策略 + profiles/<name> 模型绑定"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config_manager import ConfigManager
from src.utils.config_profile import (
    load_profile_preset_models,
    load_profile_presets,
    load_profile_visible_models,
    resolve_config_profile,
    resolve_profile_file,
)
from src.client.llm.registry import LiteLLMRegistry


class TestConfigProfile(unittest.TestCase):
    def test_explicit_arg_profile_wins(self):
        with patch.dict(os.environ, {
            "MODEL_GATEWAY_TYPE": "model_lake",
        }, clear=False):
            self.assertEqual(resolve_config_profile("litellm"), "litellm")

    def test_follow_gateway_type(self):
        with patch.dict(os.environ, {
            "MODEL_GATEWAY_TYPE": "model_lake",
        }, clear=False):
            self.assertEqual(resolve_config_profile(), "model_lake")

    def test_openai_alias(self):
        with patch.dict(os.environ, {"MODEL_GATEWAY_TYPE": "openai"}, clear=False):
            self.assertEqual(resolve_config_profile(), "model_lake")

    def test_unknown_falls_back_to_litellm(self):
        with patch.dict(os.environ, {"MODEL_GATEWAY_TYPE": "does-not-exist"}, clear=False):
            self.assertEqual(resolve_config_profile(), "litellm")

    def test_litellm_bindings(self):
        models = load_profile_preset_models("litellm")
        self.assertEqual(models["fast"], "qwen3.7-flash")
        self.assertEqual(models["quality"], "deepseek-v4-pro")

    def test_model_lake_bindings_keep_channel(self):
        models = load_profile_preset_models("model_lake")
        self.assertEqual(models["fast"], "alibaba-dashscope/ali-qwen3-7-flash")
        self.assertIn("/", models["fast"])

    def test_config_manager_loads_profile_preset_table(self):
        with patch.dict(os.environ, {"MODEL_GATEWAY_TYPE": "model_lake"}, clear=False):
            cm = ConfigManager()
            preset = cm.get_llm_preset("fast")
            self.assertEqual(preset["model"], "alibaba-dashscope/ali-qwen3-7-flash")
            self.assertEqual(preset["temperature"], 0.3)
            self.assertEqual(preset["thinking_level"], "off")
            self.assertEqual(preset["timeout"], 60)

        lake = load_profile_presets("model_lake")
        lite = load_profile_presets("litellm")
        self.assertEqual(lake["fast"]["model"], "alibaba-dashscope/ali-qwen3-7-flash")
        self.assertEqual(lite["fast"]["model"], "qwen3.7-flash")
        self.assertIn("temperature", lake["fast"])
        self.assertIn("thinking_level", lake["reasoning"])

    def test_capability_files_come_from_profile(self):
        with patch.dict(os.environ, {"MODEL_GATEWAY_TYPE": "litellm"}, clear=False):
            path = resolve_profile_file("thinking_models.json")
            self.assertTrue(path.exists())
            self.assertIn("profiles/litellm", str(path).replace("\\", "/"))
            specs = LiteLLMRegistry._load_thinking_models()
            self.assertIn("qwen3.7-flash", specs)

        with patch.dict(os.environ, {"MODEL_GATEWAY_TYPE": "model_lake"}, clear=False):
            path = resolve_profile_file("thinking_models.json")
            self.assertIn("profiles/model_lake", str(path).replace("\\", "/"))
            specs = LiteLLMRegistry._load_thinking_models()
            self.assertIn("ali-qwen3-7-flash", specs)
            self.assertNotIn("qwen3.7-flash", specs)

    def test_model_lake_thinking_lookup_accepts_channel_route(self):
        """Model Lake 档案用 channel/model 写 DeepSeek 时，SDK id 也必须能查到声明。"""
        with patch.dict(os.environ, {"MODEL_GATEWAY_TYPE": "model_lake"}, clear=False):
            reg = LiteLLMRegistry()
            official = "openai/deepseek-official/deepseek-v4-flash"
            ali = "openai/alibaba-dashscope/ali-deepseek-v4-flash"
            qwen = "openai/alibaba-dashscope/ali-qwen3-7-flash"

            self.assertEqual(reg.resolve_reasoning_effort(official, "high"), "high")
            self.assertEqual(reg.clamp_thinking_level(official, "high"), "high")
            self.assertIsNotNone(reg.peek_thinking_spec(official))

            self.assertEqual(reg.resolve_reasoning_effort(ali, "high"), "high")
            self.assertEqual(reg.clamp_thinking_level(ali, "high"), "high")

            # 只写最后一段的 Qwen 条目仍按裸名命中
            self.assertEqual(reg.resolve_reasoning_effort(qwen, "medium"), "enabled")
            self.assertEqual(reg.clamp_thinking_level(qwen, "high"), "medium")

    def test_thinking_miss_passthrough_keeps_user_level(self):
        """档案对不上时不能把用户打开的思考档位钳成 off / None。"""
        with patch.dict(os.environ, {"MODEL_GATEWAY_TYPE": "model_lake"}, clear=False):
            reg = LiteLLMRegistry()
            unknown = "openai/unknown-channel/deepseek-v4-flash-unknown"
            self.assertEqual(reg.clamp_thinking_level(unknown, "high"), "high")
            self.assertEqual(reg.resolve_reasoning_effort(unknown, "high"), "high")
            self.assertEqual(reg.clamp_thinking_level(unknown, "off"), "off")
            self.assertIsNone(reg.resolve_reasoning_effort(unknown, "off"))

    def test_visible_whitelist_is_separate_from_presets(self):
        presets = load_profile_preset_models("model_lake")
        visible = load_profile_visible_models("model_lake")
        self.assertIn("fast", presets)
        self.assertIn("alibaba-dashscope/ali-qwen3-7-flash", visible)
        self.assertNotIn("fast", visible)

        litellm_visible = load_profile_visible_models("litellm")
        self.assertIn("qwen3.7-flash", litellm_visible)


if __name__ == "__main__":
    unittest.main()
