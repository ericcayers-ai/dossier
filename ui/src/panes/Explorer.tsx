import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import type {KeyboardEvent,ReactNode} from 'react';
import type {FileNode} from '../lib/api';
import type {Loadable} from '../lib/useLoad';
import {extOf,flatten,formatAge,formatBytes,icon,nameOf} from '../lib/files';
import {count} from '../lib/copy';
import {EmptyState,ErrorState,Loading} from './StateViews';

const KINDS=['all','md','json','txt','pdf','docx','csv'];
/** Fallback row height before the first row can be measured. Matches `--s2` padding
 *  plus the 1.62 line box the row renders at 100% text. */
const ROW_H=33;
/** Rows rendered above and below the viewport, so a fling does not show a blank band. */
const OVERSCAN=8;

export default function Explorer({tree,selected,onSelect,onRetry,inert}:{tree:Loadable<FileNode[]>;selected:string;onSelect:(rel:string)=>void;onRetry:()=>void;inert?:boolean}):ReactNode{
  const [filter,setFilter]=useState('');
  const [kind,setKind]=useState('all');
  const [range,setRange]=useState({start:0,end:40});
  const rows=useRef(new Map<string,HTMLButtonElement>());
  const scroller=useRef<HTMLDivElement>(null);
  const rowH=useRef(ROW_H);
  const pendingFocus=useRef<string|null>(null);

  const files=useMemo(()=>{
    const all=tree.status==='ready'?flatten(tree.data):[];
    const needle=filter.trim().toLowerCase();
    return all.filter(node=>nameOf(node).toLowerCase().includes(needle)&&(kind==='all'||extOf(node.rel)===kind));
  },[tree,filter,kind]);

  const kinds=useMemo(()=>{
    const present=tree.status==='ready'?new Set(flatten(tree.data).map(node=>extOf(node.rel))):new Set<string>();
    return KINDS.filter(value=>value==='all'||present.has(value));
  },[tree]);

  /* A workspace holds hundreds of files and the rail is 260px wide. Rendering all of them
     put 728 buttons in the DOM that nobody could see; Lighthouse counted 2,984 elements.
     The list is a flat array, so the honest fix is a window: render the rows the rail can
     show plus an overscan band, and keep two spacers so the scrollbar still measures the
     whole list. `aria-setsize`/`aria-posinset` keep the position announced for assistive
     tech, which is what the removed rows would have said. */
  const syncWindow=useCallback(()=>{
    const el=scroller.current;
    if(!el)return;
    const height=rowH.current||ROW_H;
    const start=Math.max(0,Math.floor(el.scrollTop/height)-OVERSCAN);
    const count=Math.ceil(el.clientHeight/height)+OVERSCAN*2;
    setRange(previous=>previous.start===start&&previous.end===start+count?previous:{start,end:start+count});
  },[]);

  useEffect(()=>{
    const el=scroller.current;
    if(!el)return;
    syncWindow();
    const observer=new ResizeObserver(syncWindow);
    observer.observe(el);
    return ()=>observer.disconnect();
  },[syncWindow,files.length]);

  /* Re-measure the row height once a row exists, and keep it fractional. Chrome lays the
     row out at 33.6px here; rounding to 33 accumulates a 0.6px error per row, which is 437
     px of scroll distance across 728 files, so the scrollbar would bottom out early. */
  useEffect(()=>{
    const first=rows.current.values().next().value;
    if(first){
      const measured=first.getBoundingClientRect().height;
      if(measured>0)rowH.current=measured;
    }
  },[files.length]);

  /* Keyboard focus may target a row that is outside the window. It is focused on the pass
     after the scroll puts it in range, so no `setTimeout` and no lost keystrokes. */
  useEffect(()=>{
    const rel=pendingFocus.current;
    if(!rel)return;
    const element=rows.current.get(rel);
    if(!element)return;
    element.focus();
    pendingFocus.current=null;
  });

  const focusAt=(index:number)=>{
    const bounded=Math.max(0,Math.min(index,files.length-1));
    const file=files[bounded];
    if(!file)return;
    onSelect(file.rel);
    const el=scroller.current;
    const height=rowH.current||ROW_H;
    if(el){
      const top=bounded*height;
      const bottom=top+height;
      if(top<el.scrollTop)el.scrollTop=top;
      else if(bottom>el.scrollTop+el.clientHeight)el.scrollTop=bottom-el.clientHeight;
      syncWindow();
    }
    pendingFocus.current=file.rel;
    const existing=rows.current.get(file.rel);
    if(existing){existing.focus();pendingFocus.current=null}
  };
  const onKeyDown=(event:KeyboardEvent<HTMLElement>)=>{
    const index=files.findIndex(file=>file.rel===selected);
    if(event.key==='ArrowDown'){event.preventDefault();focusAt(index+1)}
    else if(event.key==='ArrowUp'){event.preventDefault();focusAt(index-1)}
    else if(event.key==='Home'){event.preventDefault();focusAt(0)}
    else if(event.key==='End'){event.preventDefault();focusAt(files.length-1)}
    else if(event.key==='Enter'&&files[index])onSelect(files[index].rel);
  };

  const active=files.findIndex(file=>file.rel===selected);
  const roving=active>=0?selected:(files[0]?.rel??'');
  const start=Math.min(range.start,files.length);
  const end=Math.min(Math.max(range.end,start),files.length);
  const shown=files.slice(start,end);
  const rowHeight=rowH.current||ROW_H;

  const resetScroll=()=>{
    if(scroller.current)scroller.current.scrollTop=0;
    setRange({start:0,end:40});
  };

  return <aside className="panel explorer" inert={inert||undefined}>
    <div className="pane-head"><span className="pane-title">Your files</span><span className="kbd pane-count" aria-hidden="true">{tree.status==='ready'?count(files.length,'file'):'n/a'}</span></div>
    <div className="explorer-tools">
      <input className="filter" aria-label="Filter files" placeholder="e.g. resume" value={filter} onChange={event=>{setFilter(event.target.value);resetScroll()}}/>
      <div className="chips">{kinds.map(value=><button type="button" key={value} className={`chip ${kind===value?'active':''}`} aria-pressed={kind===value} onClick={()=>{setKind(value);resetScroll()}}>{value==='all'?'All':`.${value}`}</button>)}</div>
    </div>
    {tree.status==='loading'?<Loading what="the folder index"/>
      :tree.status==='failed'?<ErrorState inline error={tree.error} what="the folder index" onRetry={onRetry}/>
      :<div className="tree" role="tree" aria-label="Files in this folder" ref={scroller} onScroll={syncWindow} onKeyDown={onKeyDown}>
        {files.length>0?<>
          {start>0&&<div role="presentation" style={{height:start*rowHeight}}/>}
          {shown.map((node,offset)=><button
            type="button"
            role="treeitem" aria-level={1}
            aria-posinset={start+offset+1} aria-setsize={files.length}
            aria-selected={selected===node.rel||undefined}
            tabIndex={node.rel===roving?0:-1}
            ref={element=>{if(element)rows.current.set(node.rel,element);else rows.current.delete(node.rel)}}
            className={`tree-row ${selected===node.rel?'selected':''}`}
            title={`${node.rel}${node.size?`, ${formatBytes(node.size)}`:''}${node.mtime_ns?`, modified ${formatAge(node.mtime_ns)}`:''}`}
            key={node.rel}
            onClick={()=>onSelect(node.rel)}
          ><span aria-hidden="true">{icon(node.rel)}</span><span className="file-name">{nameOf(node)}</span>{!nameOf(node).toLowerCase().endsWith(`.${extOf(node.rel).toLowerCase()}`)&&<span className="ext" aria-hidden="true">{extOf(node.rel)}</span>}</button>)}
          {end<files.length&&<div role="presentation" style={{height:(files.length-end)*rowHeight}}/>}
        </>
          :filter||kind!=='all'
            ?<EmptyState title={`No files match ${filter?`“${filter}”`:`the .${kind} filter`}`}>
              <p>Clear the filter, or search all text with ⌘K.</p>
            </EmptyState>
            :<EmptyState title="No files to show">
              <p>The tree loaded and this folder has none. <code>.dossier</code>, <code>.git</code> and <code>node_modules</code> are skipped by design.</p>
            </EmptyState>}
      </div>}
  </aside>;
}
