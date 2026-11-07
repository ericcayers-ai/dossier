import {useEffect,useMemo,useRef,useState} from 'react';
import type {KeyboardEvent,ReactNode} from 'react';
import {api} from '../lib/api';
import {ErrorState} from './StateViews';
import {count} from '../lib/copy';

type Hit={rel:string;snippet?:string;kind?:string};
export type Place={id:string;label:string;area:string};

/* The palette is the shortcut layer: with nothing typed it is a launcher for the
   eleven panes, and typing filters places and files together. Before this, ⌘K could
   only find files, so "jobs" returned capture JSON and the pane was still two clicks
   away through the two nav rows. */
const score=(place:Place,text:string):number=>{
  const needle=text.toLowerCase();
  if(!needle)return 1;
  const label=place.label.toLowerCase();
  const area=place.area.toLowerCase();
  if(label===needle)return 100;
  if(label.startsWith(needle))return 80;
  if(area.startsWith(needle))return 60;
  if(label.includes(needle))return 40;
  if(`${area} ${label}`.includes(needle))return 20;
  return 0;
};

/* The index returns snippets with `<mark>` around the match. Rendered as a string that
   markup showed up literally — a palette row reading `NZ Government <mark>Jobs</mark>`
   — and a raw JSON quote is not a sentence. This turns the markup into a real
   highlight and keeps a window of context around the first match. */
const Snippet=({text}:{text:string})=>{
  const clean=text.replace(/\s+/g,' ').trim();
  const first=clean.search(/<mark>/i);
  const window=160;
  let body=clean;
  let lead=false;
  if(first>window/2){
    const start=Math.max(0,first-Math.round(window/3));
    body=(start>0?'…':'')+clean.slice(start,start+window);
    lead=start>0;
  }else if(clean.length>window){
    body=clean.slice(0,window)+'…';
  }
  const parts=body.split(/<mark>|<\/mark>/i);
  let marked=false;
  return <>{lead?'':null}{parts.map((part,index)=>{
    if(index===0)marked=false;
    const isMark=index%2===1;
    return isMark?<mark key={index}>{part}</mark>:<span key={index}>{part}</span>;
  })}</>;
};

/* The index returns matches in its own order, which puts audit JSON above the document a
   person was looking for: "resume" led with `verification-search-batch.json` before any
   resume. Relevance is the server's job; this is about the shelf order — the user's own
   documents first, generated audit trails after them. */
const INTERNAL_PATH=/^(_preview|\.dossier|resync-)/i;
const AUDIT_NAME=/(audit|verification|snapshot|batch|report)/i;
const rank=(hit:Hit,index:number,needle:string):number=>{
  const name=(hit.rel.split('/').pop()||'').toLowerCase();
  let score=1_000-index;
  if(needle&&name.includes(needle.toLowerCase()))score+=400;
  if(/\.(pdf|docx|md|txt)$/i.test(hit.rel))score+=140;
  if(INTERNAL_PATH.test(hit.rel))score-=500;
  if(AUDIT_NAME.test(name)&&!/\.(pdf|docx)$/i.test(name))score-=220;
  if((hit.snippet||'').trim().startsWith('{'))score-=60;
  return score;
};

export default function Palette({onClose,onOpen,onGo,places=[]}:{onClose:()=>void;onOpen:(rel:string)=>void;onGo?:(pane:string)=>void;places?:Place[]}):ReactNode{
  const [query,setQuery]=useState('');
  const [hits,setHits]=useState<Hit[]>([]);
  const [error,setError]=useState<unknown>(null);
  const [state,setState]=useState<'idle'|'loading'|'ready'>('idle');
  const [active,setActive]=useState(0);
  const dialog=useRef<HTMLDivElement>(null);
  const input=useRef<HTMLInputElement>(null);
  const sequence=useRef(0);
  const list=useRef<HTMLDivElement>(null);

  useEffect(()=>{input.current?.focus()},[]);

  /* One debounced request per pause, and a sequence guard so a slow earlier
     response cannot overwrite a later one. */
  useEffect(()=>{
    const text=query.trim();
    if(!text){setHits([]);setError(null);setState('idle');return}
    setState('loading');
    const ticket=sequence.current+=1;
    const timer=window.setTimeout(()=>{
      api.search(text).then(value=>{
        if(ticket!==sequence.current)return;
        setHits(Array.isArray(value)?value:[]);
        setError(null);
        setActive(0);
        setState('ready');
      }).catch(reason=>{
        if(ticket!==sequence.current)return;
        setHits([]);
        setError(reason);
        setState('ready');
      });
    },160);
    return()=>window.clearTimeout(timer);
  },[query]);

  const placeMatches=useMemo(()=>places
    .map(place=>({place,rank:score(place,query.trim())}))
    .filter(item=>item.rank>0)
    .sort((a,b)=>b.rank-a.rank)
    .map(item=>item.place),[places,query]);

  const orderedHits=useMemo(()=>{
    const needle=query.trim();
    return hits.map((hit,index)=>({hit,score:rank(hit,index,needle)}))
      .sort((a,b)=>b.score-a.score)
      .map(item=>item.hit);
  },[hits,query]);

  const rows=useMemo(()=>[
    ...placeMatches.map(place=>({kind:'place' as const,place})),
    ...orderedHits.map(hit=>({kind:'file' as const,hit})),
  ],[placeMatches,orderedHits]);

  const open=(index:number)=>{
    const row=rows[index];
    if(!row)return;
    if(row.kind==='place')onGo?.(row.place.id);
    else onOpen(row.hit.rel);
    onClose();
  };

  const onKeyDown=(event:KeyboardEvent<HTMLDivElement>)=>{
    if(event.key==='Escape'){event.preventDefault();onClose();return}
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){
      event.preventDefault();
      if(rows.length===0)return;
      const next=event.key==='ArrowDown'?(active+1)%rows.length:(active-1+rows.length)%rows.length;
      setActive(next);
      list.current?.querySelectorAll<HTMLElement>('[role="option"]')[next]?.scrollIntoView({block:'nearest'});
      return;
    }
    if(event.key==='Enter'){event.preventDefault();open(active);return}
    if(event.key==='Tab'){
      const nodes=dialog.current?.querySelectorAll<HTMLElement>('input, button, [href], select, textarea');
      const items=nodes?Array.from(nodes):[];
      if(items.length===0)return;
      const first=items[0];
      const last=items[items.length-1];
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
    }
  };

  const placesShown=placeMatches.length;
  return <div className="palette-backdrop" onMouseDown={event=>{if(event.target===event.currentTarget)onClose()}}>
    <div className="palette" role="dialog" aria-modal="true" aria-label="Search and go" ref={dialog} onKeyDown={onKeyDown}>
      <input
        ref={input}
        role="combobox"
        aria-label="Search files, or type a place to go to"
        aria-expanded={rows.length>0}
        aria-autocomplete="list"
        aria-controls="palette-results"
        aria-activedescendant={rows[active]?`palette-hit-${active}`:undefined}
        placeholder="Search files or go to a pane"
        name="dossier-search"
        autoComplete="off"
        spellCheck={false}
        value={query}
        onChange={event=>{setQuery(event.target.value);setActive(0)}}
      />
      <p className="sr-only" role="status" aria-live="polite">
        {state==='idle'?`${count(placesShown,'place')}.`:state==='loading'?'Searching…':`${count(hits.length,'result')}.`}
      </p>
      <div className="palette-results" id="palette-results" role="listbox" aria-label="Places and search results" ref={list}>
        {rows.length>0?rows.map((row,index)=>row.kind==='place'
          ?<button
              type="button"
              role="option"
              aria-selected={index===active}
              id={`palette-hit-${index}`}
              className="result place"
              key={`place-${row.place.id}`}
              onMouseEnter={()=>setActive(index)}
              onClick={()=>open(index)}
            ><div className="result-path">{row.place.label}</div><div className="result-snippet">Go to {row.place.area}</div></button>
          :<button
              type="button"
              role="option"
              aria-selected={index===active}
              id={`palette-hit-${index}`}
              className="result"
              key={`${row.hit.rel}-${index}`}
              onMouseEnter={()=>setActive(index)}
              onClick={()=>open(index)}
            ><div className="result-path" translate="no">{row.hit.rel}</div><div className="result-snippet">{row.hit.snippet?<Snippet text={row.hit.snippet}/>:(row.hit.kind||'file')}</div></button>)
          :error?<ErrorState inline error={error} what="Searching the index"/>
          :state==='loading'?<div className="loading" role="status">Searching…</div>
          :state==='ready'?<div className="empty">No place or file matches <b>“{query}”</b>.</div>
          :<div className="empty">Nothing to go to.</div>}
      </div>
    </div>
  </div>;
}
