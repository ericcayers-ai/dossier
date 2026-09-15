from dossier.extract import extract_text
def test_text_extract(tmp_path):
 p=tmp_path/'a.json'; p.write_text('{"needle": 1}'); text,meta=extract_text(p); assert 'needle' in text
def test_big_skips(tmp_path):
 p=tmp_path/'a.md'; p.write_bytes(b'x'*(8*1024*1024+1)); assert extract_text(p)[1]['error']=='skipped: size'
