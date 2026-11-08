from __future__ import annotations

import importlib.util
import json
import logging
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VENDOR_APP = ROOT / "vendor" / "universal-web-api" / "app"


class DeepSeekParserContractTest(unittest.TestCase):
    """Regression coverage for DeepSeek's current no-op fragment snapshots."""

    @classmethod
    def setUpClass(cls) -> None:
        parser_path = VENDOR_APP / "core" / "parsers" / "deepseek_parser.py"
        base_path = VENDOR_APP / "core" / "parsers" / "base.py"
        if not parser_path.exists():
            raise unittest.SkipTest("universal-web-api vendor checkout is not installed")

        cls._saved_modules = {
            name: sys.modules.get(name)
            for name in (
                "app",
                "app.core",
                "app.core.config",
                "app.core.parsers",
                "app.core.parsers.base",
                "app.core.parsers.deepseek_parser",
            )
        }

        app_package = types.ModuleType("app")
        app_package.__path__ = [str(VENDOR_APP)]
        core_package = types.ModuleType("app.core")
        core_package.__path__ = [str(VENDOR_APP / "core")]
        parsers_package = types.ModuleType("app.core.parsers")
        parsers_package.__path__ = [str(VENDOR_APP / "core" / "parsers")]
        config_module = types.ModuleType("app.core.config")
        config_module.logger = logging.getLogger("test.deepseek_parser")

        sys.modules.update(
            {
                "app": app_package,
                "app.core": core_package,
                "app.core.config": config_module,
                "app.core.parsers": parsers_package,
            }
        )

        cls._load_module("app.core.parsers.base", base_path)
        parser_module = cls._load_module(
            "app.core.parsers.deepseek_parser",
            parser_path,
        )
        cls.Parser = parser_module.DeepSeekParser

    @classmethod
    def tearDownClass(cls) -> None:
        for name, module in cls._saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    @staticmethod
    def _load_module(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load module: {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _event(payload: dict) -> str:
        return "data: " + json.dumps(payload) + "\n\n"

    def test_no_operation_fragment_snapshot_emits_response_only(self) -> None:
        parser = self.Parser()
        ready = (
            "event: ready\n"
            'data: {"request_message_id":1,"response_message_id":2,'
            '"model_type":"default"}\n\n'
        )
        thinking = ready + self._event(
            {
                "v": {
                    "response": {
                        "status": "WIP",
                        "fragments": [
                            {"id": 2, "type": "THINK", "content": "reasoning"}
                        ],
                    }
                }
            }
        )
        thinking_deltas = thinking + self._event(
            {
                "p": "response/fragments/-1/content",
                "o": "APPEND",
                "v": " details",
            }
        )
        response_started = thinking_deltas + self._event(
            {
                "p": "response/fragments",
                "v": [
                    {
                        "id": 2,
                        "type": "THINK",
                        "content": "reasoning details",
                    },
                    {"id": 3, "type": "RESPONSE", "content": "A"},
                ],
            }
        )
        response_deltas = (
            response_started
            + self._event(
                {
                    "p": "response/fragments/-1/content",
                    "o": "APPEND",
                    "v": "BC",
                }
            )
            + self._event({"v": "D"})
        )
        finished = response_deltas + self._event(
            {
                "p": "response",
                "o": "BATCH",
                "v": [
                    {"p": "accumulated_token_usage", "v": 73},
                    {"p": "quasi_status", "v": "FINISHED"},
                ],
            }
        ) + self._event(
            {"p": "response/status", "o": "SET", "v": "FINISHED"}
        )

        outputs = []
        result = {}
        for raw in (
            ready,
            thinking,
            thinking_deltas,
            response_started,
            response_deltas,
            finished,
        ):
            result = parser.parse_chunk(raw)
            outputs.append(result["content"])

        self.assertEqual(["", "", "", "A", "BCD", ""], outputs)
        self.assertEqual("ABCD", "".join(outputs))
        self.assertTrue(result["done"])


if __name__ == "__main__":
    unittest.main()
