#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""Model Lake 鉴权：静态 token / Service JWT 换票 / URL 归一 / fail-closed"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.env_manager import EnvManager, normalize_model_lake_api_base
from src.client.llm.model_lake_auth import (
    ModelLakeAuthError,
    ModelLakeAuthProvider,
    extract_access_token,
    looks_like_auth_failure,
    reset_model_lake_auth,
)


def _auth_body(token: str, expires_in: int = 3600) -> dict:
    return {"code": 200, "data": {"access_token": token, "expires_in": expires_in}}


class TestModelLakeAuth(unittest.TestCase):
    def tearDown(self) -> None:
        reset_model_lake_auth()

    def test_normalize_model_lake_api_base(self):
        self.assertEqual(
            normalize_model_lake_api_base("http://192.168.19.238:30888"),
            "http://192.168.19.238:30888/model-lake/v1",
        )
        self.assertEqual(
            normalize_model_lake_api_base("http://192.168.19.238:30888/model-lake"),
            "http://192.168.19.238:30888/model-lake/v1",
        )
        self.assertEqual(
            normalize_model_lake_api_base("http://192.168.19.238:30888/model-lake/v1/"),
            "http://192.168.19.238:30888/model-lake/v1",
        )

    def test_extract_access_token_shapes(self):
        token, ttl = extract_access_token(_auth_body("tok-1", 3600))
        self.assertEqual(token, "tok-1")
        self.assertEqual(ttl, 3600.0)
        token, ttl = extract_access_token({"access_token": "eyJabc", "expires_in": 120})
        self.assertEqual(token, "eyJabc")
        self.assertEqual(ttl, 120.0)
        token, _ = extract_access_token({"code": 401, "data": {"access_token": "x"}})
        self.assertIsNone(token)
        token, ttl = extract_access_token({"message": "ok"})
        self.assertIsNone(token)
        self.assertIsNone(ttl)

    def test_missing_credentials_raises_error(self):
        env = EnvManager()
        with patch.dict(os.environ, {
            "MODEL_GATEWAY_TYPE": "model_lake",
        }, clear=True):
            self.assertFalse(env.has_auth_client_credentials())
            self.assertIsNone(env.get_model_gateway_url())
            with self.assertRaises(ModelLakeAuthError):
                ModelLakeAuthProvider().get_token()

    def test_model_lake_does_not_fallback_to_litellm_key(self):
        env = EnvManager()
        with patch.dict(os.environ, {
            "MODEL_GATEWAY_TYPE": "model_lake",
            "LITELLM_PROXY_URL": "http://litellm:4000",
            "LITELLM_PROXY_KEY": "sk-litellm-key",
        }, clear=True):
            self.assertIsNone(env.get_model_gateway_key())
            self.assertIsNone(env.get_model_gateway_url())
            self.assertEqual(env.get_embedding_gateway_key(), "sk-litellm-key")

    def test_model_lake_base_alias(self):
        env = EnvManager()
        with patch.dict(os.environ, {
            "MODEL_GATEWAY_TYPE": "model_lake",
            "MODEL_LAKE_BASE": "http://192.168.19.238:30888",
        }, clear=True):
            self.assertEqual(env.get_model_gateway_url(), "http://192.168.19.238:30888/model-lake/v1")

    def _mock_http(self, bodies):
        inst = MagicMock()
        inst.__enter__.return_value = inst
        inst.__exit__.return_value = False
        responses = []
        for body in bodies:
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = body
            responses.append(resp)
        inst.post.side_effect = responses
        return inst

    def test_service_jwt_mint_and_cache(self):
        with patch.dict(os.environ, {
            "MODEL_GATEWAY_TYPE": "model_lake",
            "AUTH_BASE": "http://192.168.19.238:31401",
            "AUTH_CLIENT_ID": "jp-knowledge-system",
            "AUTH_CLIENT_SECRET": "secret",
        }, clear=True):
            provider = ModelLakeAuthProvider()
            with patch("httpx.Client") as client_cls:
                inst = self._mock_http([_auth_body("tok-live")])
                client_cls.return_value = inst
                self.assertEqual(provider.get_token(), "tok-live")
                args, kwargs = inst.post.call_args
                self.assertEqual(args[0], "http://192.168.19.238:31401/auth/client/token")
                self.assertEqual(kwargs["json"]["client_id"], "jp-knowledge-system")
                self.assertEqual(provider.get_token(), "tok-live")
                self.assertEqual(inst.post.call_count, 1)

    def test_force_refresh_remints(self):
        with patch.dict(os.environ, {
            "AUTH_BASE": "http://192.168.19.238:31401",
            "AUTH_CLIENT_ID": "aks",
            "AUTH_CLIENT_SECRET": "secret",
        }, clear=True):
            provider = ModelLakeAuthProvider()
            with patch("httpx.Client") as client_cls:
                inst = self._mock_http([_auth_body("t1"), _auth_body("t2")])
                client_cls.return_value = inst
                self.assertEqual(provider.get_token(), "t1")
                self.assertEqual(provider.get_token(force_refresh=True), "t2")
                self.assertEqual(inst.post.call_count, 2)

    def test_auth_code_not_200(self):
        with patch.dict(os.environ, {
            "AUTH_BASE": "http://192.168.19.238:31401",
            "AUTH_CLIENT_ID": "aks",
            "AUTH_CLIENT_SECRET": "secret",
        }, clear=True):
            provider = ModelLakeAuthProvider()
            with patch("httpx.Client") as client_cls:
                inst = self._mock_http([{"code": 401, "message": "bad client"}])
                client_cls.return_value = inst
                with self.assertRaises(ModelLakeAuthError):
                    provider.get_token()

    def test_fail_closed_without_credentials(self):
        with patch.dict(os.environ, {"MODEL_GATEWAY_TYPE": "model_lake"}, clear=True):
            with self.assertRaises(ModelLakeAuthError):
                ModelLakeAuthProvider().get_token()

    def test_looks_like_auth_failure(self):
        self.assertTrue(looks_like_auth_failure(RuntimeError('{"error":{"code":"expired_token"}}')))
        self.assertTrue(looks_like_auth_failure(RuntimeError("AuthenticationError: Error code: 401")))
        self.assertFalse(looks_like_auth_failure(RuntimeError("model_not_allowed")))


if __name__ == "__main__":
    unittest.main()
