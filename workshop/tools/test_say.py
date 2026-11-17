"""Tests for say.py's stream parser. Run:  python3 -m unittest workshop/tools/test_say.py -v"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import say  # noqa: E402


def sse(*events):
    return "\n".join("data: " + json.dumps({"event": e}) for e in events) + "\n"


def tool_start(i, name):
    return {"contentBlockStart": {"contentBlockIndex": i, "start": {"toolUse": {"toolUseId": "t%d" % i, "name": name}}}}


def tool_delta(i, piece):
    return {"contentBlockDelta": {"contentBlockIndex": i, "delta": {"toolUse": {"input": piece}}}}


def text_delta(i, piece):
    return {"contentBlockDelta": {"contentBlockIndex": i, "delta": {"text": piece}}}


class ParseStream(unittest.TestCase):
    def test_two_tools_with_fragmented_arguments_and_a_reply(self):
        stream = sse(
            tool_start(0, "walk"), tool_delta(0, ""), tool_delta(0, '{"direc'), tool_delta(0, 'tion": "forward", "meters": 1}'),
            tool_start(1, "turn"), tool_delta(1, '{"side": "left"'), tool_delta(1, ', "degrees": 90}'),
            text_delta(2, "Listo. "), text_delta(2, "Avancé 1 metro."),
        )
        calls, reply = say.parse_stream(stream)
        self.assertEqual(calls, [("walk", {"direction": "forward", "meters": 1}), ("turn", {"side": "left", "degrees": 90})])
        self.assertEqual(reply, "Listo. Avancé 1 metro.")

    def test_a_tool_without_arguments(self):
        calls, _ = say.parse_stream(sse(tool_start(0, "stop"), tool_delta(0, "")))
        self.assertEqual(calls, [("stop", {})])

    def test_reply_only(self):
        calls, reply = say.parse_stream(sse(text_delta(0, "Hola")))
        self.assertEqual((calls, reply), ([], "Hola"))

    def test_parallel_blocks_keep_their_own_arguments(self):
        stream = sse(tool_start(0, "walk"), tool_start(1, "walk"), tool_delta(0, '{"direction": "forward"'), tool_delta(1, '{"direction": "left"'), tool_delta(0, ', "meters": 2}'), tool_delta(1, ', "meters": 1}'))
        calls, _ = say.parse_stream(stream)
        self.assertEqual(calls, [("walk", {"direction": "forward", "meters": 2}), ("walk", {"direction": "left", "meters": 1})])

    def test_garbage_and_non_data_lines_are_ignored(self):
        text = "status=200\ndata: not json\n\n" + sse(text_delta(0, "ok")) + "data: [DONE]\n"
        self.assertEqual(say.parse_stream(text), ([], "ok"))

    def test_broken_tool_arguments_are_shown_raw_not_crashed(self):
        calls, _ = say.parse_stream(sse(tool_start(0, "walk"), tool_delta(0, '{"direction": ')))
        self.assertEqual(calls[0][0], "walk")
        self.assertIsInstance(calls[0][1], str)

    def test_the_answer_after_the_tools_is_a_second_message_whose_blocks_restart_at_zero(self):
        # What the real runtime sends: message 1 = tool calls (blocks 0, 1); message 2 = the text (block 0 again).
        stream = sse(
            {"messageStart": {"role": "assistant"}},
            tool_start(0, "walk"), tool_delta(0, '{"direction": "forward", "meters": 2}'),
            tool_start(1, "turn"), tool_delta(1, '{"side": "right", "degrees": 90}'),
            {"messageStop": {"stopReason": "tool_use"}},
            {"messageStart": {"role": "assistant"}},
            text_delta(0, "Listo. "), text_delta(0, "Avancé 2 m."),
            {"messageStop": {"stopReason": "end_turn"}},
        )
        calls, reply = say.parse_stream(stream)
        self.assertEqual([c[0] for c in calls], ["walk", "turn"])
        self.assertEqual(reply, "Listo. Avancé 2 m.")

    def test_empty_stream(self):
        self.assertEqual(say.parse_stream(""), ([], ""))

    def test_format_call(self):
        self.assertEqual(say.format_call("walk", {"direction": "forward", "meters": 2}), "walk(direction='forward', meters=2)")
        self.assertEqual(say.format_call("stop", {}), "stop()")

    def test_the_default_session_id_is_long_enough_for_agentcore(self):
        self.assertGreaterEqual(len(say.DEFAULT_SESSION), 33)


if __name__ == "__main__":
    unittest.main()
