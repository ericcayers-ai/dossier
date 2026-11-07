import {useEffect,useMemo,useState} from 'react';
import type {ReactNode} from 'react';
import {api,fault} from '../lib/api';
import type {Action,Bundle,Member} from '../lib/api';
import type {Loadable} from '../lib/useLoad';
import {useLoad} from '../lib/useLoad';
import {appliesTo,extOf,formatBytes,siblingWith} from '../lib/files';
import {ErrorState,Loading} from './StateViews';
import {count,isOne} from '../lib/copy';

const ROLES=['source','analysis','artifact','render','proof'] as const;
const ROLE_LABEL:Record<string,string>={source:'Source',analysis:'Analysis',artifact:'Artifact',render:'Render',proof:'Proof'};

function ActionRow({action,rel,onRun}:{action:Action;rel:string;onRun:(action:Action,confirmed:boolean)=>Promise<void>}):ReactNode{
  const [confirming,setConfirming]=useState(false);
  const needsConfirm=Boolean(action.confirm||action.writes);
  if(confirming)return <div className="confirm">
    <span>Run {action.label.toLowerCase()} on this file?</span>
    <button type="button" onClick={()=>setConfirming(false)}>Do not run it</button>
    <button type="button" className="primary" onClick={()=>{setConfirming(false);void onRun(action,true)}}>Run</button>
  </div>;
  return <button type="button" className="action" data-rel={rel} onClick={()=>{if(needsConfirm)setConfirming(true);else void onRun(action,false)}}>{action.label}</button>;
}

function ExportRow({rel,onDone}:{rel:string;onDone:(message:string)=>void}):ReactNode{
  const [target,setTarget]=useState(()=>siblingWith(rel,'pdf'));
  const [busy,setBusy]=useState(false);
  useEffect(()=>setTarget(siblingWith(rel,'pdf')),[rel]);
  const run=async()=>{
    setBusy(true);
    try{
      const result=await api.exportFile(rel,target);
      onDone(`Exported to ${result.path}`);
    }catch(error){
      const {title,next}=fault(error,'Exporting this document');
      onDone(`${title} ${next}`);
    }finally{setBusy(false)}
  };
  return <div className="export-row">
    <label className="field">
      <span>Export to (relative path)</span>
      <input value={target} onChange={event=>setTarget(event.target.value)} aria-label="Export destination path"/>
    </label>
    <div className="button-row">
      <button type="button" onClick={()=>void run()} disabled={busy||!target.trim()}>{busy?'Exporting…':'Export'}</button>
    </div>
  </div>;
}

export default function BundleRail({bundle,selected,onOpen,onRetry,onChanged,pulse=false,inert}:{bundle:Loadable<Bundle>;selected:string;onOpen:(rel:string)=>void;onRetry:()=>void;onChanged:()=>void;pulse?:boolean;inert?:boolean}):ReactNode{
  const actions=useLoad(()=>api.actions(),[]);
  const [log,setLog]=useState<{rel:string;text:string}|null>(null);

  /* Output belongs to the file it came from: clear it when the selection moves. */
  useEffect(()=>setLog(null),[selected]);

  const all=bundle.status==='ready'?(bundle.data.members??[]):[];
  const declared=actions.state.status==='ready'?actions.state.data:[];
  const applicable=useMemo(()=>declared.filter(action=>appliesTo(selected,action.applies_to)),[declared,selected]);
  const hidden=declared.length-applicable.length;
  const stale=useMemo(()=>bundle.status==='ready'?(bundle.data.stale??[]):[],[bundle]);

  const run=async(action:Action,confirmed:boolean)=>{
    try{
      const result=await api.runAction(action.id,selected,confirmed);
      setLog({rel:selected,text:[result.stdout,result.stderr].filter(Boolean).join('\n')||`Finished with exit code ${result.returncode}`});
    }catch(error){
      const {title,next}=fault(error,`Running ${action.label}`);
      setLog({rel:selected,text:`${title} ${next}`});
    }
    onChanged();
  };

  const byteTotal=all.reduce((sum,member)=>sum+(member.size??0),0);

  return <aside className="panel rail" aria-label="Bundle rail" inert={inert||undefined}>
    <div className="pane-head">
      <span className="pane-title">Bundle rail</span>
      {bundle.status==='ready'&&all.length>0
        ?<span className={`kbd ${stale.length?'stale':''} ${pulse?'pulse':''}`}>{`${bundle.data.stem_key?`${bundle.data.stem_key}: `:''}${stale.length?`${stale.length} stale of ${all.length}`:`${all.length} current`}`}</span>
        :<span className="kbd">n/a</span>}
    </div>
    <div className="rail-body">
      {!selected?<div className="empty">Select a file.</div>
        :bundle.status==='loading'?<Loading what="the bundle"/>
        :bundle.status==='failed'?<ErrorState inline error={bundle.error} what="resolving this file’s bundle" onRetry={onRetry}/>
        :all.length===0?<div className="empty">No sibling files share this stem.</div>
        :<>
          {stale.length>0&&<div className="notice" role="status">{`${count(stale.length,'file')} older than the source it came from: ${stale.map(base=>base.split('/').pop()).join(', ')}`}</div>}
          {ROLES.map(role=>{
            const list=all.filter((member:Member)=>member.role===role);
            if(!list.length)return null;
            return <section className="rail-section" key={role}>
              <h3>{ROLE_LABEL[role]} <span className="rail-count">{list.length||''}</span></h3>
              {list.map(member=><button type="button" className="rail-row" key={member.rel} onClick={()=>onOpen(member.rel)} title={member.rel}>
                <span className="name">{member.rel.split('/').pop()}</span>
                {typeof member.size==='number'&&<small>{formatBytes(member.size)}</small>}
                {member.stale&&<span className="stale" aria-label="older than its source">stale</span>}
              </button>)}
            </section>;
          })}
          {(()=>{const empty=ROLES.filter(role=>!all.some((m:Member)=>m.role===role));
            return empty.length?<div className="rail-facts">{`Nothing yet: ${empty.map(role=>ROLE_LABEL[role].toLowerCase()).join(', ')}.`}</div>:null})()}
          <div className="rail-facts">{`${count(all.length,'file')}, ${formatBytes(byteTotal)} in this set`}</div>
        </>}

      <section className="rail-section actions">
        <h3>Actions</h3>
        {!selected?<div className="rail-empty">Select a file first.</div>
          :actions.state.status==='loading'?<Loading what="the action list"/>
          :actions.state.status==='failed'?<ErrorState inline error={actions.state.error} what="the action list" onRetry={actions.reload}/>
          :applicable.length===0?<div className="rail-empty">{declared.length===0?'No actions configured.':`No action applies to a .${extOf(selected)||'?'} file.`}</div>
          :applicable.map(action=><ActionRow key={action.id} action={action} rel={selected} onRun={run}/>)}
        {hidden>0&&applicable.length>0&&selected&&<p className="rail-empty" role="note">
          {`${count(hidden,'action')} hidden — not applicable to a ${extOf(selected)?`.${extOf(selected)}`:''} file.`}
        </p>}
        {selected&&extOf(selected)==='docx'&&<ExportRow rel={selected} onDone={message=>setLog({rel:selected,text:message})}/>}
        {log&&log.rel===selected&&<pre className="action-log" role="status" aria-live="polite">{log.text}</pre>}
      </section>
    </div>
  </aside>;
}
