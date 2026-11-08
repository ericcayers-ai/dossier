from pathlib import Path
import csv, io, json

def extract_text(path:Path):
    meta={}
    try:
        if path.stat().st_size>8*1024*1024: return '', {'error':'skipped: size'}
        ext=path.suffix.lower()
        if ext in {'.md','.txt','.py','.json'}:
            text=path.read_text(encoding='utf-8',errors='replace')
            if ext=='.json':
                obj=json.loads(text); keys=[]
                def walk(x):
                    if isinstance(x,dict):
                        keys.extend(map(str,x.keys())); [walk(v) for v in x.values()]
                    elif isinstance(x,list): [walk(v) for v in x]
                walk(obj); meta['keys']=len(keys); text += '\n'+' '.join(keys)
            return text,meta
        if ext=='.csv':
            rows=list(csv.reader(io.StringIO(path.read_text(encoding='utf-8',errors='replace'))))[:201]
            meta['rows']=max(0,len(rows)-1); return '\n'.join(','.join(r) for r in rows),meta
        if ext=='.docx':
            from docx import Document
            d=Document(str(path)); parts=[p.text for p in d.paragraphs]
            for t in d.tables:
                parts += [c.text for r in t.rows for c in r.cells]
            for section in d.sections:
                parts += [p.text for p in section.header.paragraphs]; parts += [p.text for p in section.footer.paragraphs]
            return '\n'.join(x for x in parts if x),meta
        if ext=='.pdf':
            # One PDF engine for the whole app: `render.text_layout` prefers PDFium
            # (permissive) and only falls back to PyMuPDF when the optional extra is
            # installed, so no module imports an AGPL library directly.
            from .engine import render as pdf_engine
            layout = pdf_engine.text_layout(path)
            if layout is None:
                return '', {'error': 'no PDF text extractor is available'}
            meta['pages'] = len(layout['pages'])
            return '\n'.join(block['text'] for page in layout['pages']
                             for block in page['blocks']), meta
        return '',meta
    except Exception as e: return '', {'error':str(e)}
