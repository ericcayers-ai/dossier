import {useEffect,useRef,useState} from 'react';
import type {ReactNode} from 'react';
import {EditorView,keymap} from '@codemirror/view';
import type {ViewUpdate} from '@codemirror/view';
import {EditorState} from '@codemirror/state';
import type {Extension} from '@codemirror/state';
import {indentWithTab} from '@codemirror/commands';
import {markdown} from '@codemirror/lang-markdown';
import {json as jsonLanguage} from '@codemirror/lang-json';
import {python} from '@codemirror/lang-python';
import {api,checkUrl} from '../lib/api';
import type {Tab} from '../lib/session';
import {dirOf,extOf,isImage} from '../lib/files';
import {MarkdownDoc,splitFrontMatter} from '../lib/markdown';
import {useLoad} from '../lib/useLoad';
import CsvGrid from '../viewer/CsvGrid';
import {ErrorState,Loading} from './StateViews';

function CodeEditor({tab,onChange,readOnly=false}:{tab:Tab;onChange:(value:string)=>void;readOnly?:boolean}):ReactNode{
  const host=useRef<HTMLDivElement>(null);
  const view=useRef<EditorView|null>(null);
  const callback=useRef(onChange);
  const suppress=useRef(false);
  callback.current=onChange;

  useEffect(()=>{
    if(!host.current)return;
    const ext=extOf(tab.rel);
    const language:Extension=ext==='md'?markdown():ext==='json'?jsonLanguage():ext==='py'?python():[];
    const state=EditorState.create({
      doc:tab.content??'',
      extensions:[
        keymap.of([indentWithTab]),
        language,
        EditorState.readOnly.of(readOnly),
        EditorView.editable.of(!readOnly),
        EditorView.updateListener.of((update:ViewUpdate)=>{if(update.docChanged&&!suppress.current)callback.current(update.state.doc.toString())}),
      ],
    });
    const instance=new EditorView({state,parent:host.current});
    view.current=instance;
    return()=>{instance.destroy();view.current=null};
    // readOnly is fixed per mount: a read failure never renders an editor at all.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[tab.rel]);

  /* Reload-theirs / external change: replace the buffer without marking it dirty. */
  useEffect(()=>{
    const instance=view.current;
    if(!instance||tab.content===undefined)return;
    const current=instance.state.doc.toString();
    if(current===tab.content)return;
    suppress.current=true;
    instance.dispatch({changes:{from:0,to:current.length,insert:tab.content}});
    suppress.current=false;
  },[tab.content,tab.rel]);

  return <div className="editor" ref={host}/>;
}

/** Images, PDFs and DOCX renders are preflighted so a failure is a sentence,
 *  not a broken icon or a raw JSON error body inside the document pane. */
function MediaPane({url,kind,title,onRetry,isPdf=false}:{url:string;kind:'image'|'frame';title:string;onRetry:()=>void;isPdf?:boolean}):ReactNode{
  const {state,reload}=useLoad(async()=>{await checkUrl(url);return url},[url]);
  const [decodeFailed,setDecodeFailed]=useState(false);
  useEffect(()=>setDecodeFailed(false),[url]);
  /* A browser without a PDF viewer (headless Chrome, some Firefox builds, an
     embedded webview) renders an iframe of a PDF as a blank rectangle. The file
     is fine and the server sends `application/pdf` inline, so say that instead of
     showing nothing: the status bar used to promise "pdf: read-only view" above
     an empty pane. */
  const canFramePdf=isPdf?typeof navigator==='undefined'||navigator.pdfViewerEnabled!==false:true;
  if(isPdf&&!canFramePdf)return <div className="media-error" role="status">
    <h2>This browser cannot show PDFs inside a page.</h2>
    <p>The file is intact and the server sends it as <code>application/pdf</code>. Open it in its own tab, or use Reveal in File Explorer in the bundle rail.</p>
    <p><a className="primary" href={url} target="_blank" rel="noreferrer">Open the PDF in a new tab</a></p>
  </div>;
  if(state.status==='loading')return <Loading what={kind==='image'?'the image':'the server render'}/>;
  if(state.status==='failed')return <ErrorState error={state.error} what={kind==='image'?'loading this image':'rendering this document'} onRetry={()=>{reload();onRetry()}}/>;
  if(kind==='image')return <div className="image-view">
    {decodeFailed
      ?<div className="media-error" role="alert"><h2>This image could not be decoded.</h2><p>The file downloaded but the browser cannot read it as an image. Export it again, or open it outside Dossier.</p><button type="button" className="primary" onClick={()=>setDecodeFailed(false)}>Try again</button></div>
      :<img src={url} alt={title} onError={()=>setDecodeFailed(true)}/>}
  </div>;
  return <iframe className="pdf-frame" title={title} src={url}/>;
}

/** A DOCX is shown through Word, and how faithful that is depends on the route the
 *  engine picked. `design.md:165` asks for the class to be on screen before anyone
 *  clicks, so it is read from the engine rather than assumed. */
function DocxRender({tab,onRetry}:{tab:Tab;onRetry:()=>void}):ReactNode{
  const routes=useLoad(()=>api.convertRoutes(tab.rel),[tab.rel]);
  /* The URL is resolved before the frame renders: `api.render` asks for the cached
     PDF and builds it on a 409, which is a request, not a string. */
  const source=useLoad(()=>api.render(tab.rel),[tab.rel]);
  const fidelity=routes.state.status==='ready'
    ?routes.state.data.routes.find(route=>route.target==='.pdf')?.fidelity
    :undefined;
  const caption=<p className="render-caption">
    {`Server render${fidelity?` · ${fidelity} fidelity`:' · fidelity unknown'}`}
  </p>;
  if(source.state.status!=='ready')return <>{caption}<Loading what="the Word render"/></>;
  return <>{caption}
    <MediaPane kind="frame" title={`${tab.rel} rendered`} url={source.state.data} onRetry={onRetry}/>
  </>;
}

export default function Viewer({tab,onChange,onRetry,onMode}:{tab:Tab;onChange:(value:string)=>void;onRetry:()=>void;onMode?:(mode:'preview'|'edit')=>void}):ReactNode{
  const ext=extOf(tab.rel);
  const [mode,setMode]=useState<'preview'|'edit'>('preview');

  useEffect(()=>{setMode('preview');onMode?.('preview')},[tab.rel]);

  /* A failed read has its own state: no buffer, no editor, nothing ⌘S can write over. */
  if(tab.error)return <div className="empty-panel" role="alert">
    <h2>{tab.error.title}</h2>
    <p>{tab.error.next}</p>
    {tab.error.raw&&<pre className="action-log">{tab.error.raw}</pre>}
    <p><button type="button" className="primary" onClick={onRetry}>Retry the read</button></p>
  </div>;

  if(isImage(ext))return <MediaPane kind="image" title={tab.rel} url={api.raw(tab.rel)} onRetry={onRetry}/>;
  if(ext==='pdf')return <MediaPane kind="frame" isPdf title={tab.rel} url={api.raw(tab.rel)} onRetry={onRetry}/>;
  if(ext==='docx')return <DocxRender tab={tab} onRetry={onRetry}/>;

  if(tab.content===undefined)return <Loading what={tab.rel}/>;

  const toolbar=<div className="markdown-toolbar" role="tablist" aria-label="Pane mode">
    <button type="button" role="tab" id="viewer-tab-preview" aria-controls="viewer-panel"
      aria-selected={mode==='preview'} className={`chip ${mode==='preview'?'active':''}`} onClick={()=>{setMode('preview');onMode?.('preview')}}>Preview</button>
    <button type="button" role="tab" id="viewer-tab-edit" aria-controls="viewer-panel"
      aria-selected={mode==='edit'} className={`chip ${mode==='edit'?'active':''}`} onClick={()=>{setMode('edit');onMode?.('edit')}}>Edit</button>
  </div>;

  /* Both chips name `viewer-panel`; that id has to exist or the pointer is a lie. */
  const panel=<div id="viewer-panel" role="tabpanel" aria-labelledby={mode==='preview'?'viewer-tab-preview':'viewer-tab-edit'} className="viewer-panel"/>;
  if(ext==='csv'){
    if(mode==='edit')return <>{toolbar}<div id="viewer-panel" role="tabpanel" aria-labelledby="viewer-tab-edit"><CodeEditor tab={tab} onChange={onChange}/></div></>;
    return <>{toolbar}<div id="viewer-panel" role="tabpanel" aria-labelledby="viewer-tab-preview"><CsvGrid text={tab.content}/></div></>;
  }
  if(ext==='md'){
    if(mode==='edit')return <>{toolbar}<div id="viewer-panel" role="tabpanel" aria-labelledby="viewer-tab-edit"><CodeEditor tab={tab} onChange={onChange}/></div></>;
    const {front,body}=splitFrontMatter(tab.content);
    return <>{toolbar}<article id="viewer-panel" role="tabpanel" aria-labelledby="viewer-tab-preview" className="doc-prose">
      {front&&<pre className="front-matter">{front}</pre>}
      <MarkdownDoc text={body} base={dirOf(tab.rel)}/>
    </article></>;
  }
  return <CodeEditor tab={tab} onChange={onChange}/>;
}
