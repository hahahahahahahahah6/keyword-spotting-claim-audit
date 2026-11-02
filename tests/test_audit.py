import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from keyword_spotting_claim_audit.audit import audit, claims, evidence, main
from keyword_spotting_claim_audit.phrases import WAKE, NOWAKE

EXPECTED_WAKE = ('wake word detection', 'wake word', 'wakes on', 'wake phrase', 'hotword detection', 'hotword', 'keyword spotting', 'spots keywords', 'detects keywords', 'keyword detection', 'listens for a keyword', 'listens for the wake word', 'wake up word', 'voice wake up', 'voice activation', 'wakes up on', 'trigger word', 'trigger phrase', 'activation word', 'always listening for', 'detects the wake word', 'detects a wake word', 'recognizes the wake word', 'recognises the wake word', 'wake word recognition', 'keyword recognition', 'voice trigger', 'wake on keyword', 'wakes when you say', 'listens for a hotword', 'detects a hotword', 'hotword recognition', 'custom wake word', 'custom keyword', 'say the wake word', 'wake word support', 'supports wake words', 'keyword activation', 'voice activated', 'wakes the assistant', 'activates on keyword', 'triggered by a keyword', 'wake word engine')
EXPECTED_NOWAKE = ('no wake word detection', 'does not detect wake words', 'without wake word detection', 'no hotword detection', 'does not detect hotwords', 'without hotword detection', 'no keyword spotting', 'does not spot keywords', 'without keyword spotting', 'wake word not supported', 'does not support wake words', 'no voice activation', 'does not listen for a wake word', 'cannot detect the wake word', 'never listens for keywords', 'no keyword detection', 'does not detect keywords', 'without keyword detection', 'no trigger word', 'does not support hotwords', 'cannot wake on a keyword', 'no custom wake word', 'without voice activation', 'does not wake on a keyword')

class AuditTests(unittest.TestCase):
    def test_phrase_oracle(self):
        self.assertEqual(WAKE, EXPECTED_WAKE)
        self.assertEqual(NOWAKE, EXPECTED_NOWAKE)
        self.assertEqual(len(WAKE), 43)
        self.assertEqual(len(NOWAKE), 24)

    def test_all_phrases(self):
        for phrase in WAKE:
            with self.subTest(phrase=phrase): self.assertEqual(claims(phrase), (True, False))
        for phrase in NOWAKE:
            with self.subTest(phrase=phrase): self.assertEqual(claims(phrase), (False, True))

    def fixture(self, doc='keyword spotting', files=None):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); (root/'README.md').write_text(doc)
        for name, content in (files or {}).items():
            path=root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
        return root

    def cli(self, args):
        output=io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code=main(args)
        return code, output.getvalue()

    def test_reports(self):
        root=self.fixture()
        code, out=self.cli([str(root), '--json']); result=json.loads(out)
        self.assertEqual(code, 2); self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual(result['findings'][0]['id'], 'documented-keyword-spotting-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertTrue(result['findings'][0]['message'])
        self.assertEqual(audit(self.fixture('no keyword spotting'))['verdict'], 'PASS')
        self.assertEqual(audit(self.fixture('ordinary prose'))['verdict'], 'PASS')
        good={'app.py':'engine.detect_keyword()'}
        self.assertEqual(audit(self.fixture(files=good))['verdict'], 'PASS')
        denial=self.fixture('no keyword spotting', good)
        self.assertEqual(self.cli([str(denial)])[0], 2)
        self.assertEqual(audit(denial)['findings'][0]['id'], 'documented-no-keyword-spotting-claim-false')

    def test_test_only(self):
        for name in ['tests/a.py','test_a.py','a_test.py']:
            root=self.fixture(files={name:'x.detect_keyword()'})
            self.assertEqual(audit(root)['findings'][0]['severity'], 'MEDIUM')
            self.assertEqual(self.cli([str(root)])[0], 0)
            self.assertEqual(self.cli([str(root),'--fail-on','MEDIUM'])[0], 2)

    def test_fences_and_normalization(self):
        for fence in ['```','~~~','   ````']:
            self.assertEqual(claims(fence+'\nkeyword spotting\n'+fence), (False,False))
        self.assertEqual(claims('`keyword-spotting`'), (True,False))
        self.assertEqual(claims("doesn't detect wake words"), (False,True))
        self.assertEqual(claims('keyword spottingish'), (False,False))
        self.assertEqual(claims('no keyword spotting but detects keywords'), (True,True))

    def test_exclusions_and_ignore(self):
        for name in ['fixtures/a.py','docs/a.py','examples/a.py']:
            self.assertFalse(audit(self.fixture(files={name:'x.detect_keyword()'}))['production_evidence'])
        root=self.fixture(files={'skip/a.py':'x.detect_keyword()','docs/nested/a.md':'no keyword spotting'})
        self.assertFalse(audit(root,['skip'])['production_evidence'])
        self.assertIn('docs/nested/a.md',audit(root)['docs'])
        (root/'link.py').symlink_to(root/'skip/a.py')
        (root/'linked').symlink_to(root/'skip',target_is_directory=True)
        self.assertNotIn('link.py',audit(root)['sources'])
        self.assertNotIn('linked/a.py',audit(root)['sources'])

    def test_split_modules(self):
        root=self.fixture(files={'a.py':'import openwakeword\nm=Model()', 'b.py':'m.predict()'})
        self.assertFalse(audit(root)['production_evidence'])

    def test_errors(self):
        self.assertEqual(self.cli(['/nonexistent-r112-path'])[0],1)
        for args in [[], ['--unknown'], ['.', '--fail-on','BAD']]:
            with self.assertRaises(SystemExit) as cm: self.cli(args)
            self.assertEqual(cm.exception.code,1)

    def test_module_entry(self):
        result=subprocess.run([sys.executable,'-m','keyword_spotting_claim_audit','--version'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0); self.assertEqual(result.stdout.strip(),'0.1.0')

    def test_evidence_yes_00(self):
        self.assertTrue(evidence('import pvporcupine\npvporcupine.create()'))

    def test_evidence_yes_01(self):
        self.assertTrue(evidence('import pvporcupine as pv\npv.create()'))

    def test_evidence_yes_02(self):
        self.assertTrue(evidence('from pvporcupine import engine as pv\npv.create()'))

    def test_evidence_yes_03(self):
        self.assertTrue(evidence('import openwakeword\nm=Model()\nm.predict()'))

    def test_evidence_yes_04(self):
        self.assertTrue(evidence('from openwakeword.model import Model as M\nm=M()\nm.predict()'))

    def test_evidence_yes_05(self):
        self.assertTrue(evidence('import openwakeword as ow\nm=ow.Model()\nm.predict()'))

    def test_evidence_yes_06(self):
        self.assertTrue(evidence('HotwordDetector()'))

    def test_evidence_yes_07(self):
        self.assertTrue(evidence('import snowboydecoder as s\ns.HotwordDetector()'))

    def test_evidence_yes_08(self):
        self.assertTrue(evidence('from snowboydecoder import HotwordDetector as H\nH()'))

    def test_evidence_yes_09(self):
        self.assertTrue(evidence('import pvporcupine as pv\ndef pv(): pass\npv.create()'))

    def test_evidence_yes_10(self):
        self.assertTrue(evidence('x.detect_keyword()'))

    def test_evidence_yes_11(self):
        self.assertTrue(evidence('from engine import detect_keyword as call\ncall()'))

    def test_evidence_yes_12(self):
        self.assertTrue(evidence('import detect_keyword as call\ncall()'))

    def test_evidence_yes_13(self):
        self.assertTrue(evidence('x.detect_wake_word()'))

    def test_evidence_yes_14(self):
        self.assertTrue(evidence('from engine import detect_wake_word as call\ncall()'))

    def test_evidence_yes_15(self):
        self.assertTrue(evidence('import detect_wake_word as call\ncall()'))

    def test_evidence_yes_16(self):
        self.assertTrue(evidence('x.detect_hotword()'))

    def test_evidence_yes_17(self):
        self.assertTrue(evidence('from engine import detect_hotword as call\ncall()'))

    def test_evidence_yes_18(self):
        self.assertTrue(evidence('import detect_hotword as call\ncall()'))

    def test_evidence_yes_19(self):
        self.assertTrue(evidence('x.listen_for_keyword()'))

    def test_evidence_yes_20(self):
        self.assertTrue(evidence('from engine import listen_for_keyword as call\ncall()'))

    def test_evidence_yes_21(self):
        self.assertTrue(evidence('import listen_for_keyword as call\ncall()'))

    def test_evidence_yes_22(self):
        self.assertTrue(evidence('x.listen_for_wake_word()'))

    def test_evidence_yes_23(self):
        self.assertTrue(evidence('from engine import listen_for_wake_word as call\ncall()'))

    def test_evidence_yes_24(self):
        self.assertTrue(evidence('import listen_for_wake_word as call\ncall()'))

    def test_evidence_no_00(self):
        self.assertFalse(evidence('import pvporcupine'))

    def test_evidence_no_01(self):
        self.assertFalse(evidence('import openwakeword'))

    def test_evidence_no_02(self):
        self.assertFalse(evidence('import snowboydecoder'))

    def test_evidence_no_03(self):
        self.assertFalse(evidence('vad.is_speech(x)'))

    def test_evidence_no_04(self):
        self.assertFalse(evidence('get_speech_timestamps(x)'))

    def test_evidence_no_05(self):
        self.assertFalse(evidence('Pipeline.from_pretrained("pyannote/segmentation")'))

    def test_evidence_no_06(self):
        self.assertFalse(evidence('whisper.transcribe(x)'))

    def test_evidence_no_07(self):
        self.assertFalse(evidence('r.recognize_google(x)'))

    def test_evidence_no_08(self):
        self.assertFalse(evidence('pipeline("automatic-speech-recognition")'))

    def test_evidence_no_09(self):
        self.assertFalse(evidence('s.verify_files(a,b)'))

    def test_evidence_no_10(self):
        self.assertFalse(evidence('VoiceEncoder().embed_utterance(x)'))

    def test_evidence_no_11(self):
        self.assertFalse(evidence('Pipeline.from_pretrained("pyannote/speaker-verification")'))

    def test_evidence_no_12(self):
        self.assertFalse(evidence('x.verify_speaker()'))

    def test_evidence_no_13(self):
        self.assertFalse(evidence('x.diarize()'))

    def test_evidence_no_14(self):
        self.assertFalse(evidence('Pipeline.from_pretrained("pyannote/diarization")'))

    def test_evidence_no_15(self):
        self.assertFalse(evidence('noisereduce.reduce_noise(x)'))

    def test_evidence_no_16(self):
        self.assertFalse(evidence('df.enhance(x)'))

    def test_evidence_no_17(self):
        self.assertFalse(evidence('x.suppress_noise()'))

    def test_evidence_no_18(self):
        self.assertFalse(evidence('x.remove_noise()'))

    def test_evidence_no_19(self):
        self.assertFalse(evidence('microphone.read()'))

    def test_evidence_no_20(self):
        self.assertFalse(evidence('audio.play()'))

    def test_evidence_no_21(self):
        self.assertFalse(evidence('engine.say(x)'))

    def test_evidence_no_22(self):
        self.assertFalse(evidence('gTTS(x).save(x)'))

    def test_evidence_no_23(self):
        self.assertFalse(evidence('edge_tts.Communicate(x)'))

    def test_evidence_no_24(self):
        self.assertFalse(evidence('import openwakeword\nModel()'))

    def test_evidence_no_25(self):
        self.assertFalse(evidence('import openwakeword\nx.predict()'))

    def test_evidence_no_26(self):
        self.assertFalse(evidence('porcupine.process(x)'))

    def test_evidence_no_27(self):
        self.assertFalse(evidence('other.create()'))

    def test_evidence_no_28(self):
        self.assertFalse(evidence('"pvporcupine Model HotwordDetector"'))

    def test_evidence_no_29(self):
        self.assertFalse(evidence('subprocess.run(["wakeword"])'))

    def test_evidence_no_30(self):
        self.assertFalse(evidence('HotwordDetector'))

    def test_evidence_no_31(self):
        self.assertFalse(evidence('x.detect_keyword('))

    def test_evidence_no_32(self):
        self.assertFalse(evidence('detect_keyword()'))

    def test_evidence_no_33(self):
        self.assertFalse(evidence('from engine import detect_keyword as d\ndef d(): pass\nd()'))

    def test_evidence_no_34(self):
        self.assertFalse(evidence('def detect_keyword(): pass\nx.detect_keyword()'))

    def test_evidence_no_35(self):
        self.assertFalse(evidence('def HotwordDetector(): pass\nx.HotwordDetector()'))

    def test_evidence_no_36(self):
        self.assertFalse(evidence('import openwakeword\ndef predict(): pass\nModel()\nx.predict()'))

    def test_evidence_no_37(self):
        self.assertFalse(evidence('import openwakeword\nclass A:\n def Model(self): pass\nx.Model()\nx.predict()'))

    def test_evidence_no_38(self):
        self.assertFalse(evidence('import other as pv\npv.create()'))

