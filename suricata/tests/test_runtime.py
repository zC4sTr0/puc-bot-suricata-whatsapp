import contextlib
import io
import json
import os
import unittest
from unittest import mock

from suricata.runtime import run_from_environment


class RuntimeCompositionTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.calls = []

    def run_runtime(self, destinations, *, delivery="desligada"):
        class Destination:
            def __init__(self, jid):
                self.jid = jid

        def objects_factory(uri):
            self.calls.append(("objects", uri))
            return {"uri": uri}

        def destinations_factory():
            self.calls.append(("destinations",))
            return [Destination(jid) for jid in destinations]

        def canvas_factory():
            self.calls.append(("canvas",))
            return "canvas"

        def session_factory(objects):
            self.calls.append(("session", objects))
            return "session"

        def bridge_factory(session):
            self.calls.append(("bridge", session))
            return "bridge"

        def single_runner(**kwargs):
            self.calls.append(("single", kwargs))
            return 7, {"estado": "ok"}

        def multi_runner(**kwargs):
            self.calls.append(("multi", kwargs))
            return 8, [{"estado": "ok"}]

        with mock.patch.dict(
            os.environ,
            {"SURICATA_ESTADO_URI": "local-state", "SURICATA_CANVAS_TOKEN": "token",
             "SURICATA_ENTREGA": delivery},
            clear=False,
        ):
            code = run_from_environment(
                canvas_factory=canvas_factory,
                destinations_factory=destinations_factory,
                objects_factory=objects_factory,
                session_factory=session_factory,
                bridge_factory=bridge_factory,
                single_runner=single_runner,
                multi_runner=multi_runner,
                print_fn=self.output.write,
            )
        return code, json.loads(self.output.getvalue())

    def test_missing_state_fails_closed(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            code = run_from_environment(
                canvas_factory=mock.Mock(), destinations_factory=mock.Mock(),
                objects_factory=mock.Mock(), session_factory=mock.Mock(),
                bridge_factory=mock.Mock(), single_runner=mock.Mock(),
                multi_runner=mock.Mock(), print_fn=self.output.write,
            )
        self.assertEqual(code, 5)
        self.assertEqual(json.loads(self.output.getvalue())["estado"], "erro")

    def test_single_destination_does_not_build_delivery_when_disabled(self):
        code, report = self.run_runtime(["group@g.us"])
        self.assertEqual(code, 7)
        self.assertEqual(report["codigo"], 7)
        self.assertEqual([call[0] for call in self.calls], ["objects", "destinations", "canvas", "single"])
        self.assertIsNone(self.calls[-1][1]["ponte"])

    def test_single_destination_builds_delivery_only_when_enabled(self):
        code, _ = self.run_runtime(["group@g.us"], delivery="ligada")
        self.assertEqual(code, 7)
        self.assertEqual([call[0] for call in self.calls],
                         ["objects", "session", "bridge", "destinations", "canvas", "single"])

    def test_multiple_destinations_preserve_multi_runner_shape(self):
        code, report = self.run_runtime(["one@g.us", "two@g.us"])
        self.assertEqual(code, 8)
        self.assertEqual(report["codigo"], 8)
        self.assertEqual([call[0] for call in self.calls], ["objects", "destinations", "canvas", "multi"])


if __name__ == "__main__":
    unittest.main()
