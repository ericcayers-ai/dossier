import {useState} from 'react';
import type {ReactNode} from 'react';
import {api} from '../lib/api';
import {useLoad} from '../lib/useLoad';
import {ErrorState,Loading} from './StateViews';

export default function SyncPane():ReactNode{
  const handoff=useLoad(()=>api.handoff(),[]);
  const [copied,setCopied]=useState(false);

  if(handoff.state.status==='loading')return <div className="sync-pane">
    <h1>Sync</h1>
    <Loading what="the reconciliation packet" rows={4}/>
  </div>;
  if(handoff.state.status==='failed')return <div className="sync-pane">
    <h1>Sync</h1>
    <ErrorState error={handoff.state.error} what="Building the reconciliation packet" onRetry={handoff.reload}/>
  </div>;

  const copy=async()=>{
    try{
      await navigator.clipboard.writeText(handoff.state.status==='ready'?handoff.state.data.prompt:'');
      setCopied(true);
      window.setTimeout(()=>setCopied(false),1500);
    }catch{
      setCopied(false);
    }
  };

  /* The packet is a wall of markdown meant for another program, so the screen
     shows one line about what it holds and the copy button; the text itself is
     one click away instead of filling the pane on arrival. */
  const packet=handoff.state.data.packet as {generated_on?:string;counts?:Record<string,number>};
  const counts=Object.entries(packet?.counts??{}).filter(([,value])=>Number(value)>0).slice(0,3);
  const summary=counts.map(([name,value])=>`${value} ${name.replace(/_/g,' ')}`).join(', ');
  return <div className="sync-pane">
    <div className="audit-head">
      <div>
        <h1>Sync</h1>
        <p className="pane-purpose">Hand this session to another AI in one paste. Nothing is sent anywhere unless you paste it.</p>
      </div>
      <button type="button" className="primary" onClick={()=>void copy()}>{copied?'Copied':'Copy prompt'}</button>
    </div>
    <p className="sr-only" role="status" aria-live="polite">{copied?'Prompt copied to the clipboard.':''}</p>
    <p className="sync-note">{`Generated ${packet?.generated_on??'just now'}${summary?` — ${summary}`:''}. Paste it into an AI of your choice; nothing leaves this machine from here.`}</p>
    <details className="sync-more">
      <summary>Show the packet text</summary>
      <textarea className="sync-text" readOnly value={handoff.state.data.prompt} aria-label="AI sync prompt"/>
    </details>
  </div>;
}
