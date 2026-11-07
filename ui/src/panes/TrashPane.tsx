import {useMemo,useState} from 'react';
import type {ReactNode} from 'react';
import {api,fault} from '../lib/api';
import type {PruneReport,TrashEntry} from '../lib/api';
import {useLoad} from '../lib/useLoad';
import {baseName,formatAge,formatBytes,formatWhen} from '../lib/files';
import {ErrorState,Loading} from './StateViews';
import {count,isOne} from '../lib/copy';

const counts=(report:PruneReport):string=>{
  if(report.exceptional)return `The last prune could not run (${report.error}).`;
  if(!report.enabled)return report.reason;
  const head=`${report.removed_count} removed, ${formatBytes(report.freed_bytes)} freed, ${report.kept_count} kept, ${report.skipped_count} skipped`;
  return report.dry_run?`${head}, dry run, nothing deleted`:head;
};

const when=(row:{trashed_at:string|null;mtime_ns?:number})=>row.trashed_at?formatWhen(row.trashed_at):formatAge(row.mtime_ns);

/** Every overwrite this app makes routes through `.dossier/trash/` first, and the
 *  folder is capped by age (see `dossier.safety.prune_trash`). The pane shows all
 *  three buckets the API reports — only `entries` can be restored; the other two
 *  are listed so the folder never silently hides backups it is holding — plus the
 *  effective cap, so the policy that prunes them is visible rather than implied. */
export default function TrashPane({onRestored}:{onRestored:(rel:string)=>void}):ReactNode{
  const trash=useLoad(()=>api.trash(),[]);
  const [message,setMessage]=useState('');
  const [faulted,setFaulted]=useState(false);
  const [busy,setBusy]=useState('');
  const [pruning,setPruning]=useState(false);
  const [prune,setPrune]=useState<PruneReport|null>(null);

  /* Grouped before any early return: a hook after `if(loading)return` runs on one
     render and not the next, which React rejects and the pane vanishes. */
  const groups=useMemo(()=>{
    const ready=trash.state.status==='ready'?trash.state.data.entries??[]:[];
    const map=new Map<string,TrashEntry[]>();
    for(const entry of ready)map.set(entry.rel,[...(map.get(entry.rel)??[]),entry]);
    const at=(list:TrashEntry[])=>list[0]?.trashed_at?Date.parse(list[0].trashed_at)||0:0;
    return [...map.entries()].sort((a,b)=>at(b[1])-at(a[1]));
  },[trash.state]);

  const note=(text:string,isFault:boolean)=>{setMessage(text);setFaulted(isFault)};

  const restore=async(entry:TrashEntry)=>{
    const rel=entry.rel;
    setBusy(rel);note('',false);
    try{
      const result=await api.trashRestore(entry);
      note(`Restored ${result.rel??rel}.`,false);
      onRestored(result.rel??rel);
      trash.reload();
    }catch(error){
      const {title,next}=fault(error,'Restoring that file');
      note(`${title} ${next}`,true);
    }finally{setBusy('')}
  };

  const runPrune=async(dryRun:boolean)=>{
    setPruning(true);note('',false);setPrune(null);
    try{
      const report=await api.trashPrune(dryRun);
      setPrune(report);
      note(counts(report),false);
      if(!dryRun)trash.reload();
    }catch(error){
      const {title,next}=fault(error,'Applying the retention window');
      note(`${title} ${next}`,true);
    }finally{setPruning(false)}
  };

  if(trash.state.status==='loading')return <div className="trash-pane">
    <h1>Trash</h1>
    <Loading what="the trash folder" rows={4}/>
  </div>;
  if(trash.state.status==='failed')return <div className="trash-pane">
    <h1>Trash</h1>
    <ErrorState error={trash.state.error} what="Listing the trash folder" onRetry={trash.reload}/>
  </div>;

  const data=trash.state.data;
  const entries=data.entries??[];
  const external=data.external??[];
  const unmanaged=data.unmanaged??[];
  const retention=data.retention;
  const held=entries.length+external.length+unmanaged.length;

  return <div className="trash-pane">
    <div className="audit-head">
      <div>
        <h1>Trash</h1>
        <p>Every overwrite this app makes keeps a timestamped copy first. Restoring writes the copy back to its original path and trashes whatever is there now, so a restore is itself reversible.</p>
      </div>
      <button type="button" onClick={trash.reload}>Refresh</button>
    </div>

    {retention&&<div className="audit-counts">
      <div className="audit-count"><span>retention</span><b>{retention.enabled?count(retention.retention_days,'day'):'off'}</b><span>from {retention.source}</span></div>
      <div className="audit-count"><span>restorable</span><b>{entries.length}</b><span>of {held} kept</span></div>
      <div className="audit-count"><span>kept elsewhere</span><b>{external.length+unmanaged.length}</b><span>not restorable</span></div>
      <div className="audit-count"><span>last prune</span><b>{data.last_prune?data.last_prune.removed_count:'never'}</b><span>{data.last_prune?`removed, ${formatBytes(data.last_prune.freed_bytes)} freed`:'no prune recorded'}</span></div>
    </div>}

    <div className="button-row">
      <button type="button" onClick={()=>void runPrune(false)} disabled={pruning}>{pruning?'Pruning…':'Prune now'}</button>
      <button type="button" onClick={()=>void runPrune(true)} disabled={pruning}>Check what would go</button>
      {retention&&<span className="reason">{`Backups older than ${count(retention.retention_days,'day')} are removed.`}</span>}
    </div>
    {retention?.warnings?.map(warning=><div className="notice" role="alert" key={warning}>{warning}</div>)}

    <p className="sr-only" role="status" aria-live="polite">{message}</p>
    {message&&<div className={`notice ${faulted?'':'ok'}`} role={faulted?'alert':'status'}>{message}</div>}

    {prune&&<div className="notice">
      <b>{`${prune.removed_count} removed by that run.`}</b>
      {prune.removed.length>0&&<ul>{prune.removed.slice(0,20).map(row=><li key={row.entry}>{`${row.entry}. ${row.reason}${row.age_days!==undefined?` (${count(row.age_days,'day')} old)`:''}`}</li>)}</ul>}
      {prune.kept.length>0&&<p>{`Kept: ${prune.kept.slice(0,6).map(row=>`${row.entry} (${row.reason})`).join('; ')}`}</p>}
      {prune.skipped.length>0&&<p>{`Skipped: ${prune.skipped.slice(0,6).map(row=>`${row.entry} (${row.reason})`).join('; ')}`}</p>}
      {prune.warnings.map(warning=><p key={warning}>{warning}</p>)}
    </div>}

    {entries.length===0
      ?<p className="empty">No restorable copies yet. The first overwrite of a file will appear here.</p>
      :<div className="results">{groups.map(([rel,list])=><section className="trash-group" key={rel}>
        <div className="result-line">
          <b title={rel}>{baseName(rel)}</b>
          <span title={list[0].trashed_at??undefined}>{when(list[0])}</span>
          <span className="reason">{count(list.length,'copy','copies')}</span>
          <button type="button" onClick={()=>void restore(list[0])} disabled={busy===rel}>{busy===rel?'Restoring…':'Restore newest'}</button>
        </div>
        {list.length>1&&<details className="trash-more">
          <summary>{`All ${count(list.length,'copy','copies')}`}</summary>
          {list.map(entry=><div className="result-line" key={entry.trash_rel}>
            <span title={entry.trash_rel}>{when(entry)}</span>
            <span>{formatBytes(entry.size)}</span>
            <button type="button" onClick={()=>void restore(entry)} disabled={busy===rel}>Restore this one</button>
          </div>)}
        </details>}
      </section>)}</div>}

    {external.length>0&&<>
      <h2>Kept for files outside this folder</h2>
      <p className="reason">Files overwritten outside this folder. Their original paths cannot be mapped back, so they are listed and not restorable.</p>
      <div className="results">{external.slice(0,6).map(row=><div className="result-line" key={row.trash_rel}>
        <b>{row.name}</b><span>{formatBytes(row.size)}</span><span>{when(row)}</span><span className="reason">not restorable</span>
      </div>)}
      {external.length>6&&<p className="reason">{`and ${external.length-6} more of the same kind, not restorable either.`}</p>}</div>
    </>}

    {unmanaged.length>0&&<>
      <h2>Reported, not restorable</h2>
      <p className="reason">Superseded renders and anything else in the folder with no honest reverse mapping. They are listed so the pane never implies it holds only what it can restore.</p>
      <div className="results">{unmanaged.slice(0,6).map(row=><div className="result-line" key={row.trash_rel}>
        <b>{row.name}</b><span>{formatBytes(row.size)}</span><span>{when(row)}</span><span className="reason">{row.trash_rel}</span>
      </div>)}
      {unmanaged.length>6&&<p className="reason">{`and ${unmanaged.length-6} more, listed in the audit trail.`}</p>}</div>
    </>}
  </div>;
}
