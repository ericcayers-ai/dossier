import {Suspense,lazy,useCallback,useEffect,useMemo,useRef,useState} from 'react';
import type {ReactNode} from 'react';
import {ApiError,api,fault,isConflict} from './lib/api';
import type {Bundle,FileNode} from './lib/api';
import {baseName,extOf,flatten,formatAge,formatBytes,isBinary} from './lib/files';
import {count} from './lib/copy';
import {clearDraft,clockTime,preferredTheme,readDraft,storeTheme,writeDraft} from './lib/session';
import type {Tab} from './lib/session';
import {useLoad} from './lib/useLoad';
import type {Loadable} from './lib/useLoad';
/* The shell is eager; the surfaces are not. `Viewer` alone pulls the whole CodeMirror
   editor, which used to ride in the first bundle and made the first paint wait for an
   editor the visitor had not opened yet. Each pane is its own chunk now, fetched when
   its tab is chosen, and one Suspense boundary holds the space while it arrives. */
import Explorer from './panes/Explorer';
import BundleRail from './panes/BundleRail';
const Viewer=lazy(()=>import('./panes/Viewer'));
const Palette=lazy(()=>import('./panes/Palette'));
const JobsPane=lazy(()=>import('./panes/JobsPane'));
const IdentityPane=lazy(()=>import('./panes/IdentityPane'));
const AuditPane=lazy(()=>import('./panes/AuditPane'));
const TrashPane=lazy(()=>import('./panes/TrashPane'));
const SyncPane=lazy(()=>import('./panes/SyncPane'));
const VerifyPane=lazy(()=>import('./panes/VerifyPane'));
const CapturePane=lazy(()=>import('./panes/CapturePane'));
const BuildPane=lazy(()=>import('./panes/BuildPane'));
const AgentPane=lazy(()=>import('./panes/AgentPane'));
const PanelPane=lazy(()=>import('./panes/PanelPane'));
const TrajectoryPane=lazy(()=>import('./trajectory/TrajectoryPane'));
const StartPane=lazy(()=>import('./panes/StartPane'));

/** One skeleton for every pane boundary: same rhythm as `Loading`, no h1 (the arriving
 *  pane owns the heading) and `aria-busy` so a screen reader is told to wait. */
function PaneSkeleton():ReactNode{
  return <div className="loading" role="status" aria-busy="true" aria-label="Opening this pane">
    <span className="sr-only">Opening this pane…</span>
    <span className="skeleton"/><span className="skeleton"/><span className="skeleton"/>
  </div>;
}

type Pane='start'|'files'|'jobs'|'identity'|'capture'|'build'|'audit'|'trash'|'sync'|'agent'|'verify'|'trajectory'|'panel';
type Area='start'|'files'|'search'|'papers'|'housekeeping'|'agent';
type Pending={kind:'open'|'close';rel:string};
/** A slide-over is only a slide-over below its breakpoint; above it the panel is
 *  always on screen. The panel is `inert` while off-canvas, so a closed drawer is
 *  removed from the tab order and the accessibility tree rather than merely moved. */
function useMediaQuery(query:string):boolean{
  const [matches,setMatches]=useState(()=>typeof window!=='undefined'&&window.matchMedia(query).matches);
  useEffect(()=>{
    const list=window.matchMedia(query);
    const update=()=>setMatches(list.matches);
    update();
    list.addEventListener('change',update);
    return ()=>list.removeEventListener('change',update);
  },[query]);
  return matches;
}

type Conflict={rel:string};
type SaveState={status:'idle'|'saving'|'saved'|'failed';at?:number;message?:string};

/* Six areas, at most three panes each. Eleven flat buttons in one strip clipped
   at 1100 px and gave the topbar no hierarchy; an area is a place in the app, a
   pane is a tab inside it. Only the active area's panes are mounted.

   `Start` comes first because a job search begins with a question, not a file
   browser: it is the only new destination this pass added, and every other area
   and pane below it is unchanged. */
const AREAS:Array<{id:Area;label:string;panes:Array<{id:Pane;label:string}>}>=[
  {id:'start',label:'Start',panes:[{id:'start',label:'Start here'}]},
  {id:'files',label:'Files',panes:[{id:'files',label:'Folder'}]},
  {id:'search',label:'Search',panes:[{id:'capture',label:'Capture'},{id:'jobs',label:'Jobs'},{id:'identity',label:'Identity'}]},
  {id:'papers',label:'Papers',panes:[{id:'build',label:'Build'},{id:'verify',label:'Verify'}]},
  {id:'housekeeping',label:'Housekeeping',panes:[{id:'audit',label:'Audit'},{id:'trash',label:'Trash'},{id:'sync',label:'Sync'}]},
  {id:'agent',label:'Agent',panes:[{id:'agent',label:'Loop'},{id:'trajectory',label:'Opportunity'},{id:'panel',label:'Panel'}]},
];
/** The palette's places: eleven panes, each named with the area it lives under. */
const PLACES=AREAS.flatMap(area=>area.panes.map(pane=>({id:pane.id,label:pane.label,area:area.label})));
const PANE_AREA:Record<Pane,Area>=(()=>{
  const map={} as Record<Pane,Area>;
  AREAS.forEach(area=>area.panes.forEach(item=>{map[item.id]=area.id}));
  return map;
})();

/* A pane is a place, so it gets an address. `#/search/jobs` survives a reload, a
   bookmark and the back button; before this the app always opened on Folder and a
   reload silently discarded where the person was. */
const PANE_IDS=new Set<Pane>(Object.keys(PANE_AREA) as Pane[]);
function paneFromHash(hash:string):Pane|null{
  const parts=hash.replace(/^#\/?/,'').split('/').filter(Boolean);
  if(!parts.length)return null;
  const candidate=(parts.length>1?parts[1]:parts[0]) as Pane;
  if(PANE_IDS.has(candidate))return candidate;
  const byArea=AREAS.find(area=>area.id===parts[0]);
  return byArea?byArea.panes[0].id:null;
}
function hashFor(pane:Pane):string{return `#/${PANE_AREA[pane]}/${pane}`}

const SHORTCUTS:[string,string][]=[
  ['⌘K','Search names and full text'],
  ['⌘S','Save the open document'],
  ['⌘W','Close the open tab'],
  ['⌘\\','Collapse or show the file list'],
  ['⌘/','Collapse or show the files related to the open one'],
  ['Esc','Close the palette, dialog or conflict banner'],
  ['?','Show this list'],
];

export default function App():ReactNode{
  const [theme,setTheme]=useState<'light'|'dark'>(()=>preferredTheme());
  const [tabs,setTabs]=useState<Tab[]>([]);
  const [selected,setSelected]=useState('');
  const [palette,setPalette]=useState(false);
  const [pane,setPane]=useState<Pane>(()=>paneFromHash(window.location.hash)??'start');
  const area=PANE_AREA[pane];

  /* The address follows the pane, and the browser's own back/forward moves between
     panes. `pushState` (not `replaceState`) is what makes back mean "the previous
     pane" instead of "leave the app". */
  const goToPane=useCallback((next:Pane,mode:'push'|'replace'='push')=>{
    setPane(next);
    const want=hashFor(next);
    if(window.location.hash===want)return;
    if(mode==='replace')window.history.replaceState(null,'',want);
    else window.history.pushState(null,'',want);
  },[]);
  /* The address changes with the pane, so the tab label does too. One route is not
     one document here: `#/search/jobs` and `#/papers/verify` are different places. */
  useEffect(()=>{
    const label=AREAS.flatMap(area=>area.panes).find(item=>item.id===pane)?.label??'Dossier';
    document.title=`${label} | Dossier`;
  },[pane]);
  useEffect(()=>{
    const sync=()=>{const next=paneFromHash(window.location.hash);if(next)setPane(next)};
    if(!window.location.hash)window.history.replaceState(null,'',hashFor(paneFromHash('')??'start'));
    window.addEventListener('popstate',sync);
    window.addEventListener('hashchange',sync);
    return()=>{window.removeEventListener('popstate',sync);window.removeEventListener('hashchange',sync)};
  },[]);
  const narrowExplorer=useMediaQuery('(max-width: 700px)');
  const narrowRail=useMediaQuery('(max-width: 1000px)');
  // The theme must live on <html>, not only on `.app`: `body` sets `color:
  // var(--ink)`, and an inherited value is not re-resolved inside a subtree, so a
  // dark `.app` kept the light ink it inherited from `body`. Setting the attribute
  // on the root is what makes every inherited token dark.
  useEffect(()=>{
    /* One frame with transitions off: otherwise the swap animates every colour on
       screen at once and the page appears to slide from light to dark. */
    document.documentElement.classList.add('theme-swapping');
    document.documentElement.dataset.theme=theme;
    requestAnimationFrame(()=>document.documentElement.classList.remove('theme-swapping'));
    storeTheme(theme);
    // The browser paints the address bar / window chrome from this meta, so it has to
    // follow the same switch the app just took. Values are the resolved --ground.
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme==='dark'?'#15191e':'#f2f5f9');
  },[theme]);
  /* An edit that exists only in React state is lost by Ctrl+W, Ctrl+R or a closed
     tab, and the app's own promise is that nothing a person typed disappears
     silently. The in-app confirm covers switching documents; this covers leaving
     the page. */
  useEffect(()=>{
    if(!tabs.some(tab=>tab.dirty))return;
    const warn=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''};
    window.addEventListener('beforeunload',warn);
    return()=>window.removeEventListener('beforeunload',warn);
  },[tabs]);
  const areaPanes=AREAS.find(item=>item.id===area)?.panes??[];
  const selectArea=(next:Area)=>{const first=AREAS.find(item=>item.id===next)?.panes[0];if(first)goToPane(first.id)};
  const [hideExplorer,setHideExplorer]=useState(false);
  const [hideRail,setHideRail]=useState(false);
  const [railOpen,setRailOpen]=useState(false);
  const [explorerOpen,setExplorerOpen]=useState(false);
  const [conflict,setConflict]=useState<Conflict|null>(null);
  const [pending,setPending]=useState<Pending|null>(null);
  const [draftOffer,setDraftOffer]=useState<{rel:string;content:string}|null>(null);
  const [saveState,setSaveState]=useState<SaveState>({status:'idle'});
  const [announcement,setAnnouncement]=useState('');
  const [help,setHelp]=useState(false);
  /** Which mode the open document is in, so the status line describes the truth. */
  const [viewerMode,setViewerMode]=useState<'preview'|'edit'>('preview');
  const helpRef=useRef<HTMLDivElement|null>(null);
  const helpReturn=useRef<HTMLElement|null>(null);
  /* A dialog that leaves focus on the page behind it is a dialog in name only. The
     open takes focus, the close hands it back to the control that asked. */
  useEffect(()=>{
    if(help){
      helpReturn.current=document.activeElement as HTMLElement|null;
      requestAnimationFrame(()=>helpRef.current?.querySelector<HTMLElement>('button')?.focus());
    }
  },[help]);
  const helpClose=()=>{requestAnimationFrame(()=>helpReturn.current?.focus())};
  const [pulse,setPulse]=useState(false);

  const tabsRef=useRef<Tab[]>([]);
  tabsRef.current=tabs;
  const selectedRef=useRef('');
  selectedRef.current=selected;
  const openTicket=useRef(0);
  const draftTimers=useRef(new Map<string,number>());
  const searchRef=useRef<HTMLButtonElement>(null);
  const staleCount=useRef(0);

  const tree=useLoad<FileNode[]>(()=>api.fileTree(),[]);
  const health=useLoad(()=>api.health(),[]);
  const online=health.state.status==='ready';

  const bundle=useLoad<Bundle|null>(()=>selected?api.bundle(selected):Promise.resolve(null),[selected]);
  const bundleState:Loadable<Bundle>=useMemo(()=>{
    if(!selected)return {status:'ready',data:{members:[],stale:[]}};
    if(bundle.state.status==='ready')return {status:'ready',data:bundle.state.data??{members:[],stale:[]}};
    return bundle.state;
  },[bundle.state,selected]);

  const announce=useCallback((message:string)=>setAnnouncement(message),[]);
  const activeTab=tabs.find(tab=>tab.rel===selected)??null;

  /* -- open / load ------------------------------------------------------- */

  const load=useCallback(async(rel:string,options:{restoreDraft?:boolean}={})=>{
    const ticket=openTicket.current+=1;
    setSelected(rel);
    setConflict(null);
    /* Opening a file must bring the document forward. Before this, clicking a
       file in the Explorer or the Bundle Rail while another pane was active
       fetched it, added the tab, and rendered nothing. */
    setPane('files');
    setTabs(current=>current.some(tab=>tab.rel===rel)?current:[...current,{rel,loaded:false}]);
    if(isBinary(rel)){
      setTabs(current=>current.map(tab=>tab.rel===rel?{...tab,loaded:true}:tab));
      return;
    }
    try{
      const data=await api.file(rel);
      if(ticket!==openTicket.current)return;
      setTabs(current=>current.map(tab=>tab.rel===rel?{...tab,content:data.content,stamp:data.stamp,loaded:true,dirty:false,error:undefined}:tab));
      const draft=readDraft(rel);
      if(!options.restoreDraft&&draft!==null&&draft!==data.content)setDraftOffer({rel,content:draft});
      else if(options.restoreDraft&&draft!==null)setTabs(current=>current.map(tab=>tab.rel===rel?{...tab,content:draft,dirty:true}:tab));
    }catch(error){
      if(ticket!==openTicket.current)return;
      const {title,next}=fault(error,`Reading ${rel}`);
      /* Only a server-supplied detail is worth showing; a raw JS exception
         string ("TypeError: Failed to fetch") is not. */
      const raw=error instanceof ApiError&&error.detail?error.detail:undefined;
      /* B2: the failure is its own state. No buffer, no editor, nothing to save. */
      setTabs(current=>current.map(tab=>tab.rel===rel?{...tab,content:undefined,stamp:undefined,loaded:true,dirty:false,error:{title,next,raw}}:tab));
    }
  },[],);

  const requestOpen=useCallback((rel:string)=>{
    if(rel===selectedRef.current)return;
    const current=tabsRef.current.find(tab=>tab.rel===selectedRef.current);
    if(current?.dirty){setPending({kind:'open',rel});return}
    void load(rel);
  },[load]);

  const closeTab=useCallback((rel:string)=>{
    const next=tabsRef.current.filter(tab=>tab.rel!==rel);
    setTabs(next);
    clearDraft(rel);
    if(selectedRef.current===rel)setSelected(next.length?next[next.length-1].rel:'');
  },[],);

  const requestClose=useCallback((rel:string)=>{
    const current=tabsRef.current.find(tab=>tab.rel===rel);
    if(current?.dirty){setPending({kind:'close',rel});return}
    closeTab(rel);
  },[closeTab]);

  /* -- save (B1: keep the returned stamp; 409 becomes a real choice) ------ */

  const save=useCallback(async(rel:string,options:{withoutPrecondition?:boolean}={}):Promise<boolean>=>{
    const tab=tabsRef.current.find(item=>item.rel===rel);
    if(!tab)return false;
    if(tab.error||tab.content===undefined){
      announce('Nothing to save: this tab has no editable buffer.');
      return false;
    }
    setSaveState({status:'saving'});
    try{
      const result=await api.save(rel,tab.content,options.withoutPrecondition?undefined:tab.stamp);
      const stamp=result?.stamp??tab.stamp;
      setTabs(current=>current.map(item=>item.rel===rel?{...item,dirty:false,stamp,savedAt:Date.now(),error:undefined}:item));
      clearDraft(rel);
      setSaveState({status:'saved',at:Date.now()});
      setConflict(null);
      announce(`Saved ${baseName(rel)}`);
      return true;
    }catch(error){
      if(isConflict(error)){
        setConflict({rel});
        setSaveState({status:'idle'});
        announce(`Conflict on ${baseName(rel)}: the file changed on disk.`);
        return false;
      }
      const {title,next}=fault(error,'Saving this file');
      setSaveState({status:'failed',message:`${title} ${next}`});
      announce(`Save failed. ${title}`);
      return false;
    }
  },[]);

  const keepMine=useCallback(async(rel:string)=>{
    const tab=tabsRef.current.find(item=>item.rel===rel);
    if(!tab||tab.content===undefined)return;
    try{
      /* A fresh stamp satisfies either backend rule (stamped compare, or no
         precondition at all) and still refuses to clobber a change we have not
         seen. If the file vanished, the save simply becomes a create. */
      const fresh=await api.file(rel);
      await api.save(rel,tab.content,fresh.stamp);
      setTabs(current=>current.map(item=>item.rel===rel?{...item,dirty:false,stamp:fresh.stamp,savedAt:Date.now()}:item));
      clearDraft(rel);
      setConflict(null);
      setSaveState({status:'saved',at:Date.now()});
      announce(`Saved ${baseName(rel)} over the version on disk. The previous copy is in .dossier/trash.`);
      bundle.reload();
    }catch(error){
      if(error instanceof ApiError&&error.status===404){
        await save(rel,{withoutPrecondition:true});
        return;
      }
      const {title,next}=fault(error,'Overwriting with your version');
      setSaveState({status:'failed',message:`${title} ${next}`});
    }
  },[bundle,save]);

  const reloadTheirs=useCallback(async(rel:string)=>{
    openTicket.current+=1;
    const ticket=openTicket.current;
    try{
      const data=await api.file(rel);
      if(ticket!==openTicket.current)return;
      setTabs(current=>current.map(item=>item.rel===rel?{...item,content:data.content,stamp:data.stamp,loaded:true,dirty:false,error:undefined}:item));
      clearDraft(rel);
      setConflict(null);
      announce(`Reloaded ${baseName(rel)} from disk. Your buffer was discarded.`);
    }catch(error){
      const {title,next}=fault(error,'Reloading from disk');
      setSaveState({status:'failed',message:`${title} ${next}`});
    }
  },[]);

  /* -- drafts, theme, unload guard --------------------------------------- */

  const onEdit=useCallback((rel:string,content:string)=>{
    setTabs(current=>current.map(tab=>tab.rel===rel?{...tab,content,dirty:true}:tab));
    const existing=draftTimers.current.get(rel);
    if(existing)window.clearTimeout(existing);
    draftTimers.current.set(rel,window.setTimeout(()=>writeDraft(rel,content),700));
  },[]);

  const dirty=tabs.some(tab=>tab.dirty);
  useEffect(()=>{
    storeTheme(theme);
  },[theme]);

  useEffect(()=>{
    if(!dirty)return;
    const guard=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''};
    window.addEventListener('beforeunload',guard);
    return()=>window.removeEventListener('beforeunload',guard);
  },[dirty]);

  /* -- file events (B7: /api/events) ------------------------------------ */

  useEffect(()=>{
    if(!online)return;
    let timer=0;
    const source=new EventSource(api.eventsUrl());
    source.onmessage=event=>{
      let payload:{type?:string;path?:string};
      try{payload=JSON.parse(event.data) as {type?:string;path?:string}}
      catch{return}
      if(!payload.type||payload.type==='connected'||payload.type==='closed')return;
      window.clearTimeout(timer);
      timer=window.setTimeout(()=>{
        tree.reload();
        const current=selectedRef.current;
        if(current&&payload.path&&String(payload.path).split(/[\\/]/).pop()===baseName(current))bundle.reload();
      },600);
    };
    return()=>{window.clearTimeout(timer);source.close()};
    // selectedRef keeps the stream alive across selection changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[online]);

  /* One 400ms amber pulse when a set gains a stale member (DESIGN.md:101). */
  useEffect(()=>{
    const count=bundleState.status==='ready'?(bundleState.data.stale?.length??0):0;
    if(count>staleCount.current){
      setPulse(true);
      const timer=window.setTimeout(()=>setPulse(false),500);
      staleCount.current=count;
      return()=>window.clearTimeout(timer);
    }
    staleCount.current=count;
  },[bundleState]);

  /* -- shortcuts --------------------------------------------------------- */

  const requestCloseSelected=useCallback(()=>{if(selectedRef.current)requestClose(selectedRef.current)},[requestClose]);

  useEffect(()=>{
    const handler=(event:KeyboardEvent)=>{
      const meta=event.metaKey||event.ctrlKey;
      const key=event.key.toLowerCase();
      if(meta&&key==='k'){event.preventDefault();setPalette(true);return}
      if(meta&&event.key==='\\'){event.preventDefault();setHideExplorer(value=>!value);setExplorerOpen(value=>!value);return}
      if(meta&&event.key==='/'){event.preventDefault();setHideRail(value=>!value);setRailOpen(value=>!value);return}
      if(meta&&key==='s'){event.preventDefault();if(selectedRef.current)void save(selectedRef.current);return}
      if(meta&&key==='w'){event.preventDefault();requestCloseSelected();return}
      if(event.key==='Escape'){
        setPalette(false);setHelp(false);setConflict(null);setPending(null);setDraftOffer(null);
        return;
      }
      if(!meta&&event.key==='?'&&!/^(input|textarea|select)$/i.test((event.target as HTMLElement)?.tagName??'')){event.preventDefault();setHelp(value=>!value)}
    };
    window.addEventListener('keydown',handler);
    return()=>window.removeEventListener('keydown',handler);
  },[save,requestCloseSelected]);

  /* -- tab keyboard navigation ------------------------------------------ */

  const onTabKeyDown=(event:React.KeyboardEvent<HTMLDivElement>,index:number)=>{
    if(event.key!=='ArrowRight'&&event.key!=='ArrowLeft')return;
    event.preventDefault();
    if(tabs.length===0)return;
    const next=event.key==='ArrowRight'?(index+1)%tabs.length:(index-1+tabs.length)%tabs.length;
    const rel=tabs[next].rel;
    if(rel===selected)return;
    const current=tabs[index];
    if(current?.dirty)setPending({kind:'open',rel});
    else void load(rel);
  };

  /* -- derived ----------------------------------------------------------- */

  const node=useMemo(()=>tree.state.status==='ready'?flattenOnce(tree.state.data,selected):null,[tree.state,selected]);
  /* Which .docx files exist, so Build can offer them instead of a guessed path. */
  const docxFiles=useMemo(()=>tree.state.status==='ready'
    ?flatten(tree.state.data).map(item=>item.rel).filter(rel=>extOf(rel)==='docx').sort()
    :[],[tree.state]);
  /* Documents a reviewer can actually read, for the panel's two pickers. */
  const readableFiles=useMemo(()=>tree.state.status==='ready'
    ?flatten(tree.state.data).map(item=>item.rel)
      .filter(rel=>['md','txt','docx','pdf'].includes(extOf(rel))).sort().slice(0,400)
    :[],[tree.state]);
  const saveLine=saveState.status==='saving'?'Saving…'
    :saveState.status==='saved'?`Saved ${clockTime(saveState.at)}`
    :saveState.status==='failed'?saveState.message??'Save failed'
    :dirty?'Unsaved changes':'';
  /* What can be typed into, said out loud: `.md` opens as a reading pane and
     `.csv` as a grid, and neither is editable until Edit is pressed. */
  const editHint=!activeTab?''
    :activeTab.error?'Read failed, read-only'
    :isBinary(activeTab.rel)?`${extOf(activeTab.rel)}: read-only view`
    :extOf(activeTab.rel)==='md'?(viewerMode==='edit'?'Editing. Press ⌘S to save.':'Markdown preview. Press Edit to type.')
    :extOf(activeTab.rel)==='csv'?(viewerMode==='edit'?'Editing. Press ⌘S to save.':'CSV grid. Press Edit to type.')
    :'Editable text, ⌘S saves';

  return <div className={`app ${hideExplorer?'hide-explorer':''} ${hideRail?'hide-rail':''} ${railOpen?'rail-open':''} ${explorerOpen?'explorer-open':''}`} data-theme={theme}>
    <a className="skip-link" href="#main-content">Skip to the open document</a>
    <header className="topbar">
      <div className="topbar-main">
      <span className="brand">Dossier</span>
      <span className="crumb">
        <span className="crumb-path" translate="no" title={selected||undefined}>{selected?selected.split('/').pop():'Open a file to begin'}</span>
        {node?.size!==undefined&&<span className="crumb-meta">{formatBytes(node.size)}</span>}
        {node?.mtime_ns!==undefined&&<span className="crumb-meta">{`modified ${formatAge(node.mtime_ns)}`}</span>}
      </span>
      <button type="button" className="search-trigger" ref={searchRef} aria-label="Search files" onClick={()=>setPalette(true)}><span>Search files</span><span className="kbd">⌘K</span></button>
      <nav className="area-nav" aria-label="Workspace areas">
        {AREAS.map(item=><button
          type="button"
          key={item.id}
          className={`area-btn ${area===item.id?'active':''}`}
          aria-current={area===item.id?'page':undefined}
          onClick={()=>{selectArea(item.id);setRailOpen(false);setExplorerOpen(false)}}
        >{item.label}</button>)}
      </nav>
      <button type="button" className="icon-btn" aria-label={`Use ${theme==='light'?'dark':'light'} theme`} onClick={()=>setTheme(theme==='light'?'dark':'light')}>{theme==='light'?'◐':'○'}</button>
      </div>
      <nav className="pane-nav" aria-label={`${AREAS.find(item=>item.id===area)?.label??area} panes`}>
        {areaPanes.map(item=><button
          type="button"
          key={item.id}
          className={`pane-btn ${pane===item.id?'active':''}`}
          aria-current={pane===item.id?'page':undefined}
          onClick={()=>{goToPane(item.id);setRailOpen(false);setExplorerOpen(false)}}
        >{item.label}</button>)}
        <span className="grow"/>
        <button type="button" className="icon-btn explorer-toggle" aria-expanded={explorerOpen} aria-label="Files: show or hide the file list" onClick={()=>setExplorerOpen(value=>!value)}>File list</button>
        <button type="button" className="icon-btn rail-toggle" aria-expanded={railOpen} aria-label="Related files: show or hide the panel of files that belong with the open one" onClick={()=>setRailOpen(value=>!value)}>Related</button>
      </nav>
    </header>

    <Explorer tree={tree.state} selected={selected} onSelect={requestOpen} onRetry={tree.reload} inert={narrowExplorer&&!explorerOpen}/>

    <main className="panel center" id="main-content" tabIndex={-1}>
      {/* A tablist with no tab inside it fails aria-required-children, and an empty
          document strip is not a tab set. The role appears with the first tab. */}
      {/* A document strip with nothing in it is a row of grey words about a document
          that does not exist. On the start screen, with no tabs, it is simply absent. */}
      {(pane!=='start'||tabs.length>0)&&<div className="tabs" role={tabs.length?'tablist':undefined} aria-label={tabs.length?'Open documents':undefined}>
        {tabs.map((tab,index)=><div
          key={tab.rel}
          role="tab"
          aria-selected={tab.rel===selected}
          aria-label={`${baseName(tab.rel)}${tab.dirty?' — unsaved changes':''}`}
          aria-controls="document-view"
          tabIndex={tab.rel===selected?0:-1}
          className={`tab ${tab.rel===selected?'active':''}`}
          onKeyDown={event=>onTabKeyDown(event,index)}
          onClick={()=>{if(tab.rel!==selected)requestOpen(tab.rel)}}
        >
          <span className="tab-label">{baseName(tab.rel)}</span>
          {tab.dirty&&<span className="tab-dirty" aria-hidden="true">•</span>}
          <button type="button" className="tab-close" aria-label={`Close ${baseName(tab.rel)}`} onClick={event=>{event.stopPropagation();requestClose(tab.rel)}}>×</button>
        </div>)}
        {tabs.length===0&&<span className="tab-placeholder">No document open</span>}
      </div>}

      <div className="viewer" id="document-view" role={tabs.length?'tabpanel':undefined} aria-label={tabs.length?'Open document':undefined}>
        {conflict&&<div className="confirm" role="alertdialog" aria-label="File changed on disk">
          <b>{`${baseName(conflict.rel)} changed on disk since you opened it.`}</b>
          <span>Keep your version (the current file is copied to .dossier/trash first), or reload theirs and lose your edits.</span>
          <button type="button" className="primary" onClick={()=>void keepMine(conflict.rel)}>Keep mine</button>
          <button type="button" onClick={()=>void reloadTheirs(conflict.rel)}>Reload theirs</button>
          <button type="button" onClick={()=>setConflict(null)}>Decide later</button>
        </div>}
        {saveState.status==='failed'&&<div className="confirm" role="alert">{saveState.message}<button type="button" onClick={()=>setSaveState({status:'idle'})}>Dismiss</button></div>}

        <Suspense fallback={<PaneSkeleton/>}>
        {pane==='start'?<StartPane onGo={next=>goToPane(next as Pane)}/>
          :pane==='files'
          ?activeTab
            ?<>
              {draftOffer?.rel===activeTab.rel&&<div className="confirm" role="alert">
                <b>Unsaved edits from earlier in this session are stored for {baseName(draftOffer.rel)}.</b>
                <button type="button" className="primary" onClick={()=>{const offer=draftOffer;setDraftOffer(null);if(offer)void load(offer.rel,{restoreDraft:true})}}>Restore unsaved edits</button>
                <button type="button" onClick={()=>{clearDraft(draftOffer.rel);setDraftOffer(null)}}>Discard the draft</button>
              </div>}
              {activeTab.error
                ?<Viewer tab={activeTab} onChange={()=>undefined} onRetry={()=>void load(activeTab.rel,{restoreDraft:false})}/>
                :<Viewer tab={activeTab} onChange={content=>onEdit(activeTab.rel,content)} onRetry={()=>void load(activeTab.rel)} onMode={setViewerMode}/>}
            </>
            :<div className="welcome">
              <h1>Your folder</h1>
              <p className="pane-purpose">Everything Dossier reads is here. Pick a file on the left to open it, or use Start here for the four steps of an application.</p>
              {docxFiles.length===0
                ?<p className="notice">No <code>.docx</code> in this folder yet. Add the resume you send to employers here, then Start here walks through the rest.</p>
                :<p className="sync-note">{`${count(docxFiles.length,'.docx')} here: ${docxFiles.slice(0,4).join(', ')}`}</p>}
            </div>
          :pane==='jobs'?<JobsPane/>
          :pane==='identity'?<IdentityPane/>
          :pane==='capture'?<CapturePane/>
          :pane==='build'?<BuildPane docx={docxFiles}/>
          :pane==='audit'?<AuditPane/>
          :pane==='trash'?<TrashPane onRestored={rel=>{tree.reload();announce(`Restored ${baseName(rel)}.`)}}/>
          :pane==='sync'?<SyncPane/>
          :pane==='panel'?<PanelPane candidate={selected} files={readableFiles}/>
          :pane==='agent'?<AgentPane/>
          :pane==='verify'?<VerifyPane candidate={selected} files={readableFiles}/>
          :<TrajectoryPane/>}
        </Suspense>
      </div>
    </main>

    <BundleRail bundle={bundleState} selected={selected} onOpen={requestOpen} onRetry={bundle.reload} onChanged={()=>{tree.reload();bundle.reload()}} pulse={pulse} inert={narrowRail&&!railOpen}/>

    {(railOpen||explorerOpen)&&<button type="button" className="scrim" aria-label="Close the side panel" onClick={()=>{setRailOpen(false);setExplorerOpen(false)}}/>}

    <footer className="status">
      <span className={online?'':'offline'}>{online?'API ready':health.state.status==='loading'?'Checking the API…':'API unavailable — showing the local shell'}</span>
      {!online&&health.state.status==='failed'&&<button type="button" onClick={()=>{health.reload();tree.reload()}}>Retry</button>}
      <span className="grow"/>
      <span className={saveState.status==='failed'?'stale':''} role="status" aria-live="polite">{saveLine}</span>
      {editHint&&<span>{editHint}</span>}
      {selected&&<span>{`${selected}${activeTab?.dirty?' — unsaved':''}`}</span>}
      <button type="button" className="status-btn" aria-pressed={hideExplorer} onClick={()=>{setHideExplorer(value=>!value);setExplorerOpen(value=>!value)}}>{'⌘\\ file list'}</button>
      <button type="button" className="status-btn" aria-pressed={hideRail} onClick={()=>{setHideRail(value=>!value);setRailOpen(value=>!value)}}>{'⌘/ related files'}</button>
      <button type="button" onClick={()=>setHelp(true)} aria-label="Keyboard shortcuts">?</button>
    </footer>

    <p className="sr-only" role="status" aria-live="polite">{announcement}</p>

    {palette&&<Suspense fallback={null}><Palette
      onClose={()=>{setPalette(false);searchRef.current?.focus()}}
      onOpen={rel=>void load(rel)}
      onGo={next=>{setPalette(false);goToPane(next as Pane)}}
      places={PLACES}/></Suspense>}

    {help&&<div className="palette-backdrop" onMouseDown={event=>{if(event.target===event.currentTarget)setHelp(false)}}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" ref={helpRef} onKeyDown={event=>{if(event.key==='Escape'){setHelp(false);helpClose()}else if(event.key==='Tab'){const focusable=event.currentTarget.querySelectorAll<HTMLElement>('button');const first=focusable[0];const last=focusable[focusable.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}}}}>
        <table className="data-table"><thead><tr><th>Keys</th><th>Action</th></tr></thead>
          <tbody>{SHORTCUTS.map(([keys,what])=><tr key={keys}><td><b>{keys}</b></td><td>{what}</td></tr>)}</tbody></table>
        <div className="button-row"><button type="button" className="primary" onClick={()=>{setHelp(false);helpClose()}}>Close the shortcuts</button></div>
      </div>
    </div>}

    {pending&&<div className="palette-backdrop" onMouseDown={event=>{if(event.target===event.currentTarget)setPending(null)}}>
      <div className="palette" role="alertdialog" aria-modal="true" aria-label="Unsaved changes">
        <div className="confirm">
          <b>{`${baseName(pending.rel)} has unsaved edits.`}</b>
          <span>Save them before {pending.kind==='open'?'opening the other file':'closing this tab'}, or discard them.</span>
          <button type="button" className="primary" onClick={()=>{const target=pending;setPending(null);void save(target.rel).then(ok=>{if(!ok)return;if(target.kind==='open'){void load(target.rel)}else{closeTab(target.rel)}})}}>Save</button>
          <button type="button" onClick={()=>{const target=pending;setPending(null);clearDraft(target.rel);if(target.kind==='open'){void load(target.rel)}else{closeTab(target.rel)}}}>Discard</button>
          <button type="button" onClick={()=>setPending(null)}>Keep editing</button>
        </div>
      </div>
    </div>}
  </div>;
}

function flattenOnce(nodes:FileNode[],rel:string):FileNode|null{
  const stack=[...nodes];
  while(stack.length){
    const node=stack.pop();
    if(!node)continue;
    if(node.rel===rel)return node;
    if(node.children)stack.push(...node.children);
  }
  return null;
}

/* Exported so the area/pane map and the shortcut table can be asserted by grep
   rather than by memory. */
export {AREAS,SHORTCUTS};
